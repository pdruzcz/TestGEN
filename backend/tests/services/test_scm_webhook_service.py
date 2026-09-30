"""Testy parsowania zdarzeń SCM — Story 8.1 (AC3, AC4; Task 7.1).

Parser jest czystą funkcją nad payloadem, więc testy nie potrzebują ani DB,
ani sieci. Payloady odwzorowują kształt zdarzeń GitHuba (tylko pola, których
faktycznie używamy).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.integration import (
    IntegrationEvent,
    ScmEventStatus,
    ScmEventType,
    ScmIntegration,
    ScmProvider,
)
from app.services.integrations.scm_webhook_service import (
    parse_github_event,
    record_event,
)

REPO = "acme/app"


def _push(ref: str = "refs/heads/main", **overrides) -> dict:
    payload = {
        "ref": ref,
        "after": "a" * 40,
        "deleted": False,
        "repository": {"full_name": REPO, "default_branch": "main"},
        "pusher": {"name": "tomek"},
        "commits": [{"id": "a" * 40}, {"id": "b" * 40}],
    }
    payload.update(overrides)
    return payload


def _pull_request(action: str = "opened", **overrides) -> dict:
    payload = {
        "action": action,
        "number": 7,
        "repository": {"full_name": REPO, "default_branch": "main"},
        "pull_request": {
            "title": "Dodaj walidację",
            "user": {"login": "tomek"},
            "html_url": f"https://github.com/{REPO}/pull/7",
            "head": {"ref": "feature/walidacja", "sha": "c" * 40},
            "base": {"ref": "main"},
        },
    }
    payload.update(overrides)
    return payload


# --- push (AC3) ---


def test_push_na_main_uruchamia_analize():
    parsed = parse_github_event("push", _push())

    assert parsed.event_type == ScmEventType.PUSH
    assert parsed.repo_full_name == REPO
    assert parsed.branch == "main"
    assert parsed.commit_sha == "a" * 40
    assert parsed.skip_reason is None
    assert parsed.summary["commits"] == 2
    assert parsed.summary["pusher"] == "tomek"


def test_push_na_master_tez_uruchamia_analize():
    parsed = parse_github_event("push", _push(ref="refs/heads/master"))
    assert parsed.branch == "master"
    assert parsed.skip_reason is None


def test_push_na_galaz_funkcyjna_jest_pomijany():
    """Analiza każdej gałęzi zalałaby kolejkę — AC3 mówi o main/master."""
    parsed = parse_github_event("push", _push(ref="refs/heads/feature/x"))

    assert parsed.branch == "feature/x"
    assert parsed.skip_reason is not None
    assert "feature/x" in parsed.skip_reason


def test_push_usuwajacy_galaz_jest_pomijany():
    parsed = parse_github_event("push", _push(deleted=True))
    assert parsed.skip_reason == "Gałąź została usunięta"


def test_push_z_zerowym_sha_jest_pomijany():
    parsed = parse_github_event("push", _push(after="0" * 40))
    assert parsed.skip_reason is not None


def test_push_tagu_jest_pomijany():
    parsed = parse_github_event("push", _push(ref="refs/tags/v1.0.0"))
    assert parsed.skip_reason is not None


# --- pull request (AC4) ---


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened"])
def test_pull_request_analizowany_dla_trzech_akcji(action):
    parsed = parse_github_event("pull_request", _pull_request(action))

    assert parsed.event_type == ScmEventType.PULL_REQUEST
    assert parsed.action == action
    assert parsed.skip_reason is None
    assert parsed.branch == "feature/walidacja"
    assert parsed.base_branch == "main"
    assert parsed.pr_number == 7
    assert parsed.commit_sha == "c" * 40


@pytest.mark.parametrize("action", ["closed", "labeled", "assigned", "edited"])
def test_pozostale_akcje_pull_requesta_pomijane(action):
    parsed = parse_github_event("pull_request", _pull_request(action))

    assert parsed.skip_reason is not None
    assert action in parsed.skip_reason


def test_pull_request_numer_z_zagniezdzonego_obiektu():
    """Niektóre dostawy niosą numer tylko w ``pull_request.number``."""
    payload = _pull_request()
    del payload["number"]
    payload["pull_request"]["number"] = 99

    assert parse_github_event("pull_request", payload).pr_number == 99


# --- zdarzenia spoza zakresu ---


@pytest.mark.parametrize("event_name", ["ping", "release", "issues", "star", ""])
def test_nieobslugiwane_zdarzenia_daja_none(event_name):
    parsed = parse_github_event(event_name, _push())
    assert parsed is None


def test_payload_bez_repozytorium_daje_none():
    assert parse_github_event("push", {"ref": "refs/heads/main"}) is None


# --- zapis zdarzenia ---


def _integration() -> ScmIntegration:
    return ScmIntegration(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        provider=ScmProvider.GITHUB,
        repo_full_name=REPO,
        repo_url=f"https://github.com/{REPO}.git",
        access_token_encrypted="enc",
    )


@pytest.mark.asyncio
async def test_record_event_zapisuje_pending_dla_analizowanego_zdarzenia():
    db = AsyncMock()
    db.add = MagicMock()
    integration = _integration()
    parsed = parse_github_event("push", _push())

    event = await record_event(db, integration, parsed)

    assert isinstance(event, IntegrationEvent)
    assert event.status == ScmEventStatus.PENDING
    assert event.tenant_id == integration.tenant_id
    assert event.integration_id == integration.id
    assert event.branch == "main"
    assert event.error_message is None
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_record_event_zapisuje_skipped_z_powodem():
    """Pominięte zdarzenie też zostawia ślad — w UI widać, że webhook dotarł."""
    db = AsyncMock()
    db.add = MagicMock()
    parsed = parse_github_event("push", _push(ref="refs/heads/dev"))

    event = await record_event(db, _integration(), parsed)

    assert event.status == ScmEventStatus.SKIPPED
    assert event.error_message == parsed.skip_reason


# ── GitLab (Story 8.2, AC3/AC4) ─────────────────────────────────────────────

from app.services.integrations.scm_webhook_service import parse_gitlab_event  # noqa: E402

GL_REPO = "grupa/app"


def _gl_push(ref: str = "refs/heads/main", **overrides) -> dict:
    payload = {
        "object_kind": "push",
        "ref": ref,
        "after": "d" * 40,
        "before": "c" * 40,
        "user_name": "Tomek",
        "user_username": "tomek",
        "total_commits_count": 3,
        "project": {"path_with_namespace": GL_REPO, "default_branch": "main"},
    }
    payload.update(overrides)
    return payload


def _gl_merge_request(action: str = "open", **attrs) -> dict:
    object_attributes = {
        "action": action,
        "iid": 42,
        "id": 900123,
        "title": "Dodaj walidację",
        "source_branch": "feature/walidacja",
        "target_branch": "main",
        "last_commit": {"id": "e" * 40},
        "url": f"https://gitlab.com/{GL_REPO}/-/merge_requests/42",
    }
    object_attributes.update(attrs)
    return {
        "object_kind": "merge_request",
        "user": {"username": "tomek"},
        "project": {"path_with_namespace": GL_REPO, "default_branch": "main"},
        "object_attributes": object_attributes,
    }


def test_gitlab_push_na_main_uruchamia_analize():
    parsed = parse_gitlab_event("Push Hook", _gl_push())

    assert parsed.event_type == ScmEventType.PUSH
    assert parsed.repo_full_name == GL_REPO
    assert parsed.branch == "main"
    assert parsed.commit_sha == "d" * 40
    assert parsed.skip_reason is None
    assert parsed.summary["commits"] == 3
    assert parsed.summary["pusher"] == "Tomek"


def test_gitlab_push_na_galaz_funkcyjna_pomijany():
    parsed = parse_gitlab_event("Push Hook", _gl_push(ref="refs/heads/dev"))
    assert parsed.skip_reason is not None
    assert "dev" in parsed.skip_reason


def test_gitlab_usuniecie_galezi_pomijane():
    """GitLab sygnalizuje usunięcie samymi zerami w ``after``."""
    parsed = parse_gitlab_event("Push Hook", _gl_push(after="0" * 40))
    assert parsed.skip_reason == "Gałąź została usunięta"


@pytest.mark.parametrize("action", ["open", "update", "reopen"])
def test_gitlab_merge_request_analizowany_dla_trzech_akcji(action):
    parsed = parse_gitlab_event("Merge Request Hook", _gl_merge_request(action))

    assert parsed.event_type == ScmEventType.MERGE_REQUEST
    assert parsed.action == action
    assert parsed.skip_reason is None
    assert parsed.branch == "feature/walidacja"
    assert parsed.base_branch == "main"
    assert parsed.commit_sha == "e" * 40


@pytest.mark.parametrize("action", ["close", "merge", "approved", "unapproved"])
def test_gitlab_pozostale_akcje_mr_pomijane(action):
    parsed = parse_gitlab_event("Merge Request Hook", _gl_merge_request(action))
    assert parsed.skip_reason is not None
    assert action in parsed.skip_reason


def test_gitlab_merge_request_uzywa_iid_a_nie_globalnego_id():
    """``iid`` to numer z UI (!42); ``id`` jest globalny i bezużyteczny w API MR."""
    parsed = parse_gitlab_event("Merge Request Hook", _gl_merge_request())
    assert parsed.pr_number == 42


@pytest.mark.parametrize("kind", ["note", "pipeline", "issue", "tag_push"])
def test_gitlab_nieobslugiwane_zdarzenia_daja_none(kind):
    payload = _gl_push()
    payload["object_kind"] = kind
    assert parse_gitlab_event("Other Hook", payload) is None


def test_gitlab_payload_bez_projektu_daje_none():
    assert parse_gitlab_event("Push Hook", {"object_kind": "push"}) is None


def test_gitlab_rodzaj_zdarzenia_z_naglowka_gdy_brak_object_kind():
    """Starsze instancje potrafią nie wysłać ``object_kind``."""
    payload = _gl_push()
    del payload["object_kind"]
    assert parse_gitlab_event("push", payload).event_type == ScmEventType.PUSH


@pytest.mark.asyncio
async def test_record_event_dziala_tak_samo_dla_gitlaba():
    db = AsyncMock()
    db.add = MagicMock()
    integration = _integration()
    integration.provider = ScmProvider.GITLAB
    parsed = parse_gitlab_event("Merge Request Hook", _gl_merge_request())

    event = await record_event(db, integration, parsed)

    assert event.event_type == ScmEventType.MERGE_REQUEST
    assert event.pr_number == 42
    assert event.status == ScmEventStatus.PENDING
