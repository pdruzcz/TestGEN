"""Celery task wrappers for FastAPI background task integration.

Provides synchronous callables compatible with FastAPI's BackgroundTasks
that dispatch the actual Celery tasks to the worker queue.
"""

import logging

from app.workers.tasks.document_tasks import parse_document_task

logger = logging.getLogger(__name__)


def process_document_task(tenant_id: str, project_id: str, source_file_id: str) -> None:
    """Dispatch document preprocessing to Celery worker.

    Thin wrapper — adapts FastAPI background-task call signature
    (tenant_id, project_id, source_file_id) to the Celery task
    (source_file_id, tenant_id).

    Args:
        tenant_id: UUID of the tenant (for RLS).
        project_id: UUID of the project (for logging only).
        source_file_id: UUID of the uploaded source file.
    """
    logger.info(
        "Dispatching document preprocessing: source_file=%s project=%s tenant=%s",
        source_file_id,
        project_id,
        tenant_id,
    )
    parse_document_task.delay(source_file_id, tenant_id)
