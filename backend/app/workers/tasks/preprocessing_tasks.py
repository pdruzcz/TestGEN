"""Celery tasks for preprocessing — language/framework detection, LOC counting."""

from __future__ import annotations

import asyncio
import logging
import uuid

from billiard.exceptions import SoftTimeLimitExceeded

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)


async def _mark_project_files_failed(project_id: str, tenant_id: str, error_msg: str) -> None:
    """Mark all PROCESSING code files in a project as FAILED."""
    from sqlalchemy import text, update

    from app.core.database import task_session
    from app.models.source_file import FileCategory, FileProcessingStatus, SourceFile

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        await session.execute(
            update(SourceFile)
            .where(
                SourceFile.project_id == pid,
                SourceFile.file_category == FileCategory.CODE,
                SourceFile.processing_status == FileProcessingStatus.PROCESSING,
            )
            .values(
                processing_status=FileProcessingStatus.FAILED,
                error_message=error_msg[:1000],
            )
        )
        await session.commit()


async def _preprocess_impl(project_id: str, tenant_id: str) -> dict:
    from sqlalchemy import text, update

    from app.core.database import task_session
    from app.models.source_file import FileCategory, FileProcessingStatus, SourceFile
    from app.services.project.preprocessing_service import PreprocessingService

    service = PreprocessingService()
    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        # Mark all code files as PROCESSING
        await session.execute(
            update(SourceFile)
            .where(
                SourceFile.project_id == pid,
                SourceFile.file_category == FileCategory.CODE,
                SourceFile.is_cleaned_up.is_(False),
                SourceFile.processing_status == FileProcessingStatus.UPLOADED,
            )
            .values(processing_status=FileProcessingStatus.PROCESSING)
        )
        await session.commit()

        report = await service.run_preprocessing(session, pid)

        # Mark all code files as READY after successful preprocessing
        await session.execute(
            update(SourceFile)
            .where(
                SourceFile.project_id == pid,
                SourceFile.file_category == FileCategory.CODE,
                SourceFile.processing_status == FileProcessingStatus.PROCESSING,
            )
            .values(processing_status=FileProcessingStatus.READY)
        )
        await session.commit()

    return {
        "status": "completed",
        "project_id": project_id,
        "total_loc": report.total_loc,
        "languages": [ls.language for ls in report.languages],
        "frameworks": report.detected_frameworks,
        "unknown_count": len(report.unknown_files),
    }


@celery_app.task(
    bind=True,
    name="preprocessing.detect_language",
    max_retries=3,
    queue="analysis",
)
def preprocessing_detect_language(
    self,
    project_id: str,
    tenant_id: str,
) -> dict:
    try:
        return asyncio.run(_preprocess_impl(project_id, tenant_id))
    except SoftTimeLimitExceeded:
        logger.warning("Soft time limit exceeded for preprocessing project=%s", project_id)
        asyncio.run(_mark_project_files_failed(project_id, tenant_id, "Preprocessing time limit exceeded"))
        return {
            "status": "timeout",
            "project_id": project_id,
            "total_loc": 0,
            "languages": [],
            "frameworks": [],
            "unknown_count": 0,
        }
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for preprocessing.detect_language (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
