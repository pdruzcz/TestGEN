"""Przetwarzanie zdarzeń z webhooków SCM — Epic 8, Story 8.1 (AC3, AC4).

Endpoint webhooka musi odpowiedzieć w kilka sekund (GitHub zrywa po 10 s),
więc cała praca — klonowanie repozytorium, indeksowanie plików, analiza —
dzieje się tutaj.

Projekt dla repozytorium tworzymy leniwie, przy pierwszym zdarzeniu, i potem
zasilamy go kolejnymi pushami. Dzięki temu podłączenie repozytorium nie
zaśmieca listy projektów, dopóki nic się w nim nie dzieje.

Story 8.3 dokłada status checki. Wynik analizy jest znany dopiero po
pipelinie, który biegnie w osobnym zadaniu, więc status końcowy wysyłamy
z callbacków Celery (``link``/``link_error``) podpiętych do dispatchu —
inaczej musielibyśmy blokować workera na odpytywaniu cudzego zadania.
Zdarzenie zostaje w stanie ``processing`` aż do callbacku: „ukończone"
ma znaczyć „analiza się skończyła", a nie „zlecenie poszło w świat".
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from app.services.integrations.status_check_builder import PENDING_DESCRIPTION
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (30, 120, 600)
# Nazwa projektu z nazwy repo: "octocat/hello-world" → "octocat/hello-world".
# Kolizję z istniejącym projektem rozstrzyga sufiks — nazwy są unikalne
# per tenant (uq_projects_name_tenant).
_MAX_PROJECT_NAME = 255


async def _ensure_project(session, integration) -> uuid.UUID:
    """Zwraca projekt integracji, tworząc go przy pierwszym zdarzeniu."""
    from app.models.project import Project
    from app.services.project.project_service import create_project

    if integration.project_id is not None:
        project = await session.get(Project, integration.project_id)
        if project is not None and not project.is_deleted:
            return project.id
        # Projekt skasowany ręcznie — odtwarzamy go pod tą samą integracją.
        integration.project_id = None

    from app.models.user import User

    actor = await session.get(User, integration.user_id)
    if actor is None:
        raise RuntimeError("Użytkownik, który podłączył repozytorium, już nie istnieje")
    actor._tenant_id = integration.tenant_id  # type: ignore[attr-defined]

    base_name = integration.repo_full_name[:_MAX_PROJECT_NAME]
    name = base_name
    for suffix in range(1, 10):
        from sqlalchemy import select

        exists = await session.execute(
            select(Project).where(
                Project.tenant_id == integration.tenant_id,
                Project.name == name,
                Project.is_deleted.is_(False),
            )
        )
        if exists.scalar_one_or_none() is None:
            break
        name = f"{base_name} ({suffix})"

    project = await create_project(
        session,
        actor,
        name=name,
        description=f"Projekt utworzony automatycznie z repozytorium {integration.repo_url}",
        tenant_id=integration.tenant_id,
    )
    integration.project_id = project.id
    await session.flush()
    return project.id


async def _set_tenant(session, tenant_id) -> None:
    """Kontekst RLS dla bieżącej transakcji (``SET LOCAL`` ginie przy commicie)."""
    from sqlalchemy import text

    await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
    session.info["tenant_scope"] = str(tenant_id)


async def _run_webhook_analysis_impl(event_id: str) -> dict:
    from app.core.constants import NIL_UUID
    from app.core.database import task_session
    from app.core.encryption import decrypt_token
    from app.models.integration import (
        IntegrationEvent,
        ScmEventStatus,
        ScmEventType,
        ScmIntegration,
    )
    from app.models.user import User
    from app.services.project.git_service import connect_repo
    from app.workers.pipeline import run_pipeline

    eid = uuid.UUID(event_id)

    async with task_session() as session:
        # Zdarzenie znajdujemy bez kontekstu tenanta — dopiero ono go niesie.
        await _set_tenant(session, NIL_UUID)
        event = await session.get(IntegrationEvent, eid)
        if event is None:
            logger.warning("Zdarzenie %s nie istnieje — pomijam", event_id)
            return {"status": "missing"}

        integration = await session.get(ScmIntegration, event.integration_id)
        if integration is None or not integration.is_active:
            event.status = ScmEventStatus.SKIPPED
            event.error_message = "Integracja została usunięta lub dezaktywowana"
            event.completed_at = datetime.now(UTC)
            await session.commit()
            return {"status": "skipped"}

        tid = integration.tenant_id
        integration_id = integration.id
        repo_full_name = integration.repo_full_name
        provider = integration.provider
        config = dict(integration.config or {})
        commit_sha = event.commit_sha
        event_type = event.event_type
        pr_number = event.pr_number
        branch = event.branch or integration.default_branch

        await _set_tenant(session, tid)
        event.status = ScmEventStatus.PROCESSING
        await session.commit()

        try:
            await _set_tenant(session, tid)
            integration = await session.get(ScmIntegration, integration_id)
            project_id = await _ensure_project(session, integration)

            actor = await session.get(User, integration.user_id)
            actor._tenant_id = tid  # type: ignore[attr-defined]
            access_token = decrypt_token(integration.access_token_encrypted, tid)

            # Self-hosted GitLab nie mieści się w stałej whiteliście hostów,
            # a jego URL klonowania wymaga prefiksu ``oauth2:`` tak jak gitlab.com.
            clone_options = _clone_options(integration)
            outcome = await connect_repo(
                session,
                actor,
                project_id,
                repo_url=integration.repo_url,
                branch=branch,
                auth_token=access_token,
                **clone_options,
            )
            # Commit PRZED dispatchem: pipeline biegnie w innym procesie i musi
            # zobaczyć zaindeksowane pliki, inaczej analizuje pusty projekt.
            await session.commit()

            # Status „w toku" na PR/MR (AC1/AC2) — zanim pipeline ruszy, żeby
            # autor zmiany od razu wiedział, że coś się dzieje.
            await _send_status(
                integration, tid, commit_sha, project_id, "pending", PENDING_DESCRIPTION
            )

            task = run_pipeline.apply_async(
                kwargs={
                    "tenant_id": str(tid),
                    "project_id": str(project_id),
                    "engine_mode": "native",
                    "modules": ["code_analysis"],
                },
                # Wynik analizy znamy dopiero po pipelinie — stąd callbacki
                # zamiast czekania (Story 8.3).
                link=finalize_webhook_status.s(event_id),
                link_error=fail_webhook_status.s(event_id),
            )

            result = {
                "status": "dispatched",
                "project_id": str(project_id),
                "task_id": task.id,
                "files_indexed": outcome.files_indexed,
                "branch": branch,
            }

            # Pull/merge request: obok analizy plików generujemy testy regresyjne
            # z diffa (Story 1.44). Niepowodzenie tego kroku nie unieważnia
            # analizy głównej — diff jest dodatkiem, nie warunkiem.
            if event_type in (ScmEventType.PULL_REQUEST, ScmEventType.MERGE_REQUEST) and pr_number:
                try:
                    result["regression_tests"] = await _generate_change_regression_tests(
                        provider, access_token, repo_full_name, pr_number, config
                    )
                except Exception as exc:  # diff to dodatek — logujemy i idziemy dalej
                    logger.warning(
                        "Analiza diffa zmiany #%s (%s) nie powiodła się: %s",
                        pr_number,
                        provider.value,
                        exc,
                    )
                    result["regression_tests"] = 0

            await _set_tenant(session, tid)
            event = await session.get(IntegrationEvent, eid)
            event.task_id = task.id
            # Status zostaje ``processing`` — domknie go callback pipeline'u.
            await session.commit()

            return result

        except Exception as exc:
            logger.error("Analiza zdarzenia %s nie powiodła się: %s", event_id, exc)
            # Rollback przed zapisem statusu — transakcja po błędzie jest
            # zatruta i każdy kolejny SQL w niej też by padł.
            await session.rollback()
            await _set_tenant(session, tid)
            event = await session.get(IntegrationEvent, eid)
            if event is not None:
                event.status = ScmEventStatus.FAILED
                event.error_message = str(exc)[:2000]
                event.completed_at = datetime.now(UTC)
                await session.commit()
            raise


def _clone_options(integration) -> dict:
    """Parametry klonowania zależne od dostawcy (Story 8.2).

    GitHub klonuje się domyślną ścieżką; GitLab self-hosted wymaga dopuszczenia
    hosta instancji i prefiksu ``oauth2:`` w URL-u z tokenem.
    """
    from app.models.integration import ScmProvider
    from app.services.integrations import gitlab_service

    if integration.provider != ScmProvider.GITLAB:
        return {}

    gitlab_url = (integration.config or {}).get("gitlab_url") or gitlab_service.default_gitlab_url()
    return {
        "extra_allowed_hosts": {gitlab_service.host_of(gitlab_url)},
        "auth_scheme": "oauth2",
    }


async def _generate_change_regression_tests(
    provider,
    access_token: str,
    repo_full_name: str,
    change_number: int,
    config: dict,
) -> int:
    """Liczba testów regresyjnych z diffa PR (GitHub) lub MR (GitLab), AC4."""
    from app.models.integration import ScmProvider
    from app.services.generators.regression_generator import RegressionTestGenerator
    from app.services.integrations import github_service, gitlab_service

    if provider == ScmProvider.GITLAB:
        project_id = config.get("gitlab_project_id")
        if not project_id:
            return 0
        gitlab_url = config.get("gitlab_url") or gitlab_service.default_gitlab_url()
        diff_text = await gitlab_service.get_merge_request_diff(
            access_token, gitlab_url, int(project_id), change_number
        )
    else:
        diff_text = await github_service.get_pull_request_diff(
            access_token, repo_full_name, change_number
        )

    if not diff_text.strip():
        return 0
    tests = RegressionTestGenerator().generate_from_diff(diff_text)
    return len(tests)


@celery_app.task(
    bind=True,
    name="integrations.run_webhook_analysis",
    queue="analysis",
    max_retries=3,
)
def run_webhook_analysis(self, event_id: str) -> dict:
    """Klonuje repozytorium ze zdarzenia i uruchamia analizę (AC3/AC4)."""
    try:
        return asyncio.run(_run_webhook_analysis_impl(event_id))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Ponowienie %d/%d dla integrations.run_webhook_analysis (za %ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Błąd przetwarzania zdarzenia %s: %s", event_id, exc)
        raise


# ── Story 8.3: status checki na PR/MR ───────────────────────────────────────


def _target_url(project_id) -> str:
    """Link z PR-a do wyników w TestGEN (AC1)."""
    from app.core.config import get_settings

    base = get_settings().frontend_base_url.rstrip("/")
    return f"{base}/projects/{project_id}/results"


def _status_config(integration) -> dict:
    """Ustawienia status checka z ``config`` integracji, z domyślnymi (AC3)."""
    from app.services.integrations.status_check_builder import (
        DEFAULT_THRESHOLD,
        normalize_threshold,
    )

    config = integration.config or {}
    return {
        "severity_threshold": normalize_threshold(config.get("severity_threshold") or DEFAULT_THRESHOLD),
        "post_comment": config.get("post_comment", True),
        "fail_on_threshold": config.get("fail_on_threshold", True),
    }


async def _send_status(
    integration,
    tenant_id,
    commit_sha: str | None,
    project_id,
    state: str,
    description: str,
) -> None:
    """Wysyła status commita do właściwego dostawcy (AC1/AC2).

    Brak ``commit_sha`` to zwykły push bez kontekstu zmiany — nie ma czego
    oznaczać. Błąd wysyłki logujemy i idziemy dalej: analiza jest wykonana,
    a nieustawiony status to utrata informacji, nie utrata wyniku.
    """
    if not commit_sha:
        return

    from app.core.encryption import decrypt_token
    from app.models.integration import ScmProvider
    from app.services.integrations import github_service, gitlab_service

    try:
        access_token = decrypt_token(integration.access_token_encrypted, tenant_id)
        target_url = _target_url(project_id)

        if integration.provider == ScmProvider.GITLAB:
            config = integration.config or {}
            gl_project_id = config.get("gitlab_project_id")
            if not gl_project_id:
                return
            await gitlab_service.send_commit_status(
                access_token,
                config.get("gitlab_url") or gitlab_service.default_gitlab_url(),
                int(gl_project_id),
                commit_sha,
                state,
                description,
                target_url,
            )
        else:
            await github_service.send_commit_status(
                access_token,
                integration.repo_full_name,
                commit_sha,
                state,
                description,
                target_url,
            )
    except Exception as exc:  # status to informacja, nie warunek poprawności
        logger.warning(
            "Nie udało się ustawić statusu %s dla %s: %s",
            state,
            integration.repo_full_name,
            exc,
        )


async def _post_change_comment(
    integration,
    tenant_id,
    change_number: int,
    body: str,
) -> None:
    """Dodaje komentarz do PR/MR (AC5); błąd nie przerywa domykania zdarzenia."""
    from app.core.encryption import decrypt_token
    from app.models.integration import ScmProvider
    from app.services.integrations import github_service, gitlab_service

    try:
        access_token = decrypt_token(integration.access_token_encrypted, tenant_id)
        if integration.provider == ScmProvider.GITLAB:
            config = integration.config or {}
            gl_project_id = config.get("gitlab_project_id")
            if not gl_project_id:
                return
            await gitlab_service.create_mr_note(
                access_token,
                config.get("gitlab_url") or gitlab_service.default_gitlab_url(),
                int(gl_project_id),
                change_number,
                body,
            )
        else:
            await github_service.create_pr_comment(
                access_token, integration.repo_full_name, change_number, body
            )
    except Exception as exc:
        logger.warning("Nie udało się dodać komentarza do #%s: %s", change_number, exc)


async def _collect_outcome(session, tenant_id, project_id, pipeline_status: str):
    """Znaleziska projektu — ta sama funkcja, z której korzysta bramka CI/CD.

    Wspólne źródło jest celowe: werdykt na PR i w pipelinie musi być ten sam
    (Story 8.4).
    """
    from app.services.integrations.findings_query import collect_project_outcome

    return await collect_project_outcome(session, tenant_id, project_id, pipeline_status)


async def _finalize_impl(event_id: str, pipeline_status: str) -> dict:
    """Domyka zdarzenie: status końcowy, komentarz, stan w bazie (AC1-AC5)."""
    from app.core.constants import NIL_UUID
    from app.core.database import task_session
    from app.models.integration import (
        IntegrationEvent,
        ScmEventStatus,
        ScmEventType,
        ScmIntegration,
    )
    from app.services.integrations.status_check_builder import (
        build_pr_comment,
        build_status_description,
    )

    eid = uuid.UUID(event_id)

    async with task_session() as session:
        await _set_tenant(session, NIL_UUID)
        event = await session.get(IntegrationEvent, eid)
        if event is None:
            logger.warning("Domykam nieistniejące zdarzenie %s — pomijam", event_id)
            return {"status": "missing"}

        integration = await session.get(ScmIntegration, event.integration_id)
        if integration is None:
            return {"status": "missing_integration"}

        tid = integration.tenant_id
        await _set_tenant(session, tid)

        project_id = integration.project_id
        outcome = (
            await _collect_outcome(session, tid, project_id, pipeline_status)
            if project_id
            else None
        )

        settings = _status_config(integration)
        if outcome is None:
            state, description = "failure", "Analiza TestGEN nie powiodła się"
        else:
            state, description = build_status_description(
                outcome,
                settings["severity_threshold"],
                fail_on_threshold=settings["fail_on_threshold"],
            )

        await _send_status(integration, tid, event.commit_sha, project_id, state, description)

        # Komentarz tylko przy zmianach (PR/MR) — pod pushem nie ma gdzie go
        # powiesić, a i tak powtarzałby treść status checka.
        is_change = event.event_type in (ScmEventType.PULL_REQUEST, ScmEventType.MERGE_REQUEST)
        if outcome is not None and is_change and event.pr_number and settings["post_comment"]:
            body = build_pr_comment(
                outcome,
                _target_url(project_id),
                threshold=settings["severity_threshold"],
            )
            await _post_change_comment(integration, tid, event.pr_number, body)

        event.status = (
            ScmEventStatus.FAILED if pipeline_status == "failed" else ScmEventStatus.COMPLETED
        )
        if pipeline_status == "failed" and not event.error_message:
            event.error_message = "Analiza nie powiodła się"
        event.completed_at = datetime.now(UTC)
        await session.commit()

        return {
            "status": event.status.value,
            "state": state,
            "description": description,
            "findings": outcome.total if outcome else 0,
        }


@celery_app.task(
    name="integrations.finalize_webhook_status",
    queue="analysis",
    ignore_result=True,
)
def finalize_webhook_status(pipeline_result, event_id: str) -> dict:
    """Callback sukcesu pipeline'u — wysyła status końcowy i komentarz.

    Pierwszy argument wstrzykuje Celery (wynik zadania nadrzędnego); używamy
    go tylko po to, żeby odróżnić ukończenie pełne od częściowego.
    """
    pipeline_status = "completed"
    if isinstance(pipeline_result, dict):
        pipeline_status = pipeline_result.get("status") or "completed"
    return asyncio.run(_finalize_impl(event_id, pipeline_status))


@celery_app.task(
    name="integrations.fail_webhook_status",
    queue="analysis",
    ignore_result=True,
)
def fail_webhook_status(request, event_id: str = "", *args) -> dict:
    """Callback błędu pipeline'u — oznacza status jako nieudany (AC1).

    Celery woła ``link_error`` z różną liczbą argumentów zależnie od wersji
    i od tego, czy zadanie jest związane; przyjmujemy je luźno, bo istotny
    jest wyłącznie identyfikator zdarzenia.
    """
    if not event_id:
        logger.warning("Callback błędu bez identyfikatora zdarzenia — pomijam")
        return {"status": "missing"}
    logger.warning("Pipeline zdarzenia %s zakończony błędem: %s", event_id, request)
    return asyncio.run(_finalize_impl(event_id, "failed"))
