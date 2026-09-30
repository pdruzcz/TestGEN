"""Zadanie Celery usage_snapshot — Story 7.9 (AC3).

``run_usage_snapshot`` (beat, codziennie 00:00): snapshot wartości
wszystkich liczników każdego tenanta do ``UsageHistory`` — po jednym
wierszu per tenant per counter_type per dzień (dane wykresu historii
i prognozy). Idempotentne: istniejący snapshot na dziś pomijany
(unique ``(tenant_id, counter_type, snapshot_date)``). Kontekst RLS
admina (NIL UUID) jak w billing_tasks (przepływ systemowy bez JWT).
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select, text

from app.core.constants import NIL_UUID
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _usage_snapshot_impl() -> dict:
    from app.core.database import task_session
    from app.models.tenant import Tenant
    from app.models.usage import CounterType, UsageCounter
    from app.models.usage_history import UsageHistory
    from app.services.billing.subscription_service import _month_window

    now = datetime.now(UTC)
    today = now.date()

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))

        tenant_ids = list((await session.execute(select(Tenant.id))).scalars().all())
        counters = list((await session.execute(select(UsageCounter))).scalars().all())
        existing = list(
            (await session.execute(select(UsageHistory).where(UsageHistory.snapshot_date == today))).scalars().all()
        )

        # Najnowszy licznik per (tenant, typ) — kolejność okresów rosnąco.
        latest: dict[tuple, UsageCounter] = {}
        for counter in sorted(counters, key=lambda c: c.period_start):
            latest[(counter.tenant_id, counter.counter_type)] = counter
        already = {(h.tenant_id, h.counter_type) for h in existing}

        fallback_start, fallback_end = _month_window(now)
        snapshots = 0
        skipped = 0
        for tenant_id in tenant_ids:
            for counter_type in CounterType:
                if (tenant_id, counter_type) in already:
                    skipped += 1
                    continue
                counter = latest.get((tenant_id, counter_type))
                # Semantyka QuotaService._current_value: miesięczne typy poza
                # okresem → 0 (reset na nowy okres); storage kumulatywny → wartość.
                value = 0
                if counter is not None and (
                    counter_type == CounterType.STORAGE_BYTES or counter.period_start <= now < counter.period_end
                ):
                    value = counter.value
                    period_start, period_end = counter.period_start.date(), counter.period_end.date()
                else:
                    period_start, period_end = fallback_start.date(), fallback_end.date()
                session.add(
                    UsageHistory(
                        tenant_id=tenant_id,
                        counter_type=counter_type,
                        value=value,
                        snapshot_date=today,
                        period_start=period_start,
                        period_end=period_end,
                    )
                )
                snapshots += 1

        await session.commit()
    logger.info("Usage snapshot: tenants=%s snapshots=%s skipped=%s", len(tenant_ids), snapshots, skipped)
    return {"tenants": len(tenant_ids), "snapshots": snapshots, "skipped": skipped}


@celery_app.task(
    name="app.workers.tasks.usage_snapshot.run_usage_snapshot",
    bind=True,
    max_retries=1,
)
def run_usage_snapshot(self) -> dict:
    """Beat codziennie 00:00 — daily snapshoty zużycia (Story 7.9 AC3)."""
    try:
        return asyncio.run(_usage_snapshot_impl())
    except Exception as exc:
        logger.exception("usage_snapshot nie powiódł się")
        raise self.retry(exc=exc, countdown=300) from exc
