"""Celery task for self-healing of UI test locators — Epic 1, Story 1.51 (FR69).

Loads a PENDING ``HealingReport`` (created up-front by the API so its id can be
returned synchronously), fills it via :class:`SelfHealingService.fill_report`,
commits, and emits the run metrics as a structured log line (shipped to Loki by
the platform log pipeline — same convention as the other analysis tasks).
"""

import asyncio
import json
import logging
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)


async def _run_healing_impl(report_id: str, tenant_id: str) -> dict:
    from sqlalchemy import select, text

    from app.core.database import task_session
    from app.models.healing_report import HealingReport
    from app.services.analysis.llm_gateway import get_llm_gateway
    from app.services.generators.self_healing import SelfHealingService

    rid = uuid.UUID(report_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        res = await session.execute(select(HealingReport).where(HealingReport.id == rid))
        report = res.scalars().one_or_none()
        if report is None:
            logger.error("Healing report %s not found", report_id)
            return {"status": "failed", "report_id": report_id, "error": "not_found"}

        # engine_mode is config-only (never user-facing); the gateway degrades
        # gracefully to native-only when no provider keys are configured.
        service = SelfHealingService(session, llm_gateway=get_llm_gateway())
        await service.fill_report(report)
        await session.commit()

        stats = report.stats or {}
        logger.info("healing.run metrics: %s", json.dumps(stats, ensure_ascii=False))
        return {
            "status": report.status.value,
            "report_id": report_id,
            "stats": stats,
        }


@celery_app.task(
    bind=True,
    name="healing.run",
    max_retries=3,
    queue="analysis",
)
def run_healing_task(self, report_id: str, tenant_id: str) -> dict:
    """Fill a pending healing report with broken-locator fixes (FR69)."""
    try:
        return asyncio.run(_run_healing_impl(report_id, tenant_id))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for healing.run (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in healing run %s: %s", report_id, exc)
        return {"status": "failed", "report_id": report_id, "error": str(exc)}
