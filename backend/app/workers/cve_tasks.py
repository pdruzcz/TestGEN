"""Celery tasks for the CVE auto-update pipeline — Epic 4, Story 4.12.

Runs the monthly CVE refresh on the ``security`` queue. Each run is bracketed by a
``CVEUpdateLog`` row (running → completed/failed) so the admin dashboard can show
status, counts and errors. ``rescan_affected_projects`` re-queues dependency scans
for projects touched by newly published CVEs.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)


async def _update_cve_database_impl() -> dict:
    from app.core.config import get_settings
    from app.core.database import task_session
    from app.models.security_finding import CVEUpdateLog
    from app.services.security_scan.cve_pipeline import CVEPipeline

    settings = get_settings()
    async with task_session() as session:
        log = CVEUpdateLog(status="running", started_at=datetime.now(UTC))
        session.add(log)
        await session.flush()
        try:
            pipeline = CVEPipeline(
                nvd_api_key=getattr(settings, "nvd_api_key", None),
                github_token=getattr(settings, "github_token", None),
            )
            result = await pipeline.update_cve_database(session)
            log.status = "completed"
            log.completed_at = datetime.now(UTC)
            log.total_new = result.total_new
            log.total_updated = result.total_updated
            log.affected_projects = result.affected_projects
            log.sources_status = {
                name: {"ok": s.ok, "fetched": s.fetched, "error": s.error} for name, s in result.sources_status.items()
            }
            log.errors = result.errors or None
            await session.commit()
            return {
                "status": "completed",
                "total_new": result.total_new,
                "total_updated": result.total_updated,
                "affected_projects": result.affected_projects,
            }
        except Exception as exc:
            log.status = "failed"
            log.completed_at = datetime.now(UTC)
            log.errors = [str(exc)[:2000]]
            await session.commit()
            raise


@celery_app.task(
    bind=True,
    name="security.update_cve_database",
    max_retries=3,
    queue="security",
    time_limit=3600,
    soft_time_limit=3300,
)
def update_cve_database(self) -> dict:
    """Refresh the CVE cache from NVD/OSV/GitHub and re-scan affected projects."""
    try:
        return asyncio.run(_update_cve_database_impl())
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for security.update_cve_database (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error updating CVE database: %s", exc)
        return {"status": "failed", "error": str(exc)}


async def _rescan_impl(project_ids: list[str]) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.models.project import Project
    from app.models.security_finding import ScanStatus, ScanType, SecurityScan
    from app.workers.tasks.security_tasks import run_dependency_scan

    queued = 0
    async with task_session() as session:
        for pid_str in project_ids:
            pid = uuid.UUID(pid_str)
            project = await session.get(Project, pid)
            if project is None:
                continue
            tid = project.tenant_id
            await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
            scan = SecurityScan(
                project_id=pid,
                tenant_id=tid,
                scan_type=ScanType.DEPENDENCY,
                status=ScanStatus.PENDING,
            )
            session.add(scan)
            await session.flush()
            run_dependency_scan.delay(str(scan.id), str(pid), str(tid))
            queued += 1
        await session.commit()
    return {"status": "completed", "queued": queued}


@celery_app.task(bind=True, name="security.rescan_affected_projects", max_retries=3, queue="security")
def rescan_affected_projects(self, project_ids: list[str]) -> dict:
    """Queue a fresh dependency scan for each project touched by new CVEs."""
    try:
        return asyncio.run(_rescan_impl(project_ids))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error re-scanning affected projects: %s", exc)
        return {"status": "failed", "error": str(exc)}
