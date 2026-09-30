"""API testy integracji GitHub — Story 8.1 (AC1, AC2, AC5, AC6; Task 7.3).

DB i Redis mockowane, ``github_service`` patchowany (wzorzec test_api_keys).
Webhook testujemy z realnym podpisem HMAC — to jedyna brama tego endpointu,
więc test liczy się tylko wtedy, gdy liczy podpis naprawdę.
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.integration import (
    IntegrationEvent,
    ScmEventStatus,
    ScmEventType,
    ScmIntegration,
    ScmProvider,
)
from tests.factories import make_user

REPO = "acme/app"
SECRET = "w3bh00k-s3cret"
BASE = "/api/v1/integrations/github"


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _db() -> AsyncMock:
    db = AsyncMock()

    def _add(obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)

    db.add = MagicMock(side_effect=_add)
    return db


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    r.scalars.return_value.__iter__ = lambda self: iter(items)
    return r


def _execute_sequence(db: AsyncMock, *results) -> None:
    """Kolejne wyniki ``db.execute``; po wyczerpaniu — pusty wynik.

    ``_set_rls_tenant`` (SET LOCAL) też przechodzi przez ``execute``, więc
    sekwencja musi je uwzględniać; fallback chroni przed StopIteration, gdy
    handler zrobi o jedno zapytanie więcej niż test przewidział.
    """
    pending = list(results)

    def _next(*args, **kwargs):
        return pending.pop(0) if pending else _scalar(None)

    db.execute.side_effect = _next


def _redis(token: str | None = None) -> AsyncMock:
    redis = AsyncMock()
    redis.get.return_value = token
    redis.set.return_value = True
    redis.delete.return_value = 1
    return redis


def _override(app, db, redis, user=None) -> tuple[uuid.UUID, object]:
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db, get_redis

    user = user or make_user(email="owner@a.com", name="Owner")
    tenant_id = uuid.uuid4()
    user._tenant_id = tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = "owner"
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    async def override_redis():
        return redis

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    return tenant_id, user


def _integration(tenant_id, user_id, **overrides) -> ScmIntegration:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "user_id": user_id,
        "provider": ScmProvider.GITHUB,
        "repo_full_name": REPO,
        "repo_url": f"https://github.com/{REPO}.git",
        "default_branch": "main",
        "access_token_encrypted": "enc-token",
        "webhook_secret_encrypted": "enc-secret",
        "hook_id": "42",
        "is_active": True,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ScmIntegration(**defaults)


def _gh_repo(full_name: str = REPO, **overrides) -> dict:
    repo = {
        "full_name": full_name,
        "name": full_name.split("/")[-1],
        "private": True,
        "default_branch": "main",
        "html_url": f"https://github.com/{full_name}",
        "clone_url": f"https://github.com/{full_name}.git",
    }
    repo.update(overrides)
    return repo


# ── OAuth (AC1) ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authorize_zwraca_url_i_zapisuje_state(app, client):
    redis = _redis()
    _override(app, _db(), redis)

    with patch("app.api.routes.integrations_scm.github_service.is_configured", return_value=True), patch(
        "app.api.routes.integrations_scm.github_service.get_authorization_url",
        return_value="https://github.com/login/oauth/authorize?state=abc",
    ):
        resp = await client.get(f"{BASE}/authorize")

    assert resp.status_code == 200
    assert resp.json()["authorization_url"].startswith("https://github.com/login/oauth/authorize")
    # state trafia do Redisa z TTL — bez tego callback nie miałby czego zweryfikować
    assert redis.set.await_args.kwargs["ex"] == 600
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_authorize_bez_konfiguracji_zwraca_422(app, client):
    _override(app, _db(), _redis())

    with patch("app.api.routes.integrations_scm.github_service.is_configured", return_value=False):
        resp = await client.get(f"{BASE}/authorize")

    assert resp.status_code == 422
    assert "GITHUB_CLIENT_ID" in resp.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_callback_zapisuje_token_i_przekierowuje_na_frontend(app, client):
    user_id = uuid.uuid4()
    redis = _redis(token=json.dumps({"user_id": str(user_id), "tenant_id": str(uuid.uuid4())}))
    _override(app, _db(), redis)

    with patch(
        "app.api.routes.integrations_scm.github_service.exchange_code_for_token",
        AsyncMock(return_value={"access_token": "gho_abc"}),
    ):
        resp = await client.get(f"{BASE}/callback?code=kod&state=st", follow_redirects=False)

    assert resp.status_code == 302
    assert "/settings/integrations/github?connected=1" in resp.headers["location"]
    redis.delete.assert_awaited()  # state jednorazowy
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_callback_z_nieznanym_state_nie_wymienia_kodu(app, client):
    """Brak state w Redisie = próba CSRF albo wygasła sesja — nic nie robimy."""
    redis = _redis(token=None)
    _override(app, _db(), redis)

    exchange = AsyncMock()
    with patch("app.api.routes.integrations_scm.github_service.exchange_code_for_token", exchange):
        resp = await client.get(f"{BASE}/callback?code=kod&state=zly", follow_redirects=False)

    assert resp.status_code == 302
    assert "error=invalid_state" in resp.headers["location"]
    exchange.assert_not_awaited()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_callback_przy_bledzie_wymiany_wraca_z_komunikatem(app, client):
    redis = _redis(token=json.dumps({"user_id": str(uuid.uuid4()), "tenant_id": str(uuid.uuid4())}))
    _override(app, _db(), redis)

    with patch(
        "app.api.routes.integrations_scm.github_service.exchange_code_for_token",
        AsyncMock(side_effect=RuntimeError("kod wygasł")),
    ):
        resp = await client.get(f"{BASE}/callback?code=kod&state=st", follow_redirects=False)

    assert resp.status_code == 302
    assert "error=token_exchange" in resp.headers["location"]
    app.dependency_overrides.clear()


# ── podłączanie repozytorium (AC1/AC2) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_connect_repo_rejestruje_webhook_i_szyfruje_token(app, client):
    db = _db()
    _override(app, db, _redis(token="gho_abc"))
    _execute_sequence(db, _scalar(None), _scalar(None))  # SET LOCAL, brak istniejącej integracji

    register = AsyncMock(return_value={"id": 4242})
    with patch(
        "app.api.routes.integrations_scm.github_service.get_user_repos",
        AsyncMock(return_value=[_gh_repo()]),
    ), patch("app.api.routes.integrations_scm.github_service.register_webhook", register), patch(
        "app.api.routes.integrations_scm.log_action", AsyncMock()
    ):
        resp = await client.post(f"{BASE}/repos", json={"full_name": REPO})

    assert resp.status_code == 201
    body = resp.json()
    assert body["repo_full_name"] == REPO
    assert body["webhook_active"] is True
    assert body["default_branch"] == "main"
    # Token ani sekret webhooka nie wychodzą w odpowiedzi
    assert "access_token_encrypted" not in body
    assert "webhook_secret_encrypted" not in body

    # Sekret webhooka jest generowany po naszej stronie, nie brany z requestu
    sent_secret = register.await_args.args[3]
    assert len(sent_secret) == 64
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_connect_repo_juz_podlaczonego_to_409(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis(token="gho_abc"))
    _execute_sequence(db, _scalar(None), _scalar(_integration(tenant_id, user.id)))

    resp = await client.post(f"{BASE}/repos", json={"full_name": REPO})

    assert resp.status_code == 409
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_connect_repo_zajetego_przez_inna_firme_to_409_z_wyjasnieniem(app, client):
    """Unikalność (provider, repo) jest globalna — webhook nie ma kontekstu tenanta."""
    db = _db()
    _override(app, db, _redis(token="gho_abc"))
    _execute_sequence(db, _scalar(None), _scalar(_integration(uuid.uuid4(), uuid.uuid4())))

    resp = await client.post(f"{BASE}/repos", json={"full_name": REPO})

    assert resp.status_code == 409
    assert "innej firmy" in resp.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_connect_repo_niedostepnego_dla_tokenu_to_404(app, client):
    db = _db()
    _override(app, db, _redis(token="gho_abc"))
    _execute_sequence(db, _scalar(None), _scalar(None))

    with patch(
        "app.api.routes.integrations_scm.github_service.get_user_repos",
        AsyncMock(return_value=[_gh_repo("inna/firma")]),
    ):
        resp = await client.post(f"{BASE}/repos", json={"full_name": REPO})

    assert resp.status_code == 404
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_available_repos_oznacza_juz_podlaczone(app, client):
    db = _db()
    _override(app, db, _redis(token="gho_abc"))
    db.execute.return_value = _scalars([REPO])

    with patch(
        "app.api.routes.integrations_scm.github_service.get_user_repos",
        AsyncMock(return_value=[_gh_repo(), _gh_repo("acme/other")]),
    ):
        resp = await client.get(f"{BASE}/available-repos")

    assert resp.status_code == 200
    items = {r["full_name"]: r for r in resp.json()}
    assert items[REPO]["connected"] is True
    assert items["acme/other"]["connected"] is False
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_lista_podlaczonych_repozytoriow(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalars([_integration(tenant_id, user.id)])

    with patch("app.api.routes.integrations_scm.github_service.is_configured", return_value=True):
        resp = await client.get(f"{BASE}/repos")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["provider_configured"] is True
    assert body["items"][0]["repo_full_name"] == REPO
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_disconnect_kasuje_webhook_i_dezaktywuje(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    integration = _integration(tenant_id, user.id)
    db.execute.return_value = _scalar(integration)

    delete_hook = AsyncMock()
    with patch("app.api.routes.integrations_scm.decrypt_token", return_value="gho_abc"), patch(
        "app.api.routes.integrations_scm.github_service.delete_webhook", delete_hook
    ), patch("app.api.routes.integrations_scm.log_action", AsyncMock()):
        resp = await client.delete(f"{BASE}/repos/{integration.id}")

    assert resp.status_code == 204
    delete_hook.assert_awaited_once()
    assert integration.is_active is False
    assert integration.hook_id is None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_disconnect_dziala_mimo_bledu_po_stronie_github(app, client):
    """Wygasły token nie może zostawić martwej integracji na liście na zawsze."""
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    integration = _integration(tenant_id, user.id)
    db.execute.return_value = _scalar(integration)

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value="gho_abc"), patch(
        "app.api.routes.integrations_scm.github_service.delete_webhook",
        AsyncMock(side_effect=RuntimeError("401")),
    ), patch("app.api.routes.integrations_scm.log_action", AsyncMock()):
        resp = await client.delete(f"{BASE}/repos/{integration.id}")

    assert resp.status_code == 204
    assert integration.is_active is False
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_disconnect_nieznanej_integracji_to_404(app, client):
    db = _db()
    _override(app, db, _redis())
    db.execute.return_value = _scalar(None)

    resp = await client.delete(f"{BASE}/repos/{uuid.uuid4()}")

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# ── lista zdarzeń (AC6) ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lista_zdarzen_zwraca_ostatnie_dziesiec(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    integration = _integration(tenant_id, user.id)
    events = [
        IntegrationEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            integration_id=integration.id,
            event_type=ScmEventType.PUSH,
            repo_full_name=REPO,
            branch="main",
            commit_sha="a" * 40,
            status=ScmEventStatus.COMPLETED,
            created_at=datetime.now(UTC),
        )
    ]
    db.execute.return_value = _scalars(events)

    resp = await client.get(f"{BASE}/events")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["event_type"] == "push"
    assert body[0]["status"] == "completed"
    assert body[0]["branch"] == "main"
    app.dependency_overrides.clear()


# ── webhook (AC3, AC4, AC5) ─────────────────────────────────────────────────


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def _push_payload() -> bytes:
    return json.dumps(
        {
            "ref": "refs/heads/main",
            "after": "a" * 40,
            "deleted": False,
            "repository": {"full_name": REPO, "default_branch": "main"},
            "pusher": {"name": "tomek"},
            "commits": [{"id": "a" * 40}],
        }
    ).encode()


@pytest.mark.asyncio
async def test_webhook_z_poprawnym_podpisem_kolejkuje_analize(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    integration = _integration(tenant_id, user.id)
    db.execute.return_value = _scalar(integration)
    body = _push_payload()

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.scm_webhook_service.dispatch_event_analysis",
        return_value="celery-task-1",
    ) as dispatch:
        resp = await client.post(
            f"{BASE}/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _sign(body),
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "accepted"
    assert payload["task_id"] == "celery-task-1"
    dispatch.assert_called_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_ze_zlym_podpisem_to_401_i_wpis_audytowy(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_integration(tenant_id, user.id))
    body = _push_payload()

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.log_action", AsyncMock()
    ) as audit, patch(
        "app.api.routes.integrations_scm.scm_webhook_service.dispatch_event_analysis"
    ) as dispatch:
        resp = await client.post(
            f"{BASE}/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": "sha256=" + "0" * 64,
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 401
    assert audit.await_args.kwargs["action"] == "integration.github.webhook_rejected"
    dispatch.assert_not_called()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_bez_naglowka_podpisu_to_401(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_integration(tenant_id, user.id))

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.log_action", AsyncMock()
    ):
        resp = await client.post(
            f"{BASE}/webhook",
            content=_push_payload(),
            headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
        )

    assert resp.status_code == 401
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_dla_niepodlaczonego_repo_konczy_sie_200(app, client):
    """4xx zniechęciłoby GitHuba do dostaw — po serii błędów wyłącza webhook."""
    db = _db()
    _override(app, db, _redis())
    db.execute.return_value = _scalar(None)

    resp = await client.post(
        f"{BASE}/webhook",
        content=_push_payload(),
        headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_push_na_galaz_funkcyjna_konczy_sie_skipped(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_integration(tenant_id, user.id))
    body = json.dumps(
        {
            "ref": "refs/heads/feature/x",
            "after": "a" * 40,
            "repository": {"full_name": REPO},
        }
    ).encode()

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.scm_webhook_service.dispatch_event_analysis"
    ) as dispatch:
        resp = await client.post(
            f"{BASE}/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": _sign(body),
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "skipped"
    dispatch.assert_not_called()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_ping_jest_ignorowany(app, client):
    """GitHub wysyła ``ping`` tuż po utworzeniu webhooka."""
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_integration(tenant_id, user.id))
    body = json.dumps({"zen": "Design for failure.", "repository": {"full_name": REPO}}).encode()

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET):
        resp = await client.post(
            f"{BASE}/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": _sign(body),
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_pull_request_kolejkuje_analize(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_integration(tenant_id, user.id))
    body = json.dumps(
        {
            "action": "synchronize",
            "number": 7,
            "repository": {"full_name": REPO},
            "pull_request": {
                "title": "Walidacja",
                "user": {"login": "tomek"},
                "head": {"ref": "feature/x", "sha": "c" * 40},
                "base": {"ref": "main"},
            },
        }
    ).encode()

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.scm_webhook_service.dispatch_event_analysis",
        return_value="task-pr",
    ) as dispatch:
        resp = await client.post(
            f"{BASE}/webhook",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(body),
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    dispatch.assert_called_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_ze_smieciowym_jsonem_to_422(app, client):
    _override(app, _db(), _redis())

    resp = await client.post(
        f"{BASE}/webhook",
        content=b"{nie-json",
        headers={"X-GitHub-Event": "push", "Content-Type": "application/json"},
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


# ═══ GitLab (Story 8.2) ══════════════════════════════════════════════════════

GL_BASE = "/api/v1/integrations/gitlab"
GL_REPO = "grupa/app"
GL_PROJECT_ID = 7
SELF_HOSTED = "https://git.firma.pl"


def _gl_integration(tenant_id, user_id, **overrides) -> ScmIntegration:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "user_id": user_id,
        "provider": ScmProvider.GITLAB,
        "repo_full_name": GL_REPO,
        "repo_url": f"{SELF_HOSTED}/{GL_REPO}.git",
        "default_branch": "main",
        "access_token_encrypted": "enc-token",
        "webhook_secret_encrypted": "enc-secret",
        "hook_id": "99",
        "is_active": True,
        "config": {"gitlab_url": SELF_HOSTED, "gitlab_project_id": GL_PROJECT_ID},
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ScmIntegration(**defaults)


def _gl_project(project_id: int = GL_PROJECT_ID, path: str = GL_REPO, **overrides) -> dict:
    project = {
        "id": project_id,
        "path_with_namespace": path,
        "name": path.split("/")[-1],
        "visibility": "private",
        "default_branch": "main",
        "web_url": f"{SELF_HOSTED}/{path}",
        "http_url_to_repo": f"{SELF_HOSTED}/{path}.git",
    }
    project.update(overrides)
    return project


# ── OAuth (AC1) ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gitlab_authorize_zapisuje_adres_instancji_w_state(app, client):
    """Callback musi wiedzieć, do którego GitLaba wysłać wymianę kodu."""
    redis = _redis()
    _override(app, _db(), redis)

    with patch(
        "app.api.routes.integrations_scm.gitlab_service.is_configured", return_value=True
    ), patch(
        "app.api.routes.integrations_scm.gitlab_service.get_authorization_url",
        return_value=f"{SELF_HOSTED}/oauth/authorize?state=abc",
    ):
        resp = await client.get(f"{GL_BASE}/authorize", params={"gitlab_url": SELF_HOSTED})

    assert resp.status_code == 200
    assert resp.json()["authorization_url"].startswith(SELF_HOSTED)
    stored = json.loads(redis.set.await_args_list[0].args[1])
    assert stored["gitlab_url"] == SELF_HOSTED
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_authorize_bez_adresu_uzywa_domyslnego(app, client):
    redis = _redis()
    _override(app, _db(), redis)

    with patch(
        "app.api.routes.integrations_scm.gitlab_service.is_configured", return_value=True
    ), patch(
        "app.api.routes.integrations_scm.gitlab_service.get_authorization_url",
        return_value="https://gitlab.com/oauth/authorize?state=abc",
    ):
        resp = await client.get(f"{GL_BASE}/authorize")

    assert resp.status_code == 200
    assert json.loads(redis.set.await_args_list[0].args[1])["gitlab_url"] == "https://gitlab.com"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_authorize_odrzuca_adres_bez_https(app, client):
    _override(app, _db(), _redis())

    with patch("app.api.routes.integrations_scm.gitlab_service.is_configured", return_value=True):
        resp = await client.get(f"{GL_BASE}/authorize", params={"gitlab_url": "http://git.firma.pl"})

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_authorize_bez_konfiguracji_zwraca_422(app, client):
    _override(app, _db(), _redis())

    with patch("app.api.routes.integrations_scm.gitlab_service.is_configured", return_value=False):
        resp = await client.get(f"{GL_BASE}/authorize")

    assert resp.status_code == 422
    assert "GITLAB_CLIENT_ID" in resp.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_callback_wymienia_kod_na_instancji_ze_state(app, client):
    user_id = uuid.uuid4()
    redis = _redis(
        token=json.dumps(
            {"user_id": str(user_id), "tenant_id": str(uuid.uuid4()), "gitlab_url": SELF_HOSTED}
        )
    )
    _override(app, _db(), redis)

    exchange = AsyncMock(return_value={"access_token": "glpat-abc"})
    with patch("app.api.routes.integrations_scm.gitlab_service.exchange_code_for_token", exchange):
        resp = await client.get(f"{GL_BASE}/callback?code=kod&state=st", follow_redirects=False)

    assert resp.status_code == 302
    assert "/settings/integrations/gitlab?connected=1" in resp.headers["location"]
    assert exchange.await_args.args[0] == SELF_HOSTED
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_callback_z_nieznanym_state_nie_wymienia_kodu(app, client):
    redis = _redis(token=None)
    _override(app, _db(), redis)

    exchange = AsyncMock()
    with patch("app.api.routes.integrations_scm.gitlab_service.exchange_code_for_token", exchange):
        resp = await client.get(f"{GL_BASE}/callback?code=kod&state=zly", follow_redirects=False)

    assert resp.status_code == 302
    assert "error=invalid_state" in resp.headers["location"]
    exchange.assert_not_awaited()
    app.dependency_overrides.clear()


# ── projekty (AC1, AC2) ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gitlab_available_projects_oznacza_podlaczone(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis(token="glpat-abc"))
    _execute_sequence(db, _scalars([_gl_integration(tenant_id, user.id)]))

    with patch(
        "app.api.routes.integrations_scm.gitlab_service.get_user_projects",
        AsyncMock(return_value=[_gl_project(), _gl_project(8, "grupa/inny")]),
    ):
        resp = await client.get(f"{GL_BASE}/available-projects", params={"gitlab_url": SELF_HOSTED})

    assert resp.status_code == 200
    items = {p["path_with_namespace"]: p for p in resp.json()}
    assert items[GL_REPO]["connected"] is True
    assert items[GL_REPO]["project_id"] == GL_PROJECT_ID
    assert items["grupa/inny"]["connected"] is False
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_connect_zapisuje_id_projektu_i_adres_instancji(app, client):
    """Bez ``gitlab_project_id`` nie da się wywołać API webhooków ani zmian MR."""
    db = _db()
    _override(app, db, _redis(token="glpat-abc"))
    _execute_sequence(db, _scalars([]), _scalar(None))

    register = AsyncMock(return_value={"id": 99})
    with patch(
        "app.api.routes.integrations_scm.gitlab_service.get_user_projects",
        AsyncMock(return_value=[_gl_project()]),
    ), patch("app.api.routes.integrations_scm.gitlab_service.register_webhook", register), patch(
        "app.api.routes.integrations_scm.log_action", AsyncMock()
    ):
        resp = await client.post(
            f"{GL_BASE}/projects",
            params={"gitlab_url": SELF_HOSTED},
            json={"project_id": GL_PROJECT_ID},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["repo_full_name"] == GL_REPO
    assert body["gitlab_url"] == SELF_HOSTED
    assert body["webhook_active"] is True

    # Webhook rejestrowany na właściwej instancji i projekcie, z własnym sekretem
    args = register.await_args.args
    assert args[1] == SELF_HOSTED
    assert args[2] == GL_PROJECT_ID
    assert len(args[4]) == 64
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_connect_juz_podlaczonego_to_409(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis(token="glpat-abc"))
    _execute_sequence(db, _scalars([]), _scalar(_gl_integration(tenant_id, user.id)))

    with patch(
        "app.api.routes.integrations_scm.gitlab_service.get_user_projects",
        AsyncMock(return_value=[_gl_project()]),
    ):
        resp = await client.post(f"{GL_BASE}/projects", json={"project_id": GL_PROJECT_ID})

    assert resp.status_code == 409
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_connect_zajetego_przez_inna_firme_to_409(app, client):
    db = _db()
    _override(app, db, _redis(token="glpat-abc"))
    _execute_sequence(db, _scalars([]), _scalar(_gl_integration(uuid.uuid4(), uuid.uuid4())))

    with patch(
        "app.api.routes.integrations_scm.gitlab_service.get_user_projects",
        AsyncMock(return_value=[_gl_project()]),
    ):
        resp = await client.post(f"{GL_BASE}/projects", json={"project_id": GL_PROJECT_ID})

    assert resp.status_code == 409
    assert "innej firmy" in resp.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_connect_niedostepnego_projektu_to_404(app, client):
    db = _db()
    _override(app, db, _redis(token="glpat-abc"))
    _execute_sequence(db, _scalars([]))

    with patch(
        "app.api.routes.integrations_scm.gitlab_service.get_user_projects",
        AsyncMock(return_value=[_gl_project(8, "grupa/inny")]),
    ):
        resp = await client.post(f"{GL_BASE}/projects", json={"project_id": GL_PROJECT_ID})

    assert resp.status_code == 404
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_lista_podlaczonych_projektow(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    _execute_sequence(db, _scalars([_gl_integration(tenant_id, user.id)]))

    with patch("app.api.routes.integrations_scm.gitlab_service.is_configured", return_value=True):
        resp = await client.get(f"{GL_BASE}/projects")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["gitlab_url"] == SELF_HOSTED
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_disconnect_kasuje_webhook_na_instancji(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    integration = _gl_integration(tenant_id, user.id)
    db.execute.return_value = _scalar(integration)

    delete_hook = AsyncMock()
    with patch("app.api.routes.integrations_scm.decrypt_token", return_value="glpat-abc"), patch(
        "app.api.routes.integrations_scm.gitlab_service.delete_webhook", delete_hook
    ), patch("app.api.routes.integrations_scm.log_action", AsyncMock()):
        resp = await client.delete(f"{GL_BASE}/projects/{integration.id}")

    assert resp.status_code == 204
    args = delete_hook.await_args.args
    assert args[1] == SELF_HOSTED
    assert args[2] == GL_PROJECT_ID
    assert integration.is_active is False
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_disconnect_dziala_mimo_bledu_instancji(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    integration = _gl_integration(tenant_id, user.id)
    db.execute.return_value = _scalar(integration)

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value="glpat-abc"), patch(
        "app.api.routes.integrations_scm.gitlab_service.delete_webhook",
        AsyncMock(side_effect=RuntimeError("401")),
    ), patch("app.api.routes.integrations_scm.log_action", AsyncMock()):
        resp = await client.delete(f"{GL_BASE}/projects/{integration.id}")

    assert resp.status_code == 204
    assert integration.is_active is False
    app.dependency_overrides.clear()


# ── webhook (AC3, AC4, AC5) ─────────────────────────────────────────────────


def _gl_push_payload() -> bytes:
    return json.dumps(
        {
            "object_kind": "push",
            "ref": "refs/heads/main",
            "after": "d" * 40,
            "user_name": "Tomek",
            "total_commits_count": 2,
            "project": {"path_with_namespace": GL_REPO, "default_branch": "main"},
        }
    ).encode()


@pytest.mark.asyncio
async def test_gitlab_webhook_z_poprawnym_tokenem_kolejkuje_analize(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_gl_integration(tenant_id, user.id))

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.scm_webhook_service.dispatch_event_analysis",
        return_value="celery-gl-1",
    ) as dispatch:
        resp = await client.post(
            f"{GL_BASE}/webhook",
            content=_gl_push_payload(),
            headers={
                "X-Gitlab-Event": "Push Hook",
                "X-Gitlab-Token": SECRET,
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert resp.json()["task_id"] == "celery-gl-1"
    dispatch.assert_called_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_webhook_ze_zlym_tokenem_to_401_i_audyt(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_gl_integration(tenant_id, user.id))

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.log_action", AsyncMock()
    ) as audit, patch(
        "app.api.routes.integrations_scm.scm_webhook_service.dispatch_event_analysis"
    ) as dispatch:
        resp = await client.post(
            f"{GL_BASE}/webhook",
            content=_gl_push_payload(),
            headers={
                "X-Gitlab-Event": "Push Hook",
                "X-Gitlab-Token": "nie-ten-sekret",
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 401
    assert audit.await_args.kwargs["action"] == "integration.gitlab.webhook_rejected"
    dispatch.assert_not_called()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_webhook_bez_tokenu_to_401(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_gl_integration(tenant_id, user.id))

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.log_action", AsyncMock()
    ):
        resp = await client.post(
            f"{GL_BASE}/webhook",
            content=_gl_push_payload(),
            headers={"X-Gitlab-Event": "Push Hook", "Content-Type": "application/json"},
        )

    assert resp.status_code == 401
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_webhook_dla_niepodlaczonego_projektu_konczy_sie_200(app, client):
    db = _db()
    _override(app, db, _redis())
    db.execute.return_value = _scalar(None)

    resp = await client.post(
        f"{GL_BASE}/webhook",
        content=_gl_push_payload(),
        headers={"X-Gitlab-Event": "Push Hook", "Content-Type": "application/json"},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_webhook_merge_request_kolejkuje_analize(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_gl_integration(tenant_id, user.id))
    body = json.dumps(
        {
            "object_kind": "merge_request",
            "user": {"username": "tomek"},
            "project": {"path_with_namespace": GL_REPO},
            "object_attributes": {
                "action": "update",
                "iid": 42,
                "title": "Walidacja",
                "source_branch": "feature/x",
                "target_branch": "main",
                "last_commit": {"id": "e" * 40},
            },
        }
    ).encode()

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.scm_webhook_service.dispatch_event_analysis",
        return_value="task-mr",
    ) as dispatch:
        resp = await client.post(
            f"{GL_BASE}/webhook",
            content=body,
            headers={
                "X-Gitlab-Event": "Merge Request Hook",
                "X-Gitlab-Token": SECRET,
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    dispatch.assert_called_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gitlab_webhook_zamkniecie_mr_konczy_sie_skipped(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_gl_integration(tenant_id, user.id))
    body = json.dumps(
        {
            "object_kind": "merge_request",
            "project": {"path_with_namespace": GL_REPO},
            "object_attributes": {"action": "close", "iid": 42, "source_branch": "f", "target_branch": "main"},
        }
    ).encode()

    with patch("app.api.routes.integrations_scm.decrypt_token", return_value=SECRET), patch(
        "app.api.routes.integrations_scm.scm_webhook_service.dispatch_event_analysis"
    ) as dispatch:
        resp = await client.post(
            f"{GL_BASE}/webhook",
            content=body,
            headers={
                "X-Gitlab-Event": "Merge Request Hook",
                "X-Gitlab-Token": SECRET,
                "Content-Type": "application/json",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "skipped"
    dispatch.assert_not_called()
    app.dependency_overrides.clear()


# ═══ Konfiguracja status checków (Story 8.3, AC3/AC5/AC6) ════════════════════

CONFIG_BASE = "/api/v1/integrations"


@pytest.mark.asyncio
async def test_config_zwraca_domyslne_ustawienia_i_nazwe_kontekstu(app, client):
    """Nazwa kontekstu jest potrzebna do wpisania w branch protection (AC4)."""
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    integration = _integration(tenant_id, user.id, config={})
    db.execute.return_value = _scalar(integration)

    resp = await client.get(f"{CONFIG_BASE}/{integration.id}/config")

    assert resp.status_code == 200
    body = resp.json()
    assert body["severity_threshold"] == "critical"
    assert body["post_comment"] is True
    assert body["fail_on_threshold"] is True
    assert body["status_context"] == "TestGEN / Code Analysis"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_config_nieznanej_integracji_to_404(app, client):
    db = _db()
    _override(app, db, _redis())
    db.execute.return_value = _scalar(None)

    resp = await client.get(f"{CONFIG_BASE}/{uuid.uuid4()}/config")

    assert resp.status_code == 404
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_zapis_konfiguracji_nie_gubi_danych_polaczenia(app, client):
    """``config`` niesie też adres instancji i id projektu GitLaba (8.2)."""
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    integration = _gl_integration(tenant_id, user.id)
    db.execute.return_value = _scalar(integration)

    with patch("app.api.routes.integrations_scm.log_action", AsyncMock()):
        resp = await client.put(
            f"{CONFIG_BASE}/{integration.id}/config",
            json={
                "severity_threshold": "high",
                "post_comment": False,
                "fail_on_threshold": False,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["severity_threshold"] == "high"
    assert body["post_comment"] is False
    assert body["fail_on_threshold"] is False
    # Dane połączenia przetrwały nadpisanie
    assert integration.config["gitlab_project_id"] == GL_PROJECT_ID
    assert integration.config["gitlab_url"] == SELF_HOSTED
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_zapis_konfiguracji_loguje_operacje(app, client):
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    integration = _integration(tenant_id, user.id)
    db.execute.return_value = _scalar(integration)

    with patch("app.api.routes.integrations_scm.log_action", AsyncMock()) as audit:
        resp = await client.put(
            f"{CONFIG_BASE}/{integration.id}/config",
            json={"severity_threshold": "medium"},
        )

    assert resp.status_code == 200
    assert audit.await_args.kwargs["action"] == "integration.status_check.configured"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_niedozwolony_prog_odrzucany(app, client):
    """Progi 'low'/'info' zablokowałyby każdy merge — kontrakt ich nie dopuszcza."""
    db = _db()
    tenant_id, user = _override(app, db, _redis())
    db.execute.return_value = _scalar(_integration(tenant_id, user.id))

    resp = await client.put(
        f"{CONFIG_BASE}/{uuid.uuid4()}/config", json={"severity_threshold": "low"}
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_config_cudzej_integracji_to_404(app, client):
    """Filtr po tenancie w zapytaniu — cudza integracja jest niewidoczna."""
    db = _db()
    _override(app, db, _redis())
    db.execute.return_value = _scalar(None)

    resp = await client.put(
        f"{CONFIG_BASE}/{uuid.uuid4()}/config", json={"severity_threshold": "critical"}
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()
