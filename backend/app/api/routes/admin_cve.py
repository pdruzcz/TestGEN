"""Admin routes for the CVE auto-update pipeline — Epic 4, Story 4.12.

Surfaces pipeline health to platform admins: last run, new/updated CVE counts,
affected projects, per-source status and errors (AC4), the full run history, and a
manual trigger that enqueues an out-of-band update.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.security_finding import CVEUpdateLog
from app.models.user import User
from app.schemas.security import (
    CVEPipelineLogListResponse,
    CVEPipelineLogResponse,
    CVEPipelineStatusResponse,
    CVEPipelineTriggerResponse,
    CVESourceStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/cve-pipeline", tags=["admin-cve"])


@router.get("/status", response_model=CVEPipelineStatusResponse)
async def get_pipeline_status(
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> CVEPipelineStatusResponse:
    """Return the latest pipeline run summary for the admin dashboard."""
    result = await db.execute(
        select(CVEUpdateLog).order_by(CVEUpdateLog.started_at.desc()).limit(1)
    )
    last = result.scalar_one_or_none()
    if last is None:
        return CVEPipelineStatusResponse()

    sources = {
        name: CVESourceStatusResponse(
            source=name,
            ok=bool(payload.get("ok")),
            fetched=int(payload.get("fetched") or 0),
            error=payload.get("error"),
        )
        for name, payload in (last.sources_status or {}).items()
    }
    return CVEPipelineStatusResponse(
        last_run_at=last.completed_at or last.started_at,
        last_status=last.status,
        total_new=last.total_new,
        total_updated=last.total_updated,
        affected_projects=last.affected_projects,
        sources_status=sources,
        errors=list(last.errors or []),
    )


@router.get("/logs", response_model=CVEPipelineLogListResponse)
async def list_pipeline_logs(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> CVEPipelineLogListResponse:
    """Return the CVE update run history (most recent first)."""
    total = await db.scalar(select(func.count()).select_from(CVEUpdateLog))
    result = await db.execute(
        select(CVEUpdateLog).order_by(CVEUpdateLog.started_at.desc()).limit(limit)
    )
    logs = [CVEPipelineLogResponse.model_validate(row) for row in result.scalars().all()]
    return CVEPipelineLogListResponse(logs=logs, total=total or 0)


@router.post("/trigger", response_model=CVEPipelineTriggerResponse, status_code=202)
async def trigger_pipeline(
    current_user: User = Depends(require_role("admin")),
) -> CVEPipelineTriggerResponse:
    """Manually enqueue a CVE database update (admin only)."""
    from app.workers.cve_tasks import update_cve_database

    task_id: str | None = None
    try:
        async_result = update_cve_database.delay()
        task_id = getattr(async_result, "id", None)
    except Exception as exc:  # broker may be unavailable
        logger.warning("Could not enqueue CVE update: %s", exc)
        return CVEPipelineTriggerResponse(
            status="error",
            message="Nie udało się uruchomić aktualizacji — broker niedostępny.",
        )
    return CVEPipelineTriggerResponse(
        status="queued",
        task_id=task_id,
        message="Aktualizacja bazy CVE została uruchomiona.",
    )
