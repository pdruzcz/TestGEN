"""Zadania synchronizacji z TMS — Story 8.11 (Task 6.3).

Sesja bazy i klienci TMS są podstawiani; sprawdzamy, co zadanie robi
z wynikiem: kogo kolejkuje, kiedy powiadamia i czy porażka nie ucieka
poza zadanie.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.sql.elements import TextClause

from app.models.sync_state import ConflictStrategy, SyncDirection, SyncHealth, SyncState
from app.services.export.sync_service import SyncOutcome

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


def _state(**overrides) -> SyncState:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "integration_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "provider": "testrail",
        "direction": SyncDirection.BIDIRECTIONAL,
        "conflict_strategy": ConflictStrategy.LAST_WRITE_WINS,
        "interval_minutes": 15,
        "is_active": True,
        "last_sync_at": None,
        "consecutive_failures": 0,
        "health": SyncHealth.ACTIVE,
        "synced_count": 0,
    }
    defaults.update(overrides)
    return SyncState(**defaults)


@asynccontextmanager
async def _session_cm(session):
    yield session


def _session_factory(session):
    return lambda: _session_cm(session)


# ── skaner ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_skaner_kolejkuje_tylko_zalegle_synchronizacje():
    from app.workers.tasks import sync_tasks

    # Zaległość liczy się względem bieżącego czasu, więc punkt odniesienia
    # musi być „teraz", a nie ustalona data.
    teraz = datetime.now(UTC)
    zalegla = _state(last_sync_at=teraz - timedelta(hours=1))
    swieza = _state(last_sync_at=teraz - timedelta(minutes=1))
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [zalegla, swieza]
    session.execute.return_value = result

    with (
        patch("app.core.database.task_session", _session_factory(session)),
        patch.object(sync_tasks.run_sync, "delay") as delay,
    ):
        summary = await sync_tasks._scan_impl()

    assert summary["dispatched"] == 1
    delay.assert_called_once_with(str(zalegla.id), str(zalegla.tenant_id))


@pytest.mark.asyncio
async def test_skaner_ustawia_bypass_rls():
    from app.workers.tasks import sync_tasks

    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    with (
        patch("app.core.database.task_session", _session_factory(session)),
        patch.object(sync_tasks.run_sync, "delay"),
    ):
        await sync_tasks._scan_impl()

    # Skaner patrzy przez wszystkie firmy — bez NIL-owego tenanta RLS
    # odciąłby mu wszystkie wiersze.
    first_sql = str(session.execute.call_args_list[0][0][0])
    assert "00000000-0000-0000-0000-000000000000" in first_sql


# ── przebieg ────────────────────────────────────────────────────────────────


def _run_session(state, integration) -> AsyncMock:
    session = AsyncMock()
    pending = [state, integration, MagicMock(name="Projekt")]

    def _next(statement, *args, **kwargs):
        result = MagicMock()
        # ``SET LOCAL app.current_tenant`` to też ``execute`` — gdyby zjadał
        # pozycję z kolejki, każdy wynik przesunąłby się o jeden.
        if isinstance(statement, TextClause):
            return result
        result.scalar_one_or_none.return_value = pending.pop(0) if pending else None
        return result

    session.execute.side_effect = _next
    return session


def _integration():
    from app.core.encryption import encrypt

    integration = MagicMock()
    integration.settings = {"testrail_project_id": 12}
    integration.encrypted_credentials = encrypt("qa@firma.pl:klucz")
    integration.base_url = "https://firma.testrail.io"
    return integration


@pytest.mark.asyncio
async def test_przebieg_dwukierunkowy_ciagnie_przed_wyslaniem():
    from app.workers.tasks import sync_tasks

    state = _state()
    session = _run_session(state, _integration())
    kolejnosc: list[str] = []

    async def fake_pull(*args, **kwargs):
        kolejnosc.append("pull")
        return SyncOutcome(pulled=2)

    async def fake_push(*args, **kwargs):
        kolejnosc.append("push")
        return SyncOutcome(pushed=3)

    with (
        patch("app.core.database.task_session", _session_factory(session)),
        patch("app.services.export.sync_service.run_pull_sync", fake_pull),
        patch("app.services.export.sync_service.run_push_sync", fake_push),
        patch("app.services.export.sync_service.fetch_remote_index", AsyncMock(return_value={})),
        patch("app.services.export.tms_exporter.build_tms_client", MagicMock()),
        patch("app.services.export.tms_exporter.build_exporter", MagicMock()),
    ):
        summary = await sync_tasks._run_impl(str(state.id), str(state.tenant_id))

    # Kolejność ma znaczenie: push przed pullem wysyłałby wersję sprzed
    # rozstrzygnięcia konfliktu i natychmiast ją cofał.
    assert kolejnosc == ["pull", "push"]
    assert summary["pulled"] == 2
    assert summary["pushed"] == 3
    assert state.synced_count == 5


@pytest.mark.asyncio
async def test_kierunek_push_pomija_odczyt_z_tms():
    from app.workers.tasks import sync_tasks

    state = _state(direction=SyncDirection.PUSH)
    session = _run_session(state, _integration())
    fetch = AsyncMock(return_value={})

    with (
        patch("app.core.database.task_session", _session_factory(session)),
        patch("app.services.export.sync_service.fetch_remote_index", fetch),
        patch(
            "app.services.export.sync_service.run_push_sync",
            AsyncMock(return_value=SyncOutcome(pushed=1)),
        ),
        patch("app.services.export.tms_exporter.build_exporter", MagicMock()),
    ):
        summary = await sync_tasks._run_impl(str(state.id), str(state.tenant_id))

    fetch.assert_not_called()
    assert summary["pushed"] == 1


@pytest.mark.asyncio
async def test_blad_tms_nie_wychodzi_poza_zadanie():
    from app.workers.tasks import sync_tasks

    state = _state()
    session = _run_session(state, _integration())

    with (
        patch("app.core.database.task_session", _session_factory(session)),
        patch(
            "app.services.export.sync_service.fetch_remote_index",
            AsyncMock(side_effect=RuntimeError("TestRail nie odpowiada")),
        ),
        patch("app.services.export.tms_exporter.build_tms_client", MagicMock()),
    ):
        summary = await sync_tasks._run_impl(str(state.id), str(state.tenant_id))

    # Wyjątek zakończyłby zadanie błędem i zgubił zapis stanu — a to właśnie
    # stan mówi, że trzecia porażka z rzędu ma zdegradować synchronizację.
    assert summary["status"] == "failed"
    assert state.consecutive_failures == 1
    assert state.last_error == "TestRail nie odpowiada"


@pytest.mark.asyncio
async def test_trzecia_porazka_powiadamia_ownera():
    from app.workers.tasks import sync_tasks

    state = _state(consecutive_failures=2)
    session = _run_session(state, _integration())
    notify = AsyncMock()

    with (
        patch("app.core.database.task_session", _session_factory(session)),
        patch(
            "app.services.export.sync_service.fetch_remote_index",
            AsyncMock(side_effect=RuntimeError("401 Unauthorized")),
        ),
        patch("app.services.export.tms_exporter.build_tms_client", MagicMock()),
        patch.object(sync_tasks, "_notify_owner", notify),
    ):
        await sync_tasks._run_impl(str(state.id), str(state.tenant_id))

    assert state.health is SyncHealth.DEGRADED
    notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_czwarta_porazka_nie_powtarza_powiadomienia():
    from app.workers.tasks import sync_tasks

    state = _state(consecutive_failures=3, health=SyncHealth.DEGRADED)
    session = _run_session(state, _integration())
    notify = AsyncMock()

    with (
        patch("app.core.database.task_session", _session_factory(session)),
        patch(
            "app.services.export.sync_service.fetch_remote_index",
            AsyncMock(side_effect=RuntimeError("401 Unauthorized")),
        ),
        patch("app.services.export.tms_exporter.build_tms_client", MagicMock()),
        patch.object(sync_tasks, "_notify_owner", notify),
    ):
        await sync_tasks._run_impl(str(state.id), str(state.tenant_id))

    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_usunieta_integracja_konczy_przebieg_bez_wyjatku():
    from app.workers.tasks import sync_tasks

    state = _state()
    session = _run_session(state, None)

    with patch("app.core.database.task_session", _session_factory(session)):
        summary = await sync_tasks._run_impl(str(state.id), str(state.tenant_id))

    assert summary["status"] == "missing_integration"
    assert state.last_error == "Integracja została usunięta"


@pytest.mark.asyncio
async def test_nieistniejacy_stan_konczy_przebieg_spokojnie():
    from app.workers.tasks import sync_tasks

    session = _run_session(None, None)

    with patch("app.core.database.task_session", _session_factory(session)):
        summary = await sync_tasks._run_impl(str(uuid.uuid4()), str(uuid.uuid4()))

    assert summary["status"] == "missing_state"


def test_zadania_ida_na_wlasna_kolejke():
    from app.workers.celery_app import celery_app
    from app.workers.tasks import sync_tasks

    assert sync_tasks.run_sync.queue == "sync"
    assert sync_tasks.scan_due_syncs.queue == "sync"
    # Bez wpisu w beat harmonogram nigdy nie sięgnąłby po zaległe przebiegi.
    assert "tms-sync-scan-due-every-5-minutes" in celery_app.conf.beat_schedule
