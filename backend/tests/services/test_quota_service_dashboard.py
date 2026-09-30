"""Testy QuotaService — dashboard zużycia (Story 7.9, Task 6.1; AC1/AC4/AC5).

``get_dashboard_data`` / ``calculate_forecast`` / ``get_usage_history``.
Wzorzec mockowania: test_quota_service (subskrypcja + plan efektywny
zamockowane; DB mockowana).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.models.usage import CounterType, UsageCounter
from app.models.usage_history import UsageHistory
from app.services.billing.quota_service import QuotaService

FREEMIUM_FEATURES = {
    "analyses": 10,
    "test_cases": 50,
    "storage_bytes": 500 * 1024 * 1024,
    "files_per_analysis": 5,
}
PREMIUM_FEATURES = {
    "analyses": None,
    "test_cases": None,
    "storage_bytes": 10 * 1024 * 1024 * 1024,
    "files_per_analysis": 50,
}


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
        display_name=name.value.capitalize(),
        currency="PLN",
        features=features,
    )


def _counter(tenant_id, counter_type: CounterType, value: int, limit: int) -> UsageCounter:
    now = datetime.now(UTC)
    return UsageCounter(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        counter_type=counter_type,
        value=value,
        limit_value=limit,
        period_start=now - timedelta(days=10),
        period_end=now + timedelta(days=20),
    )


def _history_row(tenant_id, counter_type: CounterType, value: int, day: date) -> UsageHistory:
    return UsageHistory(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        counter_type=counter_type,
        value=value,
        snapshot_date=day,
        period_start=day.replace(day=1),
        period_end=day.replace(day=28),
    )


def _history_rows(tenant_id, counter_type: CounterType, values: list[int], end: date) -> list[UsageHistory]:
    """Ciągłe daily snapshoty: ostatni w ``end``, idąc wstecz po 1 dniu."""
    return [
        _history_row(tenant_id, counter_type, v, end - timedelta(days=len(values) - 1 - i))
        for i, v in enumerate(values)
    ]


def _subscription_mock(period_days_remaining: int = 20) -> MagicMock:
    sub = MagicMock()
    sub.current_period_start = datetime.now(UTC) - timedelta(days=10)
    # +5 min marginesu: (end - now).days nie ucina się o mikrosekundy wykonania.
    sub.current_period_end = datetime.now(UTC) + timedelta(days=period_days_remaining, minutes=5)
    return sub


def _svc(db, plan: SubscriptionPlan | None, sub: MagicMock | None) -> QuotaService:
    """QuotaService z zamockowanym SubscriptionService (subskrypcja + plan efektywny)."""
    svc = QuotaService(db)
    subs = MagicMock()
    subs.get_current_subscription = AsyncMock(return_value=sub)
    subs.get_effective_plan = AsyncMock(return_value=plan)
    svc._subs = subs
    return svc


class TestGetDashboardData:
    async def test_zwraca_okres_plan_liczniki_i_dni(self):
        db = _db()
        tid = uuid.uuid4()
        sub = _subscription_mock(period_days_remaining=20)
        counters = [
            _counter(tid, CounterType.ANALYSES, 7, 10),
            _counter(tid, CounterType.TEST_CASES, 30, 50),
        ]
        # get_usage → select(UsageCounter); forecast (analyses) → select(UsageHistory)
        db.execute = AsyncMock(side_effect=[_scalars(counters), _scalars([])])
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES), sub)

        data = await svc.get_dashboard_data(tid)

        assert data.plan == "freemium"
        assert data.days_remaining == 20
        assert data.current_period_start == sub.current_period_start
        assert data.current_period_end == sub.current_period_end
        by_type = {c.counter_type: c for c in data.counters}
        assert set(by_type) == set(CounterType)  # 4 zasoby, bez users (AC1)
        assert by_type[CounterType.ANALYSES].value == 7
        assert by_type[CounterType.ANALYSES].limit == 10
        assert by_type[CounterType.ANALYSES].percentage == 70.0
        assert by_type[CounterType.FILES_PER_ANALYSIS].value == 0
        assert data.forecast is None  # brak snapshotów — prognoza dopiero po 7 dniach (AC4)

    async def test_unlimited_limit_none_percentage_none(self):
        db = _db()
        db.execute = AsyncMock(side_effect=[_scalars([]), _scalars([])])
        svc = _svc(db, _plan(PlanName.PREMIUM, PREMIUM_FEATURES), _subscription_mock())

        data = await svc.get_dashboard_data(uuid.uuid4())

        analyses = {c.counter_type: c for c in data.counters}[CounterType.ANALYSES]
        assert analyses.limit is None
        assert analyses.percentage is None

    async def test_brak_subskrypcji_404(self):
        svc = _svc(_db(), None, None)
        with pytest.raises(NotFoundError):
            await svc.get_dashboard_data(uuid.uuid4())

    async def test_forecast_dolaczony_gdy_dostepny(self):
        db = _db()
        tid = uuid.uuid4()
        sub = _subscription_mock(period_days_remaining=20)
        today = datetime.now(UTC).date()
        # 10 dni po 1 analizie/dzień: 0..9; limit 10 → prognoza przed końcem okresu
        rows = _history_rows(tid, CounterType.ANALYSES, list(range(10)), today)
        db.execute = AsyncMock(side_effect=[_scalars([]), _scalars(rows)])
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES), sub)

        data = await svc.get_dashboard_data(tid)

        assert data.forecast is not None
        assert data.forecast.exceeds_before_period_end is True


class TestCalculateForecast:
    async def test_ekstrapolacja_liniowa(self):
        """avg = (9-0)/9 dni = 1/dzień; remaining 1 → limit jutro (AC4)."""
        db = _db()
        tid = uuid.uuid4()
        today = datetime.now(UTC).date()
        rows = _history_rows(tid, CounterType.ANALYSES, list(range(10)), today)
        db.execute = AsyncMock(return_value=_scalars(rows))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES), _subscription_mock())

        forecast = await svc.calculate_forecast(tid, CounterType.ANALYSES)

        assert forecast is not None
        assert forecast.avg_daily == pytest.approx(1.0)
        assert forecast.limit_date == today + timedelta(days=1)
        assert forecast.days_to_limit == 1

    async def test_mniej_niz_7_dni_none(self):
        db = _db()
        tid = uuid.uuid4()
        rows = _history_rows(tid, CounterType.ANALYSES, [0, 1, 2], datetime.now(UTC).date())
        db.execute = AsyncMock(return_value=_scalars(rows))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES), _subscription_mock())

        assert await svc.calculate_forecast(tid, CounterType.ANALYSES) is None

    async def test_unlimited_none(self):
        db = _db()
        tid = uuid.uuid4()
        rows = _history_rows(tid, CounterType.ANALYSES, list(range(10)), datetime.now(UTC).date())
        db.execute = AsyncMock(return_value=_scalars(rows))
        svc = _svc(db, _plan(PlanName.PREMIUM, PREMIUM_FEATURES), _subscription_mock())

        assert await svc.calculate_forecast(tid, CounterType.ANALYSES) is None

    async def test_brak_wzrostu_none(self):
        db = _db()
        tid = uuid.uuid4()
        rows = _history_rows(tid, CounterType.ANALYSES, [3] * 10, datetime.now(UTC).date())
        db.execute = AsyncMock(return_value=_scalars(rows))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES), _subscription_mock())

        assert await svc.calculate_forecast(tid, CounterType.ANALYSES) is None

    async def test_prognoza_po_okresie_bez_ostrzezenia(self):
        """Limit osiągalny dopiero po końcem okresu → exceeds=False (AC4)."""
        db = _db()
        tid = uuid.uuid4()
        today = datetime.now(UTC).date()
        values = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]  # avg 0.5/dzień, used 4, remaining 6 → ~12 dni
        rows = _history_rows(tid, CounterType.ANALYSES, values, today)
        db.execute = AsyncMock(return_value=_scalars(rows))
        svc = _svc(db, _plan(PlanName.FREEMIUM, FREEMIUM_FEATURES), _subscription_mock(5))

        forecast = await svc.calculate_forecast(tid, CounterType.ANALYSES)

        assert forecast is not None
        assert forecast.exceeds_before_period_end is False

    async def test_brak_subskrypcji_none(self):
        svc = _svc(_db(), None, None)
        assert await svc.calculate_forecast(uuid.uuid4(), CounterType.ANALYSES) is None


class TestGetUsageHistory:
    async def test_punkty_rosnaco_po_dacie(self):
        db = _db()
        tid = uuid.uuid4()
        today = datetime.now(UTC).date()
        rows = list(reversed(_history_rows(tid, CounterType.TEST_CASES, [10, 20, 30], today)))
        db.execute = AsyncMock(return_value=_scalars(rows))
        svc = _svc(db, None, None)

        points = await svc.get_usage_history(tid, CounterType.TEST_CASES, days=30)

        assert [(p.date, p.value) for p in points] == [
            (today - timedelta(days=2), 10),
            (today - timedelta(days=1), 20),
            (today, 30),
        ]

    async def test_brak_danych_pusta_lista(self):
        db = _db()
        db.execute = AsyncMock(return_value=_scalars([]))
        svc = _svc(db, None, None)
        assert await svc.get_usage_history(uuid.uuid4(), CounterType.ANALYSES) == []
