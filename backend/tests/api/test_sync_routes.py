"""API testy synchronizacji dwukierunkowej — Story 8.11 (Task 6.2).

DB mockowana, zadanie Celery patchowane. Sprawdzamy kontrakt endpointów:
walidację odstępu, dostawców bez wsparcia, stan i rozstrzyganie konfliktów.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.integration import IntegrationConfig, IntegrationProvider, SyncStatus
from app.models.sync_conflict import ConflictResolution, SyncConflict
from app.models.sync_state import ConflictStrategy, SyncDirection, SyncHealth, SyncState
from tests.factories import make_user

BASE = "/api/v1/integrations"
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


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
            obj.created_at = NOW

    db.add = MagicMock(side_effect=_add)
    return db


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    r.scalar_one.return_value = item
    return r


def _count(value: int) -> MagicMock:
    r = MagicMock()
    r.scalar_one.return_value = value
    return r


def _rows(items) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = list(items)
    return r


def _sequence(db: AsyncMock, *results) -> None:
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
    return tenant_id, user.id


def _integration(tenant_id, provider=IntegrationProvider.TESTRAIL) -> IntegrationConfig:
    from app.core.encryption import encrypt

    return IntegrationConfig(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        project_id=uuid.uuid4(),
        provider=provider,
        base_url="https://firma.testrail.io",
        encrypted_credentials=encrypt("qa@firma.pl:klucz"),
        settings={"testrail_project_id": 12},
        is_active=True,
        created_at=NOW,
    )


def _state(tenant_id, integration_id=None, **overrides) -> SyncState:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "integration_id": integration_id or uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "provider": "testrail",
        "direction": SyncDirection.BIDIRECTIONAL,
        "conflict_strategy": ConflictStrategy.LAST_WRITE_WINS,
        "interval_minutes": 15,
        "is_active": True,
        "health": SyncHealth.ACTIVE,
        "last_sync_at": NOW - timedelta(minutes=5),
        "last_sync_status": SyncStatus.SUCCESS,
        "consecutive_failures": 0,
        "synced_count": 7,
        "created_at": NOW,
    }
    defaults.update(overrides)
    return SyncState(**defaults)


# ── konfiguracja ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_konfiguracja_tworzy_stan_synchronizacji(app, client):
    db = _db()
    tenant_id, _ = _override(app, db)
    integration = _integration(tenant_id)
    _sequence(db, _scalar(integration), _scalar(None), _count(0))

    response = await client.put(
        f"{BASE}/{integration.id}/sync/config",
        json={"direction": "pull", "interval_minutes": 30, "conflict_strategy": "manual"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["direction"] == "pull"
    assert body["interval_minutes"] == 30
    assert body["conflict_strategy"] == "manual"
    # Konfiguracja nie uruchamia synchronizacji.
    assert body["is_active"] is False


@pytest.mark.asyncio
async def test_odstep_ponizej_minimum_odrzucony_przez_schemat(app, client):
    db = _db()
    tenant_id, _ = _override(app, db)

    response = await client.put(
        f"{BASE}/{uuid.uuid4()}/sync/config",
        json={"direction": "pull", "interval_minutes": 2},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_dostawca_bez_wsparcia_synchronizacji_jest_odrzucany(app, client):
    db = _db()
    tenant_id, _ = _override(app, db)
    integration = _integration(tenant_id, provider=IntegrationProvider.AZURE_DEVOPS)
    _sequence(db, _scalar(integration))

    response = await client.put(
        f"{BASE}/{integration.id}/sync/config", json={"direction": "push"}
    )

    assert response.status_code == 422
    assert "azure_devops" in response.text


@pytest.mark.asyncio
async def test_nieistniejaca_integracja_daje_404(app, client):
    db = _db()
    _override(app, db)
    _sequence(db, _scalar(None))

    response = await client.put(f"{BASE}/{uuid.uuid4()}/sync/config", json={})

    assert response.status_code == 404


# ── stan ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_zwraca_zdrowie_i_liczbe_konfliktow(app, client):
    db = _db()
    tenant_id, _ = _override(app, db)
    integration_id = uuid.uuid4()
    state = _state(tenant_id, integration_id, health=SyncHealth.DEGRADED, consecutive_failures=3)
    _sequence(db, _scalar(state), _count(2))

    response = await client.get(f"{BASE}/{integration_id}/sync/status")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["health"] == "degraded"
    assert body["pending_conflicts"] == 2
    assert body["synced_count"] == 7
    assert body["next_sync_at"] is not None


@pytest.mark.asyncio
async def test_status_bez_konfiguracji_daje_404(app, client):
    db = _db()
    _override(app, db)
    _sequence(db, _scalar(None))

    response = await client.get(f"{BASE}/{uuid.uuid4()}/sync/status")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_aktywacja_zeruje_licznik_porazek(app, client):
    db = _db()
    tenant_id, _ = _override(app, db)
    integration_id = uuid.uuid4()
    state = _state(
        tenant_id,
        integration_id,
        is_active=False,
        health=SyncHealth.DEGRADED,
        consecutive_failures=5,
        last_error="timeout",
    )
    _sequence(db, _scalar(state), _count(0))

    response = await client.post(f"{BASE}/{integration_id}/sync/activate")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_active"] is True
    assert body["health"] == "active"
    assert body["consecutive_failures"] == 0
    assert body["last_error"] is None


@pytest.mark.asyncio
async def test_dezaktywacja_zatrzymuje_przebiegi(app, client):
    db = _db()
    tenant_id, _ = _override(app, db)
    integration_id = uuid.uuid4()
    _sequence(db, _scalar(_state(tenant_id, integration_id)), _count(0))

    response = await client.post(f"{BASE}/{integration_id}/sync/deactivate")

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is False
    # Nieaktywna synchronizacja nie ma terminu następnego przebiegu.
    assert body["next_sync_at"] is None


# ── ręczne wyzwolenie ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reczne_wyzwolenie_kolejkuje_zadanie(app, client):
    db = _db()
    tenant_id, _ = _override(app, db)
    integration_id = uuid.uuid4()
    state = _state(tenant_id, integration_id)
    _sequence(db, _scalar(state))

    with patch("app.workers.tasks.sync_tasks.run_sync.delay") as delay:
        delay.return_value = MagicMock(id="zadanie-1")
        response = await client.post(f"{BASE}/{integration_id}/sync/run")

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["task_id"] == "zadanie-1"
    assert body["status_url"] == "/api/v1/tasks/zadanie-1"
    delay.assert_called_once_with(str(state.id), str(tenant_id))


# ── konflikty ───────────────────────────────────────────────────────────────


def _conflict(tenant_id, sync_state_id, **overrides) -> SyncConflict:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "sync_state_id": sync_state_id,
        "test_case_id": uuid.uuid4(),
        "tms_test_id": "42",
        "testgen_version": {"title": "Wersja TestGEN"},
        "tms_version": {"title": "Wersja TMS"},
        "resolution": ConflictResolution.PENDING,
        "created_at": NOW,
    }
    defaults.update(overrides)
    return SyncConflict(**defaults)


@pytest.mark.asyncio
async def test_lista_konfliktow_niesie_obie_wersje(app, client):
    db = _db()
    tenant_id, _ = _override(app, db)
    integration_id = uuid.uuid4()
    state = _state(tenant_id, integration_id)
    conflict = _conflict(tenant_id, state.id)
    _sequence(db, _scalar(state), _count(1), _rows([conflict]))

    response = await client.get(f"{BASE}/{integration_id}/sync/conflicts")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["testgen_version"]["title"] == "Wersja TestGEN"
    assert body["items"][0]["tms_version"]["title"] == "Wersja TMS"


@pytest.mark.asyncio
async def test_rozstrzygniecie_na_korzysc_testgen_nie_dotyka_przypadku(app, client):
    db = _db()
    tenant_id, user_id = _override(app, db)
    conflict = _conflict(tenant_id, uuid.uuid4())
    _sequence(db, _scalar(conflict))

    response = await client.post(
        f"/api/v1/sync/conflicts/{conflict.id}/resolve", json={"resolution": "testgen_wins"}
    )

    assert response.status_code == 200, response.text
    assert response.json()["resolution"] == "testgen_wins"
    assert conflict.resolved_by == user_id


@pytest.mark.asyncio
async def test_juz_rozstrzygniety_konflikt_nie_daje_sie_rozstrzygnac_ponownie(app, client):
    db = _db()
    tenant_id, _ = _override(app, db)
    conflict = _conflict(tenant_id, uuid.uuid4(), resolution=ConflictResolution.TMS_WINS)
    _sequence(db, _scalar(conflict))

    response = await client.post(
        f"/api/v1/sync/conflicts/{conflict.id}/resolve", json={"resolution": "testgen_wins"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_nieznane_rozstrzygniecie_jest_odrzucane(app, client):
    db = _db()
    _override(app, db)

    response = await client.post(
        f"/api/v1/sync/conflicts/{uuid.uuid4()}/resolve", json={"resolution": "moje_zdanie"}
    )

    assert response.status_code == 422
