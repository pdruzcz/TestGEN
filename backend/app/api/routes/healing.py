"""Self-healing routes — Epic 1, Story 1.51 (FR69).

Project-scoped endpoints to launch a healing run (async, 202 + report_id), read
a report with its items, and accept/reject a proposed locator fix (which applies
the change to ``TestCode`` on accept).  RBAC: Owner/Admin for the mutating
endpoints; any authenticated user may read.  Plan gating is a light hook for
Story 7.13 (freemium): self-healing requires Basic or higher.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.models.healing_report import HealingItem, HealingReport, HealingStatus
from app.models.project import Project
from app.models.user import User
from app.schemas.healing import (
    HealingDecisionRequest,
    HealingDecisionResponse,
    HealingReportResponse,
    HealRequest,
    HealTriggerResponse,
)
from app.services.generators.self_healing import SelfHealingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["healing"])


def _tenant_of(current_user: User) -> uuid.UUID:
    tenant_id = getattr(current_user, "_tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="No tenant context")
    return tenant_id


async def _verify_project_access(db: AsyncSession, project_id: uuid.UUID, tenant_id: uuid.UUID) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _require_healing_plan(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Gating hook (Story 7.13) — self-healing naprawia locatory GUI, więc
    podlega modułowi ``gui`` (próg basic, ``gated_modules`` z 7.1)."""
    from app.services.billing.feature_gating import FeatureGatingService

    await FeatureGatingService(db).enforce_feature(tenant_id, "gui")


@router.post(
    "/{project_id}/tests/heal",
    response_model=HealTriggerResponse,
    status_code=202,
)
async def start_healing(
    project_id: uuid.UUID,
    body: HealRequest,
    current_user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
) -> HealTriggerResponse:
    """Launch an asynchronous self-healing run between two GUI versions."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    await _require_healing_plan(db, tid)

    # Pre-generate the id so it can be returned synchronously before the task fills the row.
    report = HealingReport(
        id=uuid.uuid4(),
        project_id=project_id,
        tenant_id=tid,
        version_a=body.version_a,
        version_b=body.version_b,
        status=HealingStatus.PENDING,
    )
    db.add(report)
    await db.flush()

    from app.workers.tasks.healing_tasks import run_healing_task

    task = run_healing_task.delay(str(report.id), str(tid))
    await db.commit()
    return HealTriggerResponse(task_id=task.id, report_id=report.id)


@router.get(
    "/{project_id}/healing/{report_id}",
    response_model=HealingReportResponse,
)
async def get_healing_report(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HealingReportResponse:
    """Return a healing report with its items (status, confidence, diff)."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    result = await db.execute(
        select(HealingReport).where(
            HealingReport.id == report_id,
            HealingReport.project_id == project_id,
            HealingReport.tenant_id == tid,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Healing report not found")
    return HealingReportResponse.model_validate(report)


@router.post(
    "/{project_id}/healing/{report_id}/items/{item_id}/decision",
    response_model=HealingDecisionResponse,
)
async def decide_healing_item(
    project_id: uuid.UUID,
    report_id: uuid.UUID,
    item_id: uuid.UUID,
    body: HealingDecisionRequest,
    current_user: User = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
) -> HealingDecisionResponse:
    """Accept (apply to TestCode) or reject a proposed locator fix."""
    tid = _tenant_of(current_user)
    await _verify_project_access(db, project_id, tid)
    result = await db.execute(
        select(HealingItem).where(
            HealingItem.id == item_id,
            HealingItem.report_id == report_id,
            HealingItem.tenant_id == tid,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Healing item not found")

    from app.services.analysis.llm_gateway import get_llm_gateway

    service = SelfHealingService(db, llm_gateway=get_llm_gateway())
    item, applied = await service.apply_decision(item, body.action)
    await db.commit()
    return HealingDecisionResponse(item_id=item.id, status=item.status.value, applied=applied)
