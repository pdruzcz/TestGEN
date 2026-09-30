"""QuotaService (DB) — egzekwowanie limitów per plan (Story 7.8, AC1/AC3/AC4)
+ dashboard zużycia, prognoza i historia (Story 7.9, AC1/AC4/AC5).

Jedno źródło prawdy limitów: ``subscription_plans.features`` (JSONB, 7.1).
Liczniki w ``usage_counters``; inkrementacja atomowa
(``UPDATE ... SET value = value + :v``). Plan efektywny (grace po downgrade,
7.2 AC6) rozstrzyga SubscriptionService.

Zasady per typ licznika:
- ``analyses``/``test_cases`` — okno miesięczne, zerowane na nowy okres (AC4);
- ``storage_bytes`` — kumulatywny, NIE zerowany (AC4);
- ``files_per_analysis`` — per analiza (stateless — porównanie liczby plików
  żądania z limitem planu, bez wiersza miesięcznego).
"""

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, QuotaExceededError
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.models.usage import CounterType, UsageCounter
from app.models.usage_history import UsageHistory
from app.services.billing.subscription_service import (
    _COUNTER_FEATURE_KEYS,
    SubscriptionService,
    _month_window,
)

logger = logging.getLogger(__name__)

# Sentinel „bez limitu" w kolumnie NOT NULL ``limit_value`` (Premium: None w features).
UNLIMITED = -1


# --- Story 7.9: dane dashboardu zużycia (AC1/AC5) ---


@dataclass(frozen=True)
class UsageDataPoint:
    """Punkt wykresu historii (AC3) — skumulowane zużycie na dzień."""

    date: date
    value: int


@dataclass(frozen=True)
class DashboardCounter:
    """Pojedynczy zasob na karcie dashboardu; ``limit``/``percentage`` None = unlimited."""

    counter_type: CounterType
    value: int
    limit: int | None
    percentage: float | None


@dataclass(frozen=True)
class ForecastData:
    """Prognoza osiągnięcia limitu (AC4) — ekstrapolacja ze snapshotów."""

    counter_type: CounterType
    limit_date: date
    avg_daily: float
    days_to_limit: int
    exceeds_before_period_end: bool


@dataclass(frozen=True)
class DashboardData:
    """Agregat GET /billing/usage/dashboard (AC5)."""

    current_period_start: datetime
    current_period_end: datetime
    plan: str | None
    counters: list[DashboardCounter] = field(default_factory=list)
    forecast: ForecastData | None = None
    days_remaining: int = 0


class QuotaService:
    """Sprawdzanie i inkrementacja limitów zasobów per tenant (AC1/AC3)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._subs = SubscriptionService(db)

    # --- limity planu (AC1) ---

    async def _get_effective_plan(self, tenant_id: uuid.UUID) -> SubscriptionPlan | None:
        subscription = await self._subs.get_current_subscription(tenant_id)
        if subscription is None:
            return None
        return await self._subs.get_effective_plan(subscription)

    async def _get_plan_limits(self, plan_name: PlanName) -> dict:
        """Limity z ``subscription_plans.features`` (JSONB) — bez hardkodu."""
        result = await self._db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == plan_name))
        plan = result.scalar_one_or_none()
        if plan is None:
            return {}
        return dict(plan.features or {})

    # --- odczyt liczników ---

    async def _current_value(self, tenant_id: uuid.UUID, counter_type: CounterType, now: datetime) -> int:
        """Aktualne zużycie: ostatni wiersz licznika; poza okresem → 0
        (storage kumulatywny — okres bez znaczenia, AC4)."""
        result = await self._db.execute(
            select(UsageCounter)
            .where(
                UsageCounter.tenant_id == tenant_id,
                UsageCounter.counter_type == counter_type,
            )
            .order_by(UsageCounter.period_start.desc())
            .limit(1)
        )
        counter = result.scalar_one_or_none()
        if counter is None:
            return 0
        if counter_type != CounterType.STORAGE_BYTES and not (counter.period_start <= now < counter.period_end):
            return 0  # stary okres — licznik czeka na reset (AC4)
        return counter.value

    # --- API serwisu (Task 1.1) ---

    async def check_quota(self, tenant_id: uuid.UUID, counter_type: CounterType, increment: int = 1) -> bool:
        """Czy operacja zużywająca ``increment`` jednostek mieści się w limicie (AC1)."""
        allowed, _, _, _ = await self._evaluate(tenant_id, counter_type, increment)
        return allowed

    async def enforce_quota(self, tenant_id: uuid.UUID, counter_type: CounterType, increment: int = 1) -> None:
        """Jak ``check_quota``, ale przy przekroczeniu rzuca 429 z body AC1:
        ``{"error": "limit_reached", "resource", "limit", "current", "plan"}``."""
        allowed, limit, current, plan = await self._evaluate(tenant_id, counter_type, increment)
        if allowed:
            return
        raise QuotaExceededError(
            detail=f"Limit zasobu '{counter_type.value}' osiągnięty w planie {plan}",
            error="limit_reached",
            resource=counter_type.value,
            limit=limit,
            current=current,
            plan=plan,
            upgrade_url="/billing/plans",
        )

    async def _evaluate(
        self, tenant_id: uuid.UUID, counter_type: CounterType, increment: int
    ) -> tuple[bool, int | None, int, str | None]:
        """(allowed, limit, current, plan) — wspólna logika check/enforce."""
        plan = await self._get_effective_plan(tenant_id)
        if plan is None:
            return True, None, 0, None  # brak subskrypcji → nie blokujemy (7.2 dunning)

        limit = (plan.features or {}).get(_COUNTER_FEATURE_KEYS[counter_type])
        plan_name = plan.name.value if hasattr(plan.name, "value") else str(plan.name)
        if limit is None:
            return True, None, 0, plan_name  # unlimited

        if counter_type == CounterType.FILES_PER_ANALYSIS:
            # Per analiza — bez licznika miesięcznego: liczba plików żądania vs limit.
            return increment <= limit, limit, increment, plan_name

        current = await self._current_value(tenant_id, counter_type, datetime.now(UTC))
        return current + increment <= limit, limit, current, plan_name

    async def increment_usage(self, tenant_id: uuid.UUID, counter_type: CounterType, value: int = 1) -> None:
        """Atomowa inkrementacja licznika (AC3): ``UPDATE ... value = value + :v``.

        Brak wiersza bieżącego okresu → utworzenie nowego (okno miesięczne,
        limit z planu; unlimited → sentinel ``UNLIMITED``).
        """
        now = datetime.now(UTC)
        conditions = [
            UsageCounter.tenant_id == tenant_id,
            UsageCounter.counter_type == counter_type,
        ]
        if counter_type != CounterType.STORAGE_BYTES:
            conditions += [UsageCounter.period_start <= now, UsageCounter.period_end > now]
        result = await self._db.execute(
            update(UsageCounter).where(*conditions).values(value=UsageCounter.value + value)
        )
        if result.rowcount:
            return

        plan = await self._get_effective_plan(tenant_id)
        limit = (plan.features or {}).get(_COUNTER_FEATURE_KEYS[counter_type]) if plan else None
        period_start, period_end = _month_window(now)
        self._db.add(
            UsageCounter(
                tenant_id=tenant_id,
                counter_type=counter_type,
                value=value,
                limit_value=limit if limit is not None else UNLIMITED,
                period_start=period_start,
                period_end=period_end,
            )
        )
        await self._db.flush()

    async def check_storage_limit(self, tenant_id: uuid.UUID, additional_bytes: int) -> bool:
        """Storage kumulatywny (AC4) — czy zmieści się ``additional_bytes``."""
        return await self.check_quota(tenant_id, CounterType.STORAGE_BYTES, increment=additional_bytes)

    async def get_usage(self, tenant_id: uuid.UUID) -> dict:
        """Wszystkie liczniki z limitami planu i procentem wykorzystania (Task 4)."""
        now = datetime.now(UTC)
        plan = await self._get_effective_plan(tenant_id)
        features = dict(plan.features or {}) if plan else {}

        result = await self._db.execute(select(UsageCounter).where(UsageCounter.tenant_id == tenant_id))
        rows = list(result.scalars().all())
        by_type: dict[CounterType, UsageCounter] = {}
        for row in sorted(rows, key=lambda c: c.period_start):
            by_type[row.counter_type] = row  # ostatni okres wygrywa

        usage: dict[str, dict] = {}
        for counter_type, feature_key in _COUNTER_FEATURE_KEYS.items():
            limit = features.get(feature_key)
            row = by_type.get(counter_type)
            used = 0
            if row is not None and (
                counter_type == CounterType.STORAGE_BYTES or row.period_start <= now < row.period_end
            ):
                used = row.value
            percent = round(used / limit * 100, 1) if limit else None
            usage[counter_type.value] = {"used": used, "limit": limit, "percent": percent}
        return usage

    # --- Story 7.9: dashboard zużycia, prognoza, historia (AC1/AC4/AC5) ---

    async def get_dashboard_data(self, tenant_id: uuid.UUID) -> DashboardData:
        """Agregat dashboardu (AC1/AC5): okres, plan, liczniki, prognoza, dni."""
        subscription = await self._subs.get_current_subscription(tenant_id)
        if subscription is None:
            raise NotFoundError("Subscription not found")

        plan = await self._subs.get_effective_plan(subscription)
        usage = await self.get_usage(tenant_id)

        counters = [
            DashboardCounter(
                counter_type=counter_type,
                value=entry["used"],
                limit=entry["limit"],
                percentage=entry["percent"],
            )
            for counter_type, entry in ((counter_type, usage[counter_type.value]) for counter_type in CounterType)
        ]

        now = datetime.now(UTC)
        days_remaining = max((subscription.current_period_end - now).days, 0)
        forecast = await self.calculate_forecast(tenant_id, CounterType.ANALYSES)

        return DashboardData(
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            plan=plan.name.value
            if plan is not None and hasattr(plan.name, "value")
            else (str(plan.name) if plan else None),
            counters=counters,
            forecast=forecast,
            days_remaining=days_remaining,
        )

    async def calculate_forecast(self, tenant_id: uuid.UUID, counter_type: CounterType) -> ForecastData | None:
        """Prognoza daty osiągnięcia limitu (AC4) — ekstrapolacja liniowa:
        ``remaining / avg_daily_usage = days_to_limit`` ze snapshotów
        ``UsageHistory`` bieżącego okresu. Wymaga ≥ 7 snapshotów (AC4);
        ``None`` gdy brak danych / wzrostu / limitu (unlimited).
        """
        subscription = await self._subs.get_current_subscription(tenant_id)
        if subscription is None:
            return None
        plan = await self._subs.get_effective_plan(subscription)
        if plan is None:
            return None
        limit = (plan.features or {}).get(_COUNTER_FEATURE_KEYS[counter_type])
        if limit is None:
            return None  # unlimited — bez prognozy

        today = datetime.now(UTC).date()
        result = await self._db.execute(
            select(UsageHistory)
            .where(
                UsageHistory.tenant_id == tenant_id,
                UsageHistory.counter_type == counter_type,
                UsageHistory.snapshot_date >= subscription.current_period_start.date(),
                UsageHistory.snapshot_date <= today,
            )
            .order_by(UsageHistory.snapshot_date.asc())
        )
        points = sorted(result.scalars().all(), key=lambda h: h.snapshot_date)
        if len(points) < 7:
            return None

        first, last = points[0], points[-1]
        dayspan = (last.snapshot_date - first.snapshot_date).days
        if dayspan <= 0:
            return None
        avg_daily = (last.value - first.value) / dayspan
        if avg_daily <= 0:
            return None  # brak wzrostu — limit nie zostanie osiągnięty

        remaining = max(limit - last.value, 0)
        days_to_limit = math.ceil(remaining / avg_daily)
        limit_date = last.snapshot_date + timedelta(days=days_to_limit)
        return ForecastData(
            counter_type=counter_type,
            limit_date=limit_date,
            avg_daily=avg_daily,
            days_to_limit=days_to_limit,
            exceeds_before_period_end=limit_date <= subscription.current_period_end.date(),
        )

    async def get_usage_history(
        self, tenant_id: uuid.UUID, counter_type: CounterType, days: int = 30
    ) -> list[UsageDataPoint]:
        """Daily snapshoty do wykresu (AC3) — rosnąco po dacie, okno ``days`` dni."""
        cutoff = datetime.now(UTC).date() - timedelta(days=days - 1)
        result = await self._db.execute(
            select(UsageHistory)
            .where(
                UsageHistory.tenant_id == tenant_id,
                UsageHistory.counter_type == counter_type,
                UsageHistory.snapshot_date >= cutoff,
            )
            .order_by(UsageHistory.snapshot_date.asc())
        )
        rows = sorted(result.scalars().all(), key=lambda h: h.snapshot_date)
        return [UsageDataPoint(date=row.snapshot_date, value=row.value) for row in rows]

    async def reset_counters(
        self,
        tenant_id: uuid.UUID,
        new_period_start: datetime,
        new_period_end: datetime,
        *,
        user_id: uuid.UUID | None = None,
    ) -> None:
        """Reset liczników na nowy okres rozliczeniowy (AC4).

        ``storage_bytes`` NIE jest zerowany (kumulatywny); wszystkie wiersze
        dostają nowe okno okresu. Operacja logowana w audit logu.
        """
        from app.services.admin.audit_service import log_action

        result = await self._db.execute(select(UsageCounter).where(UsageCounter.tenant_id == tenant_id))
        counters = list(result.scalars().all())
        reset_types: list[str] = []
        for counter in counters:
            if counter.counter_type != CounterType.STORAGE_BYTES:
                counter.value = 0
                reset_types.append(counter.counter_type.value)
            counter.period_start = new_period_start
            counter.period_end = new_period_end

        await log_action(
            self._db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="billing.usage_counters.reset",
            resource_type="usage_counter",
            resource_id=tenant_id,
            changes={
                "period_start": new_period_start.isoformat(),
                "period_end": new_period_end.isoformat(),
                "reset": reset_types,
                "preserved": [CounterType.STORAGE_BYTES.value],
            },
        )
        logger.info("Reset liczników tenant=%s: %s (storage zachowany)", tenant_id, reset_types)


# --- Sync API dla workerów Celery (pipeline persystuje przez sync Session) ---


def _limit_for_tenant_sync(session, tenant_id: uuid.UUID, counter_type: CounterType) -> int | None:
    """Limit z ``subscription_plans.features`` po legacy ``tenants.plan``
    (kolumna trzymana w sync z subskrypcją — subscription_service)."""
    from app.models.tenant import Tenant

    tenant_plan = session.execute(select(Tenant.plan).where(Tenant.id == tenant_id)).scalar_one_or_none()
    if tenant_plan is None:
        return None
    plan_value = tenant_plan.value if hasattr(tenant_plan, "value") else str(tenant_plan)
    plan = session.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == PlanName(plan_value))
    ).scalar_one_or_none()
    if plan is None:
        return None
    return (plan.features or {}).get(_COUNTER_FEATURE_KEYS[counter_type])


def remaining_quota_sync(session, tenant_id: uuid.UUID, counter_type: CounterType) -> int | None:
    """Ile jednostek zostało w bieżącym okresie; ``None`` = bez limitu (AC1)."""
    limit = _limit_for_tenant_sync(session, tenant_id, counter_type)
    if limit is None:
        return None
    now = datetime.now(UTC)
    counter = session.execute(
        select(UsageCounter)
        .where(UsageCounter.tenant_id == tenant_id, UsageCounter.counter_type == counter_type)
        .order_by(UsageCounter.period_start.desc())
        .limit(1)
    ).scalar_one_or_none()
    used = 0
    if counter is not None and (
        counter_type == CounterType.STORAGE_BYTES or counter.period_start <= now < counter.period_end
    ):
        used = counter.value
    return max(limit - used, 0)


def increment_usage_sync(session, tenant_id: uuid.UUID, counter_type: CounterType, value: int = 1) -> None:
    """Atomowa inkrementacja (AC3) — wariant sync dla pipeline'u Celery."""
    now = datetime.now(UTC)
    conditions = [
        UsageCounter.tenant_id == tenant_id,
        UsageCounter.counter_type == counter_type,
    ]
    if counter_type != CounterType.STORAGE_BYTES:
        conditions += [UsageCounter.period_start <= now, UsageCounter.period_end > now]
    result = session.execute(update(UsageCounter).where(*conditions).values(value=UsageCounter.value + value))
    if result.rowcount:
        return
    limit = _limit_for_tenant_sync(session, tenant_id, counter_type)
    period_start, period_end = _month_window(now)
    session.add(
        UsageCounter(
            tenant_id=tenant_id,
            counter_type=counter_type,
            value=value,
            limit_value=limit if limit is not None else UNLIMITED,
            period_start=period_start,
            period_end=period_end,
        )
    )
    session.flush()
