"""Testy zadania Celery usage_snapshot — Story 7.9, Task 2 (AC3).

Daily snapshot liczników do ``UsageHistory``: po jednym wierszu per tenant
per counter_type per dzień; idempotentny (istniejące snapshoty na dziś
pomijane). Wzorzec mockowania: test_cleanup_tasks.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.usage import CounterType, UsageCounter


def _counter(tenant_id, counter_type: CounterType, value: int, *, stale: bool = False) -> UsageCounter:
    now = datetime.now(UTC)
    if stale:
        start, end = now - timedelta(days=60), now - timedelta(days=30)
    else:
        start, end = now - timedelta(days=5), now + timedelta(days=25)
    return UsageCounter(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        counter_type=counter_type,
        value=value,
        limit_value=10,
        period_start=start,
        period_end=end,
    )


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _mock_session_ctx(mock_session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestUsageSnapshotImpl:
    @patch("app.core.database.task_session")
    async def test_snapshotuje_wszystkie_typy_dla_kazdego_tenanta(self, mock_ses_factory):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        mock_ses_factory.return_value = _mock_session_ctx(session)

        tid = uuid.uuid4()
        counters = [
            _counter(tid, CounterType.ANALYSES, 7),
            _counter(tid, CounterType.TEST_CASES, 30),
            _counter(tid, CounterType.STORAGE_BYTES, 1024),
        ]
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(),  # SET LOCAL RLS
                _scalars([tid]),  # select(Tenant.id)
                _scalars(counters),  # select(UsageCounter)
                _scalars([]),  # select(UsageHistory) na dziś
            ]
        )

        from app.workers.tasks.usage_snapshot import _usage_snapshot_impl

        stats = await _usage_snapshot_impl()

        # 4 typy liczników (3 z wierszami + files_per_analysis bez wiersza → 0)
        assert stats == {"tenants": 1, "snapshots": 4, "skipped": 0}
        assert session.add.call_count == 4
        added_types = {c.counter_type for c in [call.args[0] for call in session.add.call_args_list]}
        assert added_types == set(CounterType)
        values = {c.counter_type: c.value for c in [call.args[0] for call in session.add.call_args_list]}
        assert values[CounterType.ANALYSES] == 7
        assert values[CounterType.FILES_PER_ANALYSIS] == 0
        # Task stempluje datę UTC (datetime.now(UTC).date()); asercja po
        # lokalnym date.today() psuje się między 00:00 a 02:00 CEST (flake
        # wykryty w regresji 7.12). Porównujemy z tą samą datą UTC.
        today_utc = datetime.now(UTC).date()
        assert all(c.snapshot_date == today_utc for c in [call.args[0] for call in session.add.call_args_list])
        session.commit.assert_awaited_once()

    @patch("app.core.database.task_session")
    async def test_idempotentny_pomija_istniejace_snapshoty(self, mock_ses_factory):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        mock_ses_factory.return_value = _mock_session_ctx(session)

        tid = uuid.uuid4()
        existing = MagicMock()
        existing.tenant_id = tid
        existing.counter_type = CounterType.ANALYSES
        existing.snapshot_date = datetime.now(UTC).date()  # UTC — jak w tasku (flake 00:00-02:00 CEST)
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _scalars([tid]),
                _scalars([_counter(tid, CounterType.ANALYSES, 7)]),
                _scalars([existing]),
            ]
        )

        from app.workers.tasks.usage_snapshot import _usage_snapshot_impl

        stats = await _usage_snapshot_impl()

        added_types = [c.counter_type for c in [call.args[0] for call in session.add.call_args_list]]
        assert CounterType.ANALYSES not in added_types  # już istnieje na dziś
        assert stats["skipped"] == 1
        assert stats["snapshots"] == 3  # pozostałe 3 typy

    @patch("app.core.database.task_session")
    async def test_licznik_starego_okresu_snapshotowany_jako_zero(self, mock_ses_factory):
        """Miesięczne typy poza okresem → 0 (reset na nowy okres, semantyka _current_value)."""
        session = AsyncMock()
        session.add = MagicMock()
        mock_ses_factory.return_value = _mock_session_ctx(session)

        tid = uuid.uuid4()
        session.execute = AsyncMock(
            side_effect=[
                MagicMock(),
                _scalars([tid]),
                _scalars([_counter(tid, CounterType.ANALYSES, 9, stale=True)]),
                _scalars([]),
            ]
        )

        from app.workers.tasks.usage_snapshot import _usage_snapshot_impl

        await _usage_snapshot_impl()

        values = {c.counter_type: c.value for c in [call.args[0] for call in session.add.call_args_list]}
        assert values[CounterType.ANALYSES] == 0

    @patch("app.core.database.task_session")
    async def test_brak_tenantow_bez_zapisow(self, mock_ses_factory):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        mock_ses_factory.return_value = _mock_session_ctx(session)
        session.execute = AsyncMock(side_effect=[MagicMock(), _scalars([]), _scalars([]), _scalars([])])

        from app.workers.tasks.usage_snapshot import _usage_snapshot_impl

        stats = await _usage_snapshot_impl()

        assert stats == {"tenants": 0, "snapshots": 0, "skipped": 0}
        session.add.assert_not_called()


class TestBeatSchedule:
    def test_zadanie_w_harmonogramie_codziennie_o_polnocy(self):
        from celery.schedules import crontab

        from app.workers.celery_app import celery_app

        entry = celery_app.conf.beat_schedule.get("billing-usage-snapshot-daily")
        assert entry is not None
        assert entry["task"] == "app.workers.tasks.usage_snapshot.run_usage_snapshot"
        assert entry["schedule"] == crontab(hour=0, minute=0)
