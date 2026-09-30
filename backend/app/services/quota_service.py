"""Quota service — analysis limit checking per tenant plan.

Uses Redis counters with monthly keys:
  ``tenant:{tenant_id}:analysis_count:{YYYY-MM}``

Źródło prawdy limitów: ``subscription_plans.features`` (JSONB, Story 7.1) —
QuotaService czyta je przez procesowy cache zasilany przy seedzie/startupie
(``set_plan_limits_cache``). Wartości poniżej to wyłącznie fallback awaryjny
(cache pusty, np. start bez DB).

Model 3-planowy (CR#2): Freemium 10 / Basic 50 / Premium unlimited.
``None`` w limicie oznacza unlimited (bez egzekwowania progu).

Counter auto-expires at end of billing month (Celery Beat resets on 1st).
"""

import logging
import uuid
from datetime import UTC, datetime

import redis

from app.core.config import get_settings
from app.core.exceptions import QuotaExceededError
from app.models.tenant import PlanType

logger = logging.getLogger(__name__)

# Fallback awaryjny — gdy cache z DB nie został jeszcze zasilany.
FALLBACK_ANALYSIS_LIMITS: dict[PlanType, int | None] = {
    PlanType.FREEMIUM: 10,
    PlanType.BASIC: 50,
    PlanType.PREMIUM: None,  # unlimited
}

COUNTER_TTL_SECONDS = 31 * 86400  # ~1 month

# Cache procesowy: plan → limit analiz (None = unlimited). Zasilany z
# subscription_plans.features przy seedzie (startup) — jedno źródło prawdy.
_plan_limits_cache: dict[PlanType, int | None] = {}


def set_plan_limits_cache(limits: dict[PlanType, int | None]) -> None:
    """Zasil cache limitów z subscription_plans.features (DB)."""
    _plan_limits_cache.clear()
    _plan_limits_cache.update(limits)


def clear_plan_limits_cache() -> None:
    _plan_limits_cache.clear()


def get_analysis_limit(plan: PlanType) -> int | None:
    """Limit analiz/mies. dla planu; None = unlimited."""
    if plan in _plan_limits_cache:
        return _plan_limits_cache[plan]
    return FALLBACK_ANALYSIS_LIMITS.get(plan)


class QuotaService:
    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client

    @property
    def redis(self) -> redis.Redis:
        if self._redis is None:
            settings = get_settings()
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _counter_key(self, tenant_id: uuid.UUID) -> str:
        now = datetime.now(UTC)
        return f"tenant:{tenant_id}:analysis_count:{now.strftime('%Y-%m')}"

    def check_analysis_quota(self, tenant_id: uuid.UUID, plan: PlanType) -> bool:
        limit = get_analysis_limit(plan)
        if limit is None:  # unlimited
            return True
        key = self._counter_key(tenant_id)
        raw = self.redis.get(key)
        used = int(raw) if raw is not None else 0

        if used >= limit:
            raise QuotaExceededError(
                detail=f"Monthly analysis limit ({limit}) reached for plan {plan.value}",
                limit=limit,
                used=used,
                plan=plan.value,
                upgrade_url="/billing/plans",
                retry_after=self._seconds_until_next_month(),
            )
        return True

    def increment_usage(self, tenant_id: uuid.UUID) -> int:
        key = self._counter_key(tenant_id)
        count = self.redis.incr(key)
        if count == 1:
            self.redis.expire(key, COUNTER_TTL_SECONDS)
        return count

    def check_and_reserve(self, tenant_id: uuid.UUID, plan: PlanType) -> int:
        """Atomic quota check + increment — eliminates TOCTOU race condition.

        Increments counter first (atomic INCR), then checks limit.
        If over limit, rolls back with DECR and raises QuotaExceededError.
        """
        limit = get_analysis_limit(plan)
        key = self._counter_key(tenant_id)

        count = self.redis.incr(key)
        if count == 1:
            self.redis.expire(key, COUNTER_TTL_SECONDS)

        if limit is not None and count > limit:
            self.redis.decr(key)
            raise QuotaExceededError(
                detail=f"Monthly analysis limit ({limit}) reached for plan {plan.value}",
                limit=limit,
                used=count - 1,
                plan=plan.value,
                upgrade_url="/billing/plans",
                retry_after=self._seconds_until_next_month(),
            )
        return count

    def get_usage(self, tenant_id: uuid.UUID, plan: PlanType) -> dict:
        """Read-only usage snapshot for dashboard plan-usage widget.

        Returns dict with: plan, analyses_used, analyses_limit.
        Does not increment counter — safe for frequent reads.
        """
        limit = get_analysis_limit(plan)
        key = self._counter_key(tenant_id)
        raw = self.redis.get(key)
        used = int(raw) if raw is not None else 0
        return {
            "plan": plan.value,
            "analyses_used": used,
            "analyses_limit": limit,
        }

    @staticmethod
    def _seconds_until_next_month() -> int:
        now = datetime.now(UTC)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        delta = next_month - now
        return int(delta.total_seconds())


def get_quota_service() -> QuotaService:
    return QuotaService()
