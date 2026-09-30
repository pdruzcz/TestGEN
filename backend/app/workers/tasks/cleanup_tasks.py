"""Celery tasks that remove uploaded source code once analysis is done.

The task runs on a Beat schedule (default hourly) and processes any
``SourceFile`` rows whose parent project has reached a terminal status
(``completed`` / ``archived``). Files are removed from MinIO and the row's
``is_cleaned_up`` flag is flipped so the same object is not deleted twice.

Story 1.54 (FR72): anonymization mappings (``anonymization_maps``) are
deleted in the same per-tenant pass — for terminal projects (alongside the
source code, per 1.49) and once their retention window (``expires_at``)
has passed.
"""

import asyncio
import logging
from datetime import UTC, datetime

from minio.error import S3Error

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Retryable failure classes — mostly transient storage/network errors.
_RETRYABLE = (S3Error, ConnectionError, OSError)
_RETRY_DELAYS = (60, 300, 600)


_BATCH_SIZE = 100


async def _cleanup_source_files_impl() -> dict[str, int]:
    """Scan for cleanup-eligible rows, remove their storage objects, mark rows.

    Iterates per-tenant to respect RLS — each batch sets
    ``SET LOCAL app.current_tenant`` so the row-level security policy
    allows the query to return rows for that tenant.
    """
    from sqlalchemy import delete, or_, select, text, update

    from app.core.config import get_settings
    from app.core.database import task_session
    from app.core.storage import delete_file
    from app.models.anonymization_map import AnonymizationMap
    from app.models.project import Project, ProjectStatus
    from app.models.source_file import SourceFile
    from app.models.tenant import Tenant

    settings = get_settings()
    bucket = settings.minio_bucket_name
    removed = 0
    failed = 0
    scanned = 0
    mappings_removed = 0

    async with task_session() as session:
        # tenants table has no RLS — safe to query without tenant context.
        tenant_ids = list((await session.execute(select(Tenant.id))).scalars().all())

        for tid in tenant_ids:
            # RLS context (transaction-scoped — reset automatically after commit).
            safe_id = str(tid)
            await session.execute(text(f"SET LOCAL app.current_tenant = '{safe_id}'"))

            # Story 1.54 (FR72): mappingi anonimizacji usuwane razem z kodem —
            # projekty terminalne (spójne z 1.49) lub po upłynięciu retencji.
            map_result = await session.execute(
                delete(AnonymizationMap).where(
                    or_(
                        AnonymizationMap.expires_at < datetime.now(UTC),
                        AnonymizationMap.project_id.in_(
                            select(Project.id).where(
                                Project.status.in_((ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED))
                            )
                        ),
                    )
                )
            )
            tenant_maps = map_result.rowcount or 0
            if tenant_maps:
                mappings_removed += tenant_maps
                logger.info(
                    "tenant=%s — removed %d anonymization mappings (with source code)",
                    safe_id,
                    tenant_maps,
                )

            stmt = (
                select(SourceFile)
                .join(Project, Project.id == SourceFile.project_id)
                .where(
                    SourceFile.is_cleaned_up.is_(False),
                    Project.status.in_((ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED)),
                )
                .limit(_BATCH_SIZE)
            )
            result = await session.execute(stmt)
            candidates = list(result.scalars().all())
            scanned += len(candidates)

            for source_file in candidates:
                try:
                    await asyncio.to_thread(delete_file, bucket, source_file.storage_key)
                except Exception as exc:
                    logger.warning(
                        "Failed to delete storage key %s: %s",
                        source_file.storage_key,
                        exc,
                    )
                    failed += 1
                    continue

                await session.execute(
                    update(SourceFile).where(SourceFile.id == source_file.id).values(is_cleaned_up=True)
                )
                removed += 1

            await session.commit()

    return {
        "removed": removed,
        "failed": failed,
        "scanned": scanned,
        "mappings_removed": mappings_removed,
    }


@celery_app.task(
    bind=True,
    max_retries=3,
    queue="default",
)
def cleanup_source_files(self) -> dict[str, int]:
    """Entry point invoked by Celery Beat (and ad-hoc)."""
    try:
        return asyncio.run(_cleanup_source_files_impl())
    except _RETRYABLE as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for cleanup_source_files (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
