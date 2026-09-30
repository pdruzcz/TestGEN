"""Task status routes — polling analysis task progress (Story 1.10, 6.3)."""

import logging

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_tenant
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.task_schemas import CancelTaskResponse, TaskStatusResponse
from app.services.task_progress_service import TaskProgressService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    tenant_id=Depends(get_tenant),
) -> TaskStatusResponse:
    progress_svc = TaskProgressService()
    status = progress_svc.get_task_status(task_id)

    if not status:
        raise NotFoundError("Task not found")

    # Verify task belongs to requesting tenant
    if status.get("tenant_id") and status["tenant_id"] != str(tenant_id):
        raise NotFoundError("Task not found")

    return TaskStatusResponse(
        task_id=status["task_id"],
        status=status["status"],
        progress=status["progress"],
        current_step=status["current_step"],
        result_url=status.get("result_url") or None,
        error=status.get("error") or None,
    )


@router.post(
    "/{task_id}/cancel",
    status_code=202,
    response_model=CancelTaskResponse,
)
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    tenant_id=Depends(get_tenant),
) -> CancelTaskResponse:
    """Anuluj uruchomione zadanie analizy (Story 6.3, AC5)."""
    progress_svc = TaskProgressService()
    status = progress_svc.get_task_status(task_id)

    if not status:
        raise NotFoundError("Zadanie nie zostało znalezione")

    if status.get("tenant_id") and status["tenant_id"] != str(tenant_id):
        raise NotFoundError("Zadanie nie zostało znalezione")

    # Revoke Celery task, then mark as cancelled in Redis (sets terminal TTL)
    celery_app.control.revoke(task_id, terminate=True)
    progress_svc.cancel_task(task_id)

    logger.info("Task %s cancelled by user %s", task_id, current_user.id)
    return CancelTaskResponse(task_id=task_id)
