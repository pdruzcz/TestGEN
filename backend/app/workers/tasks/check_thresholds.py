"""Zadanie Celery check_thresholds — Story 7.11 (AC6).

``check_usage_thresholds`` (beat, co godzinę): progi zużycia 80/90/100%
per aktywny tenant → powiadomienia in-app + email Ownera (dedup per
okres rozliczeniowy w ``NotificationService``). Kontekst RLS admina
(NIL UUID) jak w billing_tasks/usage_snapshot (przepływ systemowy bez JWT).
"""

import asyncio
import logging

from sqlalchemy import text

from app.core.constants import NIL_UUID
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _check_thresholds_impl() -> dict:
    from app.core.database import task_session
    from app.services.notification_service import NotificationService

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{NIL_UUID}'"))
        stats = await NotificationService(session).check_and_notify_thresholds()
        await session.commit()
    return stats


@celery_app.task(
    name="app.workers.tasks.check_thresholds.check_usage_thresholds",
    bind=True,
    max_retries=1,
)
def check_usage_thresholds(self) -> dict:
    """Beat co godzinę — progi zużycia → powiadomienia (Story 7.11 AC6)."""
    try:
        return asyncio.run(_check_thresholds_impl())
    except Exception as exc:
        logger.exception("check_usage_thresholds nie powiódł się")
        raise self.retry(exc=exc, countdown=300) from exc
