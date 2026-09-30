"""Testy QuotaService (DB) — Story 7.8, Task 6.1 (AC1/AC3/AC4).

Limity czytane z ``subscription_plans.features`` (jedno źródło prawdy, 7.1).
DB mockowana (wzorzec test_plan_change); plan efektywny podawany przez
zmockowany SubscriptionService (grace/dunning testowane w 7.2).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import QuotaExceededError
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.models.usage import CounterType, UsageCounter
from app.services.billing.quota_service import UNLIMITED, QuotaService

FREEMIUM_FEATURES = {
    "analyses": 10,
    "test_cases": 50,
    "storage_bytes": 500 * 1024 * 1024,
    "files_per_analysis": 5,
    "rate_limit_per_min": 100,
}
PREMIUM_FEATURES = {
    "analyses": None,
    "test_cases": None,
    "storage_bytes": 10 * 1024 * 1024 * 1024,
    "files_per_analysis": 50,
    "rate_limit_per_min": 1000,
}


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


def _plan(name: PlanName, features: dict) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=uuid.uuid4(),
        name=name,
        display_name=name.capitalize(),
        currency="PLN",
        features=features,
    )


def _counter(tenant_id, counter_type: CounterType, value: int, limit: int, *, now=None) -> UsageCounter:
    now = now or datetime.now(UTC)
    return UsageCounter(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        counter_type=counter_type,
        value=value,
        limit_value=limit,
        period_start=now - timedelta(days=10),
        period_end=now + timedelta(days=20),
    )


def _svc(db, plan: SubscriptionPlan | None) -> QuotaService:
    """QuotaService z zamockowanym SubscriptionService (plan efektywny)."""
    svc = QuotaService(db)
    subs = MagicMock()
    subs.get_current_subscription = AsyncMock(return_value=MagicMock() if plan else None)
    subs.get_effective_plan = AsyncMock(return_value=plan)
    svc._subs = subs
    return svc


class TestCheckQuota:
    @pytest.mark.asyncio
    async def test_ponizej_limitu_zwraca_true(self):
        db = _db()
        tid = uuid.uuid4()
        db.execute.return_value = _scalar(_counter(tid, CounterType.ANALYSES, 3, 10))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        assert await svc.check_quota(tid, CounterType.ANALYSES) is True

    @pytest.mark.asyncio
    async def test_limit_osiagniety_zwraca_false(self):
        db = _db()
        tid = uuid.uuid4()
        db.execute.return_value = _scalar(_counter(tid, CounterType.ANALYSES, 10, 10))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        assert await svc.check_quota(tid, CounterType.ANALYSES) is False

    @pytest.mark.asyncio
    async def test_increment_wieksze_niz_pozostalo_zwraca_false(self):
        db = _db()
        tid = uuid.uuid4()
        db.execute.return_value = _scalar(_counter(tid, CounterType.TEST_CASES, 48, 50))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        assert await svc.check_quota(tid, CounterType.TEST_CASES, increment=3) is False
        db.execute.return_value = _scalar(_counter(tid, CounterType.TEST_CASES, 48, 50))
        assert await svc.check_quota(tid, CounterType.TEST_CASES, increment=2) is True

    @pytest.mark.asyncio
    async def test_unlimited_premium_zwraca_true(self):
        db = _db()
        svc = _svc(db, _plan(PlanName.PREMIUM, PREMIUM_FEATURES))
        assert await svc.check_quota(uuid.uuid4(), CounterType.ANALYSES, increment=999) is True
        db.execute.assert_not_awaited()  # unlimited — bez odczytu licznika

    @pytest.mark.asyncio
    async def test_brak_subskrypcji_nie_blokuje(self):
        db = _db()
        svc = _svc(db, None)
        assert await svc.check_quota(uuid.uuid4(), CounterType.ANALYSES) is True

    @pytest.mark.asyncio
    async def test_brak_licznika_liczy_od_zera(self):
        db = _db()
        db.execute.return_value = _scalar(None)
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        assert await svc.check_quota(uuid.uuid4(), CounterType.ANALYSES) is True

    @pytest.mark.asyncio
    async def test_licznik_z_poprzedniego_okresu_ignorowany(self):
        """Stary okres (period_end w przeszłości) → used = 0 (AC4)."""
        db = _db()
        tid = uuid.uuid4()
        old = datetime.now(UTC) - timedelta(days=60)
        stale = _counter(tid, CounterType.ANALYSES, 10, 10, now=old)
        db.execute.return_value = _scalar(stale)
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        assert await svc.check_quota(tid, CounterType.ANALYSES) is True

    @pytest.mark.asyncio
    async def test_files_per_analysis_stateless(self):
        """files_per_analysis — per analiza, bez licznika miesięcznego (AC3)."""
        db = _db()
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        assert await svc.check_quota(uuid.uuid4(), CounterType.FILES_PER_ANALYSIS, increment=5) is True
        assert await svc.check_quota(uuid.uuid4(), CounterType.FILES_PER_ANALYSIS, increment=6) is False
        db.execute.assert_not_awaited()


class TestEnforceQuota:
    @pytest.mark.asyncio
    async def test_429_z_wymaganym_body_ac1(self):
        db = _db()
        tid = uuid.uuid4()
        db.execute.return_value = _scalar(_counter(tid, CounterType.ANALYSES, 10, 10))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        with pytest.raises(QuotaExceededError) as exc_info:
            await svc.enforce_quota(tid, CounterType.ANALYSES)
        body = exc_info.value.to_rfc7807()
        assert body["status"] == 429
        assert body["error"] == "limit_reached"
        assert body["resource"] == "analyses"
        assert body["limit"] == 10
        assert body["current"] == 10
        assert body["plan"] == "freemium"

    @pytest.mark.asyncio
    async def test_przepuszcza_gdy_w_limicie(self):
        db = _db()
        tid = uuid.uuid4()
        db.execute.return_value = _scalar(_counter(tid, CounterType.ANALYSES, 3, 10))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        await svc.enforce_quota(tid, CounterType.ANALYSES)  # nie rzuca


class TestIncrementUsage:
    @pytest.mark.asyncio
    async def test_atomowy_update_istniejacego_licznika(self):
        db = _db()
        db.execute.return_value = MagicMock(rowcount=1)
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        await svc.increment_usage(uuid.uuid4(), CounterType.ANALYSES)
        stmt = db.execute.await_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "UPDATE usage_counters" in compiled
        assert "value + " in compiled  # AC3: value = value + :v
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_brak_licznika_tworzy_nowy_wiersz(self):
        db = _db()
        db.execute.return_value = MagicMock(rowcount=0)
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        tid = uuid.uuid4()
        await svc.increment_usage(tid, CounterType.ANALYSES, value=2)
        db.add.assert_called_once()
        counter = db.add.call_args.args[0]
        assert isinstance(counter, UsageCounter)
        assert counter.tenant_id == tid
        assert counter.counter_type == CounterType.ANALYSES
        assert counter.value == 2
        assert counter.limit_value == 10

    @pytest.mark.asyncio
    async def test_nowy_wiersz_unlimited_ma_sentinel(self):
        db = _db()
        db.execute.return_value = MagicMock(rowcount=0)
        svc = _svc(db, _plan(PlanName.PREMIUM, PREMIUM_FEATURES))
        await svc.increment_usage(uuid.uuid4(), CounterType.ANALYSES)
        counter = db.add.call_args.args[0]
        assert counter.limit_value == UNLIMITED

    @pytest.mark.asyncio
    async def test_storage_dodaje_rozmiar_pliku(self):
        db = _db()
        db.execute.return_value = MagicMock(rowcount=1)
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        await svc.increment_usage(uuid.uuid4(), CounterType.STORAGE_BYTES, value=1024)
        stmt = db.execute.await_args.args[0]
        assert "UPDATE usage_counters" in str(stmt.compile())


class TestCheckStorageLimit:
    @pytest.mark.asyncio
    async def test_w_limicie_true(self):
        db = _db()
        tid = uuid.uuid4()
        limit = FREEMIUM_FEATURES["storage_bytes"]
        db.execute.return_value = _scalar(_counter(tid, CounterType.STORAGE_BYTES, 400 * 1024 * 1024, limit))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        assert await svc.check_storage_limit(tid, 50 * 1024 * 1024) is True

    @pytest.mark.asyncio
    async def test_przekroczenie_false(self):
        db = _db()
        tid = uuid.uuid4()
        limit = FREEMIUM_FEATURES["storage_bytes"]
        db.execute.return_value = _scalar(_counter(tid, CounterType.STORAGE_BYTES, 400 * 1024 * 1024, limit))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        assert await svc.check_storage_limit(tid, 200 * 1024 * 1024) is False

    @pytest.mark.asyncio
    async def test_storage_kumulatywny_stary_okres_liczony(self):
        """Storage NIE zeruje się z okresem — stary wiersz nadal się liczy (AC4)."""
        db = _db()
        tid = uuid.uuid4()
        old = datetime.now(UTC) - timedelta(days=60)
        limit = FREEMIUM_FEATURES["storage_bytes"]
        stale = _counter(tid, CounterType.STORAGE_BYTES, 450 * 1024 * 1024, limit, now=old)
        db.execute.return_value = _scalar(stale)
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        assert await svc.check_storage_limit(tid, 100 * 1024 * 1024) is False


class TestKolumnyLicznikowBigint:
    """Regresja 2026-09-29: limit storage planu w bajtach (10 GiB) nie mieści
    się w int32 — INSERT licznika ``storage_bytes`` kończył się błędem asyncpg
    ``value out of int32 range`` i każdy upload pliku zwracał 500.

    Te testy trzymają typ kolumn modelu na BIGINT (kolumny w bazie zmienia
    migracja 059); mockowana DB nie zobaczy overflowu, więc strażnikiem
    jest asercja typu na metadanych SQLAlchemy. Tej samej klasy ryzyko
    domykamy w ``usage_history.value`` (snapshot storage) i
    ``notifications.current_value``/``limit_value`` (progi 80/90/100).
    """

    TEN_GIB = 10 * 1024 * 1024 * 1024  # 10 737 418 240 > int32 max (2 147 483 647)

    def test_value_i_limit_value_sa_bigint(self):
        from sqlalchemy import BigInteger

        columns = UsageCounter.__table__.columns
        assert isinstance(columns["value"].type, BigInteger)
        assert isinstance(columns["limit_value"].type, BigInteger)

    def test_usage_history_value_jest_bigint(self):
        from sqlalchemy import BigInteger

        from app.models.usage_history import UsageHistory

        assert isinstance(UsageHistory.__table__.columns["value"].type, BigInteger)

    def test_notifications_wartosci_limitow_sa_bigint(self):
        from sqlalchemy import BigInteger

        from app.models.notification import Notification

        columns = Notification.__table__.columns
        assert isinstance(columns["current_value"].type, BigInteger)
        assert isinstance(columns["limit_value"].type, BigInteger)

    def test_licznik_przyjmuje_limit_10_gib(self):
        counter = _counter(uuid.uuid4(), CounterType.STORAGE_BYTES, 0, self.TEN_GIB)
        assert counter.limit_value == self.TEN_GIB


class TestResetCounters:
    @pytest.mark.asyncio
    async def test_zeruje_liczniki_zachowuje_storage_i_loguje_audit(self):
        db = _db()
        tid = uuid.uuid4()
        analyses = _counter(tid, CounterType.ANALYSES, 7, 10)
        test_cases = _counter(tid, CounterType.TEST_CASES, 30, 50)
        storage = _counter(tid, CounterType.STORAGE_BYTES, 123456, 500 * 1024 * 1024)
        db.execute.return_value = _scalars([analyses, test_cases, storage])
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))

        new_start = datetime(2026, 10, 1, tzinfo=UTC)
        new_end = datetime(2026, 11, 1, tzinfo=UTC)
        await svc.reset_counters(tid, new_start, new_end)

        assert analyses.value == 0
        assert test_cases.value == 0
        assert storage.value == 123456  # AC4: storage kumulatywny
        for c in (analyses, test_cases, storage):
            assert c.period_start == new_start
            assert c.period_end == new_end

        # AC4: reset logowany w audit log
        from app.models.audit_log import AuditLog

        audit_entries = [a.args[0] for a in db.add.call_args_list if isinstance(a.args[0], AuditLog)]
        assert len(audit_entries) == 1
        assert audit_entries[0].tenant_id == tid
        assert "reset" in audit_entries[0].action


class TestGetUsage:
    @pytest.mark.asyncio
    async def test_zwraca_liczniki_z_limitami_i_procentem(self):
        db = _db()
        tid = uuid.uuid4()
        analyses = _counter(tid, CounterType.ANALYSES, 5, 10)
        db.execute.return_value = _scalars([analyses])
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))

        usage = await svc.get_usage(tid)
        assert usage["analyses"]["used"] == 5
        assert usage["analyses"]["limit"] == 10
        assert usage["analyses"]["percent"] == 50.0
        # brak wiersza → 0 użycia, limit z planu
        assert usage["test_cases"]["used"] == 0
        assert usage["test_cases"]["limit"] == 50
        assert usage["test_cases"]["percent"] == 0.0

    @pytest.mark.asyncio
    async def test_unlimited_ma_limit_none_i_percent_none(self):
        db = _db()
        db.execute.return_value = _scalars([])
        svc = _svc(db, _plan(PlanName.PREMIUM, PREMIUM_FEATURES))
        usage = await svc.get_usage(uuid.uuid4())
        assert usage["analyses"]["limit"] is None
        assert usage["analyses"]["percent"] is None


class TestGetPlanLimits:
    @pytest.mark.asyncio
    async def test_limity_z_features_jsonb(self):
        db = _db()
        db.execute.return_value = _scalar(_plan(PlanName.FREEMIUM, FREEMIUM_FEATURES))
        svc = QuotaService(db)
        limits = await svc._get_plan_limits(PlanName.FREEMIUM)
        assert limits["analyses"] == 10
        assert limits["test_cases"] == 50
        assert limits["storage_bytes"] == 500 * 1024 * 1024
        assert limits["files_per_analysis"] == 5
        assert limits["rate_limit_per_min"] == 100

    @pytest.mark.asyncio
    async def test_nieznany_plan_zwraca_pusty_dict(self):
        db = _db()
        db.execute.return_value = _scalar(None)
        svc = QuotaService(db)
        assert await svc._get_plan_limits(PlanName.PREMIUM) == {}
