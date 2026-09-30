"""Przyjmowanie zdarzeń z webhooków SCM — Epic 8, Story 8.1 (AC3, AC4).

Rozdzielone na dwie warstwy, bo mają różne wymagania czasowe:

1. **parsowanie** (tu) — czysta funkcja na payloadzie, bez I/O. Musi być
   szybka: GitHub uznaje webhook za nieudany po 10 s, więc endpoint tylko
   zapisuje zdarzenie i oddaje sterowanie.
2. **przetwarzanie** (``workers/tasks/integration_tasks.py``) — klonowanie
   i analiza, minuty pracy, w Celery.

Parser jest wspólny dla GitHuba i GitLaba (Story 8.2): oba dostawcy niosą te
same fakty, różnią się tylko nazwami pól.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.integration import (
    IntegrationEvent,
    ScmEventStatus,
    ScmEventType,
    ScmIntegration,
    ScmProvider,
)

logger = logging.getLogger(__name__)

# Akcje pull requesta, które uzasadniają ponowną analizę (8.1 AC4). GitHub nie
# pozwala zawęzić subskrypcji webhooka do wybranych akcji, więc filtrujemy tu.
PR_ACTIONS = frozenset({"opened", "synchronize", "reopened"})
# Odpowiedniki po stronie GitLaba (8.2 AC4) — inne nazwy, ta sama intencja:
# MR powstał albo dostał nowe commity.
MR_ACTIONS = frozenset({"open", "update", "reopen"})


@dataclass
class ParsedScmEvent:
    """Fakty wyłuskane z payloadu — wspólny kształt dla obu dostawców."""

    event_type: ScmEventType
    repo_full_name: str
    action: str | None = None
    branch: str | None = None
    base_branch: str | None = None
    commit_sha: str | None = None
    pr_number: int | None = None
    # Powód pominięcia; ustawiony ⇒ zdarzenie zapisujemy jako ``skipped``
    # i nie uruchamiamy analizy. Zapisujemy je mimo to, żeby w UI było
    # widać, że webhook dotarł (AC6).
    skip_reason: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)


def _branch_from_ref(ref: str | None) -> str | None:
    """``refs/heads/main`` → ``main``; tagi i inne refy zwracamy bez zmian."""
    if not ref:
        return None
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else ref


def parse_github_event(event_name: str, payload: dict[str, Any]) -> ParsedScmEvent | None:
    """Zamienia payload GitHuba na ``ParsedScmEvent``.

    ``None`` oznacza zdarzenie, którego w ogóle nie zapisujemy (np. ``ping``
    przy rejestracji webhooka) — w odróżnieniu od ``skip_reason``, które
    zapisuje ślad, ale nie uruchamia analizy.
    """
    repo = payload.get("repository") or {}
    repo_full_name = repo.get("full_name")
    if not repo_full_name:
        return None

    if event_name == "push":
        branch = _branch_from_ref(payload.get("ref"))
        analyzed = set(get_settings().scm_analyzed_branches)
        skip: str | None = None
        if branch not in analyzed:
            skip = f"Push na gałąź '{branch}' — analizujemy tylko: {', '.join(sorted(analyzed))}"
        elif payload.get("deleted"):
            skip = "Gałąź została usunięta"
        elif payload.get("after", "").strip("0") == "":
            skip = "Push bez commitów (usunięcie refa)"
        return ParsedScmEvent(
            event_type=ScmEventType.PUSH,
            repo_full_name=repo_full_name,
            branch=branch,
            commit_sha=payload.get("after"),
            skip_reason=skip,
            summary={
                "pusher": (payload.get("pusher") or {}).get("name"),
                "commits": len(payload.get("commits") or []),
                "ref": payload.get("ref"),
            },
        )

    if event_name == "pull_request":
        action = payload.get("action")
        pr = payload.get("pull_request") or {}
        head = pr.get("head") or {}
        base = pr.get("base") or {}
        return ParsedScmEvent(
            event_type=ScmEventType.PULL_REQUEST,
            repo_full_name=repo_full_name,
            action=action,
            branch=head.get("ref"),
            base_branch=base.get("ref"),
            commit_sha=head.get("sha"),
            pr_number=payload.get("number") or pr.get("number"),
            skip_reason=None if action in PR_ACTIONS else f"Akcja pull requesta '{action}' nie wymaga analizy",
            summary={
                "title": pr.get("title"),
                "author": (pr.get("user") or {}).get("login"),
                "html_url": pr.get("html_url"),
            },
        )

    # ping, release, issues… — webhook dotarł, ale nie jest dla nas.
    return None


def parse_gitlab_event(event_name: str, payload: dict[str, Any]) -> ParsedScmEvent | None:
    """Zamienia payload GitLaba na ten sam ``ParsedScmEvent`` co GitHub (8.2 AC3/AC4).

    GitLab niesie rodzaj zdarzenia zarówno w nagłówku ``X-Gitlab-Event``
    („Push Hook"), jak i w polu ``object_kind`` — czytamy to drugie, bo jest
    stabilniejsze i identyczne dla wszystkich wersji instancji.
    """
    project = payload.get("project") or {}
    repo_full_name = project.get("path_with_namespace")
    if not repo_full_name:
        return None

    kind = payload.get("object_kind") or event_name

    if kind == "push":
        branch = _branch_from_ref(payload.get("ref"))
        analyzed = set(get_settings().scm_analyzed_branches)
        after = payload.get("after") or ""
        skip: str | None = None
        if branch not in analyzed:
            skip = f"Push na gałąź '{branch}' — analizujemy tylko: {', '.join(sorted(analyzed))}"
        elif after.strip("0") == "":
            # GitLab sygnalizuje usunięcie gałęzi samymi zerami w ``after``.
            skip = "Gałąź została usunięta"
        return ParsedScmEvent(
            event_type=ScmEventType.PUSH,
            repo_full_name=repo_full_name,
            branch=branch,
            commit_sha=after or None,
            skip_reason=skip,
            summary={
                "pusher": payload.get("user_name") or payload.get("user_username"),
                "commits": payload.get("total_commits_count") or len(payload.get("commits") or []),
                "ref": payload.get("ref"),
            },
        )

    if kind == "merge_request":
        attrs = payload.get("object_attributes") or {}
        action = attrs.get("action")
        last_commit = attrs.get("last_commit") or {}
        return ParsedScmEvent(
            event_type=ScmEventType.MERGE_REQUEST,
            repo_full_name=repo_full_name,
            action=action,
            branch=attrs.get("source_branch"),
            base_branch=attrs.get("target_branch"),
            commit_sha=last_commit.get("id"),
            # ``iid`` to numer widoczny w UI (!42); ``id`` jest globalny i bezużyteczny w API MR.
            pr_number=attrs.get("iid"),
            skip_reason=None
            if action in MR_ACTIONS
            else f"Akcja merge requesta '{action}' nie wymaga analizy",
            summary={
                "title": attrs.get("title"),
                "author": (payload.get("user") or {}).get("username"),
                "url": attrs.get("url"),
            },
        )

    # note, pipeline, issue… — webhook dotarł, ale nie jest dla nas.
    return None


async def find_integration(
    db: AsyncSession,
    provider: ScmProvider,
    repo_full_name: str,
) -> ScmIntegration | None:
    """Znajduje aktywną integrację dla repozytorium.

    Wywoływane przed ustaleniem tenanta (webhook przychodzi anonimowo), więc
    zapytanie musi widzieć wiersze wszystkich tenantów — wywołujący ustawia
    wcześniej kontekst NIL, tak jak przy uwierzytelnianiu kluczem API.
    """
    result = await db.execute(
        select(ScmIntegration).where(
            ScmIntegration.provider == provider,
            ScmIntegration.repo_full_name == repo_full_name,
            ScmIntegration.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def record_event(
    db: AsyncSession,
    integration: ScmIntegration,
    parsed: ParsedScmEvent,
) -> IntegrationEvent:
    """Zapisuje zdarzenie ze statusem wynikającym z ``skip_reason``."""
    event = IntegrationEvent(
        tenant_id=integration.tenant_id,
        integration_id=integration.id,
        event_type=parsed.event_type,
        action=parsed.action,
        repo_full_name=parsed.repo_full_name,
        branch=parsed.branch,
        base_branch=parsed.base_branch,
        commit_sha=parsed.commit_sha,
        pr_number=parsed.pr_number,
        status=ScmEventStatus.SKIPPED if parsed.skip_reason else ScmEventStatus.PENDING,
        error_message=parsed.skip_reason,
        payload=parsed.summary or None,
    )
    db.add(event)
    await db.flush()
    return event


def dispatch_event_analysis(event_id: uuid.UUID) -> str | None:
    """Kolejkuje analizę zdarzenia; zwraca id zadania Celery.

    Import wewnątrz funkcji rozcina cykl ``workers → services → workers``
    i pozwala testom podmienić task bez ładowania brokera.
    """
    from app.workers.tasks.integration_tasks import run_webhook_analysis

    task = run_webhook_analysis.delay(str(event_id))
    return task.id
