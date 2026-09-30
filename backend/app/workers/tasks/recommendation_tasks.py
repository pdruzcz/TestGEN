"""Celery tasks for recommendation generation — Epic 5, Story 5.5.

Fetches gap findings and code errors for a project, runs RecommendationEngine,
and persists Recommendation rows.
"""

import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)


async def _run_recommendation_generation_impl(
    project_id: str,
    tenant_id: str,
    sources: list[str],
) -> dict:
    from sqlalchemy import select, text

    from app.core.database import task_session
    from app.models.code_error import CodeError
    from app.models.gap_finding import GapFinding
    from app.models.recommendation import Recommendation
    from app.services.gap_analysis.recommendation_engine import (
        RecommendationEngine,
    )

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(
            text(f"SET LOCAL app.current_tenant = '{tid}'")
        )

        engine = RecommendationEngine()
        generated = []

        if "gap_finding" in sources:
            findings = list(
                (
                    await session.execute(
                        select(GapFinding).where(
                            GapFinding.project_id == pid,
                            GapFinding.tenant_id == tid,
                        )
                    )
                ).scalars().all()
            )
            generated.extend(engine.generate_from_gap_findings(findings))

        if "code_error" in sources:
            errors = list(
                (
                    await session.execute(
                        select(CodeError).where(
                            CodeError.project_id == pid,
                            CodeError.tenant_id == tid,
                        )
                    )
                ).scalars().all()
            )
            generated.extend(engine.generate_from_code_errors(errors))

        # Clear old recommendations
        await session.execute(
            text(
                f"DELETE FROM recommendations "
                f"WHERE project_id = '{pid}' AND tenant_id = '{tid}'"
            )
        )

        for g in generated:
            session.add(
                Recommendation(
                    tenant_id=tid,
                    project_id=pid,
                    gap_finding_id=(
                        uuid.UUID(g.gap_finding_id)
                        if g.gap_finding_id
                        else None
                    ),
                    code_error_id=(
                        uuid.UUID(g.code_error_id)
                        if g.code_error_id
                        else None
                    ),
                    title=g.title,
                    description=g.description,
                    priority=g.priority,
                    confidence=g.confidence,
                    source_type=g.source_type,
                    source_ref=g.source_ref,
                    suggestion=g.suggestion,
                    context=g.context or None,
                )
            )

        await session.commit()

        return {
            "status": "completed",
            "project_id": project_id,
            "total_recommendations": len(generated),
        }


@celery_app.task(
    bind=True,
    name="recommendation_generation.run",
    max_retries=3,
    queue="default",
)
def run_recommendation_generation(
    self,
    project_id: str,
    tenant_id: str,
    sources: list[str] | None = None,
) -> dict:
    """Generate recommendations for a project."""
    if sources is None:
        sources = ["gap_finding", "code_error"]

    try:
        return asyncio.run(
            _run_recommendation_generation_impl(
                project_id,
                tenant_id,
                sources,
            )
        )
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = (
            _RETRY_DELAYS[retry_num]
            if retry_num < len(_RETRY_DELAYS)
            else _RETRY_DELAYS[-1]
        )
        logger.warning(
            "Retry %d/%d for recommendation_generation.run (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error(
            "Error generating recommendations for project %s: %s",
            project_id,
            exc,
        )
        return {
            "status": "failed",
            "project_id": project_id,
            "error": str(exc),
        }
