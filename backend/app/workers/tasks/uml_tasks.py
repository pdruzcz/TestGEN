"""Celery tasks for UML diagram parsing — Epic 3."""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)


async def _parse_uml_impl(diagram_id: str, tenant_id: str) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.analysis.uml.orchestrator import UMLParserOrchestrator

    did = uuid.UUID(diagram_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        orchestrator = UMLParserOrchestrator()
        model = await orchestrator.parse(did, session)
        await session.commit()
        return {
            "status": "completed",
            "diagram_id": diagram_id,
            "model_id": str(model.id),
            "diagram_type": model.model_type.value,
        }


@celery_app.task(
    bind=True,
    name="uml.parse_diagram",
    max_retries=3,
    queue="analysis",
)
def parse_uml_diagram(self, diagram_id: str, tenant_id: str) -> dict:
    """Parse a UML diagram asynchronously and persist its structural model."""
    try:
        return asyncio.run(_parse_uml_impl(diagram_id, tenant_id))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for uml.parse_diagram (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error parsing UML diagram %s: %s", diagram_id, exc)
        return {"status": "failed", "diagram_id": diagram_id, "error": str(exc)}
