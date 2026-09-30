"""Zadania Celery modułu billing — Story 7.2.

``run_subscription_renewals`` (beat, co dobę): skan odnowień cyklicznych +
dunning + wygasłe grace. Kontekst RLS admina (NIL UUID) jak w WebhookProcessor
(przepływ systemowy bez JWT); prywatny engine per wywołanie (``task_session``).
"""

import asyncio
import logging

from sqlalchemy import text

from app.core.constants import NIL_UUID
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_subscription_renewals_impl() -> dict:
    from app.core.config_billing import get_billing_settings
    from app.core.database import task_session
    from app.services.billing.providers.tpay import TpayProvider
    from app.services.billing.subscription_scheduler import SubscriptionScheduler

    provider = TpayProvider(get_billing_settings())
    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))
        stats = await SubscriptionScheduler(session, provider).run()
        await session.commit()
    return stats


@celery_app.task(
    name="app.workers.tasks.billing_tasks.run_subscription_renewals",
    bind=True,
    max_retries=1,
)
def run_subscription_renewals(self) -> dict:
    """Beat co dobę — odnowienia subskrypcji płatnych (Story 7.2 AC5/AC6)."""
    try:
        return asyncio.run(_run_subscription_renewals_impl())
    except Exception as exc:
        logger.exception("SubscriptionScheduler nie powiódł się")
        raise self.retry(exc=exc, countdown=300) from exc
