"""Testy domykania status checków — Story 8.3 (AC1-AC5; Task 7.4).

Wynik analizy znamy dopiero po pipelinie, więc status końcowy leci
z callbacku Celery. Te testy pilnują dwóch rzeczy, na których łatwo się
przewrócić: że callback jest w ogóle podpięty do dispatchu i że nieudana
wysyłka statusu nie unieważnia wykonanej analizy.

Wzorzec mockowania sesji: test_check_thresholds_task.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.elements import TextClause

from app.models.integration import (
    IntegrationEvent,
    ScmEventStatus,
    ScmEventType,
    ScmIntegration,
    ScmProvider,
)
from app.services.integrations.status_check_builder import STATUS_CONTEXT

REPO = "acme/app"
SHA = "a" * 40


def _session_ctx(session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _integration(provider=ScmProvider.GITHUB, **overrides) -> ScmIntegration:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "provider": provider,
        "repo_full_name": REPO,
        "repo_url": f"https://github.com/{REPO}.git",
        "default_branch": "main",
        "access_token_encrypted": "enc",
        "is_active": True,
        "config": {},
    }
    defaults.update(overrides)
    return ScmIntegration(**defaults)


def _event(integration, **overrides) -> IntegrationEvent:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": integration.tenant_id,
        "integration_id": integration.id,
        "event_type": ScmEventType.PULL_REQUEST,
        "action": "opened",
        "repo_full_name": REPO,
        "branch": "feature/x",
        "base_branch": "main",
        "commit_sha": SHA,
        "pr_number": 7,
        "status": ScmEventStatus.PROCESSING,
    }
    defaults.update(overrides)
    return IntegrationEvent(**defaults)


def _session(event, integration, security_rows=(), code_error_rows=()) -> AsyncMock:
    """Sesja oddająca kolejno: zdarzenie, integrację i wiersze znalezisk."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())

    async def _get(model, _id):
        if model is IntegrationEvent:
            return event
        if model is ScmIntegration:
            return integration
        return None

    session.get = AsyncMock(side_effect=_get)

    rows = [list(security_rows), list(code_error_rows)]

    async def _execute(statement, *args, **kwargs):
        result = MagicMock()
        # ``SET LOCAL`` (kontekst RLS) idzie tym samym kanałem co SELECT-y,
        # więc rozróżniamy je po typie — inaczej zjadłoby wiersze znalezisk.
        if isinstance(statement, TextClause):
            return result
        result.scalars.return_value.all.return_value = rows.pop(0) if rows else []
        return result

    session.execute = AsyncMock(side_effect=_execute)
    return session


class _Row:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


async def _finalize(event, integration, *, pipeline_status="completed", **rows):
    from app.workers.tasks import integration_tasks

    session = _session(event, integration, **rows)
    with patch("app.core.database.task_session", return_value=_session_ctx(session)):
        result = await integration_tasks._finalize_impl(str(event.id), pipeline_status)
    return result, session


# ── status końcowy (AC1/AC2/AC3) ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_brak_znalezisk_konczy_zdarzenie_sukcesem():
    integration = _integration()
    event = _event(integration)

    with patch(
        "app.workers.tasks.integration_tasks._send_status", AsyncMock()
    ) as send, patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ):
        result, session = await _finalize(event, integration)

    assert result["state"] == "success"
    assert event.status == ScmEventStatus.COMPLETED
    assert event.completed_at is not None
    assert send.await_args.args[4] == "success"
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_krytyczne_znalezisko_blokuje_merge():
    integration = _integration()
    event = _event(integration)
    findings = [_Row(severity="critical", vulnerability_type="SQLi", file_path="db.py", line_start=1)]

    with patch(
        "app.workers.tasks.integration_tasks._send_status", AsyncMock()
    ) as send, patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ):
        result, _ = await _finalize(event, integration, security_rows=findings)

    assert result["state"] == "failure"
    assert "krytyczny" in result["description"]
    assert send.await_args.args[4] == "failure"
    # Zdarzenie jest ukończone — to analiza się udała, blokada dotyczy merge'a
    assert event.status == ScmEventStatus.COMPLETED


@pytest.mark.asyncio
async def test_prog_z_konfiguracji_integracji_jest_respektowany():
    integration = _integration(config={"severity_threshold": "high"})
    event = _event(integration)
    findings = [_Row(severity="high", vulnerability_type="XSS", file_path="v.py", line_start=2)]

    with patch("app.workers.tasks.integration_tasks._send_status", AsyncMock()), patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ):
        result, _ = await _finalize(event, integration, security_rows=findings)

    assert result["state"] == "failure"


@pytest.mark.asyncio
async def test_fail_on_threshold_false_nie_blokuje():
    integration = _integration(config={"fail_on_threshold": False})
    event = _event(integration)
    findings = [_Row(severity="critical", vulnerability_type="SQLi", file_path="db.py", line_start=1)]

    with patch("app.workers.tasks.integration_tasks._send_status", AsyncMock()), patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ):
        result, _ = await _finalize(event, integration, security_rows=findings)

    assert result["state"] == "success"


@pytest.mark.asyncio
async def test_nieudany_pipeline_oznacza_zdarzenie_jako_bledne():
    integration = _integration()
    event = _event(integration)

    with patch(
        "app.workers.tasks.integration_tasks._send_status", AsyncMock()
    ) as send, patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ):
        result, _ = await _finalize(event, integration, pipeline_status="failed")

    assert result["state"] == "failure"
    assert event.status == ScmEventStatus.FAILED
    assert event.error_message == "Analiza nie powiodła się"
    assert send.await_args.args[4] == "failure"


# ── komentarz na PR/MR (AC5) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_komentarz_dodawany_dla_pull_requesta():
    integration = _integration()
    event = _event(integration)

    with patch("app.workers.tasks.integration_tasks._send_status", AsyncMock()), patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ) as comment:
        await _finalize(event, integration)

    comment.assert_awaited_once()
    body = comment.await_args.args[3]
    assert body.startswith("## Analiza TestGEN")


@pytest.mark.asyncio
async def test_pod_pushem_nie_ma_komentarza():
    """Push nie ma gdzie powiesić komentarza — status check wystarczy."""
    integration = _integration()
    event = _event(integration, event_type=ScmEventType.PUSH, pr_number=None, action=None)

    with patch("app.workers.tasks.integration_tasks._send_status", AsyncMock()) as send, patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ) as comment:
        await _finalize(event, integration)

    comment.assert_not_awaited()
    send.assert_awaited_once()  # status commita nadal leci


@pytest.mark.asyncio
async def test_wylaczony_komentarz_w_konfiguracji_jest_respektowany():
    integration = _integration(config={"post_comment": False})
    event = _event(integration)

    with patch("app.workers.tasks.integration_tasks._send_status", AsyncMock()), patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ) as comment:
        await _finalize(event, integration)

    comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_merge_request_gitlaba_tez_dostaje_komentarz():
    integration = _integration(
        ScmProvider.GITLAB, config={"gitlab_url": "https://git.firma.pl", "gitlab_project_id": 7}
    )
    event = _event(integration, event_type=ScmEventType.MERGE_REQUEST, action="update", pr_number=42)

    with patch("app.workers.tasks.integration_tasks._send_status", AsyncMock()), patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ) as comment:
        await _finalize(event, integration)

    assert comment.await_args.args[2] == 42


# ── odporność ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nieistniejace_zdarzenie_nie_wywraca_callbacku():
    from app.workers.tasks import integration_tasks

    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.execute = AsyncMock(return_value=MagicMock())

    with patch("app.core.database.task_session", return_value=_session_ctx(session)):
        result = await integration_tasks._finalize_impl(str(uuid.uuid4()), "completed")

    assert result == {"status": "missing"}


@pytest.mark.asyncio
async def test_blad_wysylki_statusu_nie_uniewaznia_analizy():
    """Status to informacja; jej utrata nie może cofnąć wykonanej pracy."""
    integration = _integration()
    event = _event(integration)

    with patch(
        "app.services.integrations.github_service.send_commit_status",
        AsyncMock(side_effect=RuntimeError("GitHub padł")),
    ), patch(
        "app.core.encryption.decrypt_token", return_value="gho_abc"
    ), patch(
        "app.workers.tasks.integration_tasks._post_change_comment", AsyncMock()
    ):
        result, _ = await _finalize(event, integration)

    assert result["status"] == "completed"
    assert event.status == ScmEventStatus.COMPLETED


@pytest.mark.asyncio
async def test_brak_sha_pomija_wysylke_statusu():
    from app.workers.tasks import integration_tasks

    integration = _integration()
    send = AsyncMock()

    with patch("app.services.integrations.github_service.send_commit_status", send):
        await integration_tasks._send_status(
            integration, integration.tenant_id, None, integration.project_id, "success", "ok"
        )

    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_status_gitlaba_bez_id_projektu_jest_pomijany():
    """Bez ``gitlab_project_id`` nie ma jak zaadresować API — lepiej nic nie robić."""
    from app.workers.tasks import integration_tasks

    integration = _integration(ScmProvider.GITLAB, config={"gitlab_url": "https://git.firma.pl"})
    send = AsyncMock()

    with patch("app.services.integrations.gitlab_service.send_commit_status", send), patch(
        "app.core.encryption.decrypt_token", return_value="glpat"
    ):
        await integration_tasks._send_status(
            integration, integration.tenant_id, SHA, integration.project_id, "success", "ok"
        )

    send.assert_not_awaited()


# ── konfiguracja i spięcie z Celery ─────────────────────────────────────────


def test_domyslna_konfiguracja_status_checka():
    from app.workers.tasks.integration_tasks import _status_config

    config = _status_config(_integration())

    assert config == {
        "severity_threshold": "critical",
        "post_comment": True,
        "fail_on_threshold": True,
    }


def test_niepoprawny_prog_w_konfiguracji_spada_na_domyslny():
    from app.workers.tasks.integration_tasks import _status_config

    config = _status_config(_integration(config={"severity_threshold": "low"}))

    assert config["severity_threshold"] == "critical"


def test_link_do_wynikow_wskazuje_na_projekt():
    from app.workers.tasks.integration_tasks import _target_url

    project_id = uuid.uuid4()

    assert _target_url(project_id).endswith(f"/projects/{project_id}/results")


def test_callbacki_zarejestrowane_w_celery():
    from app.workers.celery_app import celery_app

    routes = celery_app.conf.task_routes
    assert routes["integrations.finalize_webhook_status"] == {"queue": "analysis"}
    assert routes["integrations.fail_webhook_status"] == {"queue": "analysis"}


def test_callback_bledu_bez_identyfikatora_nie_wywraca_workera():
    from app.workers.tasks.integration_tasks import fail_webhook_status

    assert fail_webhook_status("task-id", "") == {"status": "missing"}


def test_nazwa_kontekstu_wspoldzielona_z_builderem():
    from app.services.integrations import github_service, gitlab_service

    assert github_service.STATUS_CONTEXT == STATUS_CONTEXT
    assert gitlab_service.STATUS_CONTEXT == STATUS_CONTEXT
