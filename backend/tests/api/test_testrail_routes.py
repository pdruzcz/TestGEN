"""API testy integracji z TestRailem — Story 8.8 (AC1, AC2, AC5; Task 5.3).

DB mockowana, klient TestRaila patchowany. Powtarzająca się asercja: klucz API
nie wychodzi żadnym endpointem — odpowiedź niesie e-mail, bo ten identyfikuje
konto, ale nie sekret.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.integration import IntegrationConfig, IntegrationProvider
from app.models.project import Project, ProjectStatus
from tests.factories import make_user

CONFIG_BASE = "/api/v1/integrations/testrail"
PROJECTS_BASE = "/api/v1/projects"
TESTRAIL_URL = "https://firma.testrail.io"
API_KEY = "klucz-api-testrail"
EMAIL = "qa@firma.pl"


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


def _sequence(db: AsyncMock, *results) -> None:
    """Kolejne wyniki ``db.execute``; po wyczerpaniu — pusty."""
    pending = list(results)

    def _next(*args, **kwargs):
        return pending.pop(0) if pending else _scalar(None)

    db.execute.side_effect = _next


def _override(app, db) -> tuple[uuid.UUID, uuid.UUID]:
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    user = make_user(email="owner@a.com", name="Owner")
    tenant_id = uuid.uuid4()
    user._tenant_id = tenant_id
    project_id = uuid.uuid4()

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = "owner"
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return tenant_id, project_id


def _project(project_id, tenant_id) -> Project:
    return Project(
        id=project_id,
        tenant_id=tenant_id,
        name="Projekt",
        status=ProjectStatus.ACTIVE,
        is_deleted=False,
        created_at=datetime.now(UTC),
    )


def _config(project_id, tenant_id, **overrides) -> IntegrationConfig:
    from app.core.encryption import encrypt

    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "project_id": project_id,
        "provider": IntegrationProvider.TESTRAIL,
        "base_url": TESTRAIL_URL,
        "encrypted_credentials": encrypt(f"{EMAIL}:{API_KEY}"),
        "settings": {"testrail_project_id": 12, "priority_map": {"CRITICAL": 4}},
        "is_active": True,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return IntegrationConfig(**defaults)


def _payload(**overrides) -> dict:
    body = {
        "base_url": TESTRAIL_URL,
        "email": EMAIL,
        "api_key": API_KEY,
        "testrail_project_id": 12,
    }
    body.update(overrides)
    return body


# ── konfiguracja (AC1/AC4) ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zapis_konfiguracji_nie_zwraca_klucza(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(None))

    with patch("app.api.routes.integrations_tms.log_action", AsyncMock()):
        resp = await client.put(
            f"{CONFIG_BASE}/config", params={"project_id": str(project_id)}, json=_payload()
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["base_url"] == TESTRAIL_URL
    assert body["email"] == EMAIL
    assert body["testrail_project_id"] == 12
    assert API_KEY not in resp.text
    assert "api_key" not in body
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_zapis_dostarcza_domyslne_mapowania(app, client):
    """Bez nich użytkownik musiałby wypełnić mapowanie, zanim cokolwiek wyeksportuje."""
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(None))

    with patch("app.api.routes.integrations_tms.log_action", AsyncMock()):
        resp = await client.put(
            f"{CONFIG_BASE}/config", params={"project_id": str(project_id)}, json=_payload()
        )

    body = resp.json()
    assert body["priority_map"]["CRITICAL"] == 4
    assert body["type_map"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_zapis_nadpisuje_istniejaca_konfiguracje(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    existing = _config(project_id, tenant_id)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(existing))

    with patch("app.api.routes.integrations_tms.log_action", AsyncMock()):
        resp = await client.put(
            f"{CONFIG_BASE}/config",
            params={"project_id": str(project_id)},
            json=_payload(testrail_project_id=99),
        )

    assert resp.status_code == 200
    assert existing.settings["testrail_project_id"] == 99
    db.add.assert_not_called()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_adres_bez_https_jest_odrzucany(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)))

    resp = await client.put(
        f"{CONFIG_BASE}/config",
        params={"project_id": str(project_id)},
        json=_payload(base_url="http://firma.testrail.io"),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_konfiguracja_cudzego_projektu_to_404(app, client):
    db = _db()
    _override(app, db)
    _sequence(db, _scalar(None))

    resp = await client.put(
        f"{CONFIG_BASE}/config", params={"project_id": str(uuid.uuid4())}, json=_payload()
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_odczyt_konfiguracji(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(_config(project_id, tenant_id)))

    resp = await client.get(f"{CONFIG_BASE}/config", params={"project_id": str(project_id)})

    assert resp.status_code == 200
    assert resp.json()["email"] == EMAIL
    assert API_KEY not in resp.text
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_odczyt_bez_konfiguracji_to_404(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(None))

    resp = await client.get(f"{CONFIG_BASE}/config", params={"project_id": str(project_id)})

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# ── test połączenia (AC1) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_polaczenie_udane_zwraca_nazwe_projektu(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(_config(project_id, tenant_id)))

    with patch(
        "app.services.export.testrail_service.TestRailClient.test_connection",
        AsyncMock(return_value={"connected": True, "project_id": 12, "project_name": "QA", "is_completed": False}),
    ):
        resp = await client.post(f"{CONFIG_BASE}/test", params={"project_id": str(project_id)})

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["project_name"] == "QA"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_polaczenie_nieudane_zwraca_komunikat_a_nie_blad_http(app, client):
    """Zły klucz to informacja dla użytkownika, nie awaria API."""
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(_config(project_id, tenant_id)))

    with patch(
        "app.services.export.testrail_service.TestRailClient.test_connection",
        AsyncMock(side_effect=RuntimeError("TestRail odrzucił poświadczenia")),
    ):
        resp = await client.post(f"{CONFIG_BASE}/test", params={"project_id": str(project_id)})

    assert resp.status_code == 200
    assert resp.json()["connected"] is False
    assert "poświadczenia" in resp.json()["message"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_konfiguracja_bez_id_projektu_testrail(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    config = _config(project_id, tenant_id, settings={})
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(config))

    resp = await client.post(f"{CONFIG_BASE}/test", params={"project_id": str(project_id)})

    assert resp.json()["connected"] is False
    assert "identyfikatora projektu" in resp.json()["message"]
    app.dependency_overrides.clear()


# ── eksport (AC2/AC5) ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_eksport_kolejkuje_zadanie_i_zwraca_202(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(_config(project_id, tenant_id)))
    db.scalar.return_value = 7

    task = MagicMock(id="celery-export-1")
    with patch(
        "app.api.routes.integrations.export_to_testrail.delay", return_value=task
    ) as dispatch, patch(
        "app.api.routes.integrations.TaskProgressService"
    ):
        resp = await client.post(
            f"{PROJECTS_BASE}/{project_id}/export/testrail", json={"test_case_ids": []}
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["task_id"] == "celery-export-1"
    assert body["status_url"] == "/api/v1/tasks/celery-export-1"
    assert body["test_cases"] == 7
    dispatch.assert_called_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_eksport_przekazuje_wybrane_przypadki(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(_config(project_id, tenant_id)))
    db.scalar.return_value = 2
    selected = [str(uuid.uuid4()), str(uuid.uuid4())]

    with patch(
        "app.api.routes.integrations.export_to_testrail.delay",
        return_value=MagicMock(id="t1"),
    ) as dispatch, patch("app.api.routes.integrations.TaskProgressService"):
        await client.post(
            f"{PROJECTS_BASE}/{project_id}/export/testrail", json={"test_case_ids": selected}
        )

    assert dispatch.call_args.kwargs["test_case_ids"] == selected
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_eksport_bez_konfiguracji_to_404(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(None))

    resp = await client.post(
        f"{PROJECTS_BASE}/{project_id}/export/testrail", json={"test_case_ids": []}
    )

    assert resp.status_code == 404
    assert "TestRail" in resp.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_eksport_cudzego_projektu_to_404(app, client):
    db = _db()
    _override(app, db)
    _sequence(db, _scalar(None))

    resp = await client.post(
        f"{PROJECTS_BASE}/{uuid.uuid4()}/export/testrail", json={"test_case_ids": []}
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# ── kolejność tras ───────────────────────────────────────────────────────────


def test_trasy_testrail_wygrywaja_z_trasa_parametryczna():
    """Bezpiecznik na realną pułapkę: ``/integrations/{integration_id}/config``
    (Story 8.3) przechwytywał ``/integrations/testrail/config``, bo był
    zarejestrowany wcześniej — „testrail" trafiało do parsera UUID."""
    from app.api.router import api_router

    paths = [getattr(route, "path", "") for route in api_router.routes]
    literal = paths.index("/api/v1/integrations/testrail/config")
    parametric = paths.index("/api/v1/integrations/{integration_id}/config")

    assert literal < parametric


@pytest.mark.asyncio
async def test_trasa_testrail_odpowiada_zamiast_parsowac_uuid(app, client):
    """Test end-to-end tej samej pułapki — 404 z braku konfiguracji, nie 422."""
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalar(None))

    resp = await client.get(f"{CONFIG_BASE}/config", params={"project_id": str(project_id)})

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# ═══ Story 8.9: Jira Xray i Zephyr Scale ═════════════════════════════════════

JIRA_BASE = "/api/v1/integrations/jira"
JIRA_URL = "https://firma.atlassian.net"
JIRA_TOKEN = "token-atlassian"
PROJECT_KEY = "QA"


def _jira_config(project_id, tenant_id, provider=IntegrationProvider.XRAY, **overrides):
    from app.core.encryption import encrypt

    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "project_id": project_id,
        "provider": provider,
        "base_url": JIRA_URL,
        "encrypted_credentials": encrypt(f"{EMAIL}:{JIRA_TOKEN}"),
        "settings": {"jira_project_key": PROJECT_KEY, "linked_issue": "QA-42"},
        "is_active": True,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return IntegrationConfig(**defaults)


def _scalars_first(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.first.return_value = items[0] if items else None
    r.scalars.return_value.all.return_value = items
    return r


def _jira_payload(**overrides) -> dict:
    body = {
        "base_url": JIRA_URL,
        "email": EMAIL,
        "api_token": JIRA_TOKEN,
        "project_key": PROJECT_KEY,
        "plugin": "xray",
    }
    body.update(overrides)
    return body


# ── konfiguracja (AC1/AC5) ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_jira_zapis_konfiguracji_nie_zwraca_tokenu(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalars_first([]))

    with patch("app.api.routes.integrations_tms.log_action", AsyncMock()):
        resp = await client.put(
            f"{JIRA_BASE}/config", params={"project_id": str(project_id)}, json=_jira_payload()
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["plugin"] == "xray"
    assert body["project_key"] == PROJECT_KEY
    assert body["email"] == EMAIL
    assert JIRA_TOKEN not in resp.text
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jira_klucz_projektu_normalizowany_do_wielkich_liter(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalars_first([]))

    with patch("app.api.routes.integrations_tms.log_action", AsyncMock()):
        resp = await client.put(
            f"{JIRA_BASE}/config",
            params={"project_id": str(project_id)},
            json=_jira_payload(project_key=" qa "),
        )

    assert resp.json()["project_key"] == "QA"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jira_wybor_drugiej_wtyczki_dezaktywuje_poprzednia(app, client):
    """Eksport nie wiedziałby, której użyć, gdyby obie zostały aktywne."""
    db = _db()
    tenant_id, project_id = _override(app, db)
    existing_xray = _jira_config(project_id, tenant_id, IntegrationProvider.XRAY)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalars_first([existing_xray]))

    with patch("app.api.routes.integrations_tms.log_action", AsyncMock()):
        resp = await client.put(
            f"{JIRA_BASE}/config",
            params={"project_id": str(project_id)},
            json=_jira_payload(plugin="zephyr"),
        )

    assert resp.status_code == 200
    assert resp.json()["plugin"] == "zephyr"
    assert existing_xray.is_active is False
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jira_adres_bez_https_odrzucony(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)))

    resp = await client.put(
        f"{JIRA_BASE}/config",
        params={"project_id": str(project_id)},
        json=_jira_payload(base_url="http://firma.atlassian.net"),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jira_nieznana_wtyczka_odrzucona(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)))

    resp = await client.put(
        f"{JIRA_BASE}/config",
        params={"project_id": str(project_id)},
        json=_jira_payload(plugin="testlink"),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jira_odczyt_konfiguracji(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalars_first([_jira_config(project_id, tenant_id)]),
    )

    resp = await client.get(f"{JIRA_BASE}/config", params={"project_id": str(project_id)})

    assert resp.status_code == 200
    assert resp.json()["linked_issue"] == "QA-42"
    assert JIRA_TOKEN not in resp.text
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jira_odczyt_bez_konfiguracji_to_404(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalars_first([]))

    resp = await client.get(f"{JIRA_BASE}/config", params={"project_id": str(project_id)})

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# ── test połączenia (AC1) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_jira_polaczenie_udane(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalars_first([_jira_config(project_id, tenant_id)]),
    )

    with patch(
        "app.services.export.jira_tms_service.JiraTmsClient.test_connection",
        AsyncMock(
            return_value={
                "connected": True,
                "account": "Anna QA",
                "project_key": PROJECT_KEY,
                "project_name": "Projekt QA",
            }
        ),
    ):
        resp = await client.post(f"{JIRA_BASE}/test", params={"project_id": str(project_id)})

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["account"] == "Anna QA"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jira_polaczenie_nieudane_to_komunikat_nie_blad_http(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalars_first([_jira_config(project_id, tenant_id)]),
    )

    with patch(
        "app.services.export.jira_tms_service.JiraTmsClient.test_connection",
        AsyncMock(side_effect=RuntimeError("Jira odrzuciła poświadczenia")),
    ):
        resp = await client.post(f"{JIRA_BASE}/test", params={"project_id": str(project_id)})

    assert resp.status_code == 200
    assert resp.json()["connected"] is False
    app.dependency_overrides.clear()


# ── eksport (AC2/AC3) ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_eksport_xray_kolejkuje_zadanie(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalars_first([_jira_config(project_id, tenant_id, IntegrationProvider.XRAY)]),
    )
    db.scalar.return_value = 4

    with patch(
        "app.api.routes.integrations.export_to_jira_tms.delay",
        return_value=MagicMock(id="celery-xray"),
    ) as dispatch, patch("app.api.routes.integrations.TaskProgressService"):
        resp = await client.post(
            f"{PROJECTS_BASE}/{project_id}/export/xray", json={"test_case_ids": []}
        )

    assert resp.status_code == 202
    assert resp.json()["task_id"] == "celery-xray"
    assert resp.json()["test_cases"] == 4
    assert dispatch.call_args.kwargs["provider"] == "xray"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_eksport_zephyr_kolejkuje_zadanie(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalars_first([_jira_config(project_id, tenant_id, IntegrationProvider.ZEPHYR)]),
    )
    db.scalar.return_value = 2

    with patch(
        "app.api.routes.integrations.export_to_jira_tms.delay",
        return_value=MagicMock(id="celery-zephyr"),
    ) as dispatch, patch("app.api.routes.integrations.TaskProgressService"):
        resp = await client.post(
            f"{PROJECTS_BASE}/{project_id}/export/zephyr", json={"test_case_ids": []}
        )

    assert resp.status_code == 202
    assert dispatch.call_args.kwargs["provider"] == "zephyr"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_eksport_niezgodny_z_konfiguracja_to_422(app, client):
    """Projekt skonfigurowany na Zephyra nie powinien po cichu eksportować do Xraya."""
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(
        db,
        _scalar(_project(project_id, tenant_id)),
        _scalars_first([_jira_config(project_id, tenant_id, IntegrationProvider.ZEPHYR)]),
    )

    resp = await client.post(
        f"{PROJECTS_BASE}/{project_id}/export/xray", json={"test_case_ids": []}
    )

    assert resp.status_code == 422
    assert "zephyr" in resp.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_eksport_jira_bez_konfiguracji_to_404(app, client):
    db = _db()
    tenant_id, project_id = _override(app, db)
    _sequence(db, _scalar(_project(project_id, tenant_id)), _scalars_first([]))

    resp = await client.post(
        f"{PROJECTS_BASE}/{project_id}/export/xray", json={"test_case_ids": []}
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_trasy_jira_wygrywaja_z_trasa_parametryczna():
    """Ta sama pułapka co przy TestRailu — ``jira`` nie może trafić do parsera UUID."""
    from app.api.router import api_router

    paths = [getattr(route, "path", "") for route in api_router.routes]
    literal = paths.index("/api/v1/integrations/jira/config")
    parametric = paths.index("/api/v1/integrations/{integration_id}/config")

    assert literal < parametric
