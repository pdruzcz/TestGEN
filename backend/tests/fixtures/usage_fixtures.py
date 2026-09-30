"""Fixtures liczników zużycia — Story 7.12 (Task 1.3).

Liczniki ``usage_counters`` na poziomach 0/50/80/90/100% limitu — wejścia
scenariuszy limitów (13-14) i progów powiadomień (7.11). Okno okresu =
bieżący miesiąc (``_month_window`` z subscription_service — to samo okno
czytają ``check_quota``/``get_usage``).
"""

import uuid
from datetime import datetime

from app.models.usage import CounterType, UsageCounter
from app.services.billing.subscription_service import _month_window

# Poziomy procentowe scenariuszy (AC13/AC12): 0/50/80/90/100%.
USAGE_LEVELS_PERCENT: tuple[int, ...] = (0, 50, 80, 90, 100)


def make_counter(
    tenant_id: uuid.UUID | None = None,
    *,
    counter_type: CounterType = CounterType.ANALYSES,
    value: int = 0,
    limit_value: int = 10,
    period: tuple[datetime, datetime] | None = None,
) -> UsageCounter:
    """Licznik w bieżącym oknie miesięcznym (domyślnie)."""
    period_start, period_end = period or _month_window(datetime.now().astimezone())
    return UsageCounter(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        counter_type=counter_type,
        value=value,
        limit_value=limit_value,
        period_start=period_start,
        period_end=period_end,
    )


def counter_at(
    percentage: int,
    *,
    limit: int = 10,
    tenant_id: uuid.UUID | None = None,
    counter_type: CounterType = CounterType.ANALYSES,
) -> UsageCounter:
    """Licznik na ``percentage``% limitu (np. 80% z 10 → value=8)."""
    value = round(limit * percentage / 100)
    return make_counter(
        tenant_id,
        counter_type=counter_type,
        value=value,
        limit_value=limit,
    )
