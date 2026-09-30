"""Celery tasks for the security module — Epic 4, Story 4.1.

Runs scans asynchronously on the ``security`` queue: updates the
``SecurityScan`` lifecycle (running → completed/failed), invokes the relevant
engine, and persists the resulting ``SecurityFinding`` rows.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.workers.celery_app import celery_app

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)


async def _mark_scan_failed(session: "AsyncSession", sid: uuid.UUID, tid: uuid.UUID, exc: BaseException) -> None:
    """Persist ``SecurityScan.status = FAILED`` with the error message.

    Robust against the very failure that aborted the scan: after a flush error
    the SQLAlchemy session is in a rolled-back state, so a plain ``commit``
    raises ``PendingRollbackError`` and the FAILED update never lands — the
    scan then shows as PENDING ("oczekuje") forever. We ``rollback`` first,
    re-establish the tenant context (``SET LOCAL app.current_tenant`` is scoped
    to a single transaction), re-fetch the scan, and only then persist FAILED.
    """
    from sqlalchemy import text

    from app.models.security_finding import ScanStatus, SecurityScan

    await session.rollback()
    await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
    scan = await session.get(SecurityScan, sid)
    if scan is None:
        return
    scan.status = ScanStatus.FAILED
    scan.error_message = str(exc)[:2000]
    scan.completed_at = datetime.now(UTC)
    await session.commit()


async def _run_sast_impl(scan_id: str, project_id: str, tenant_id: str, engine_mode: str) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.models.security_finding import ScanStatus, SecurityScan
    from app.services.security_scan.sast_engine import SASTEngine

    sid = uuid.UUID(scan_id)
    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    llm_gateway = None
    if engine_mode in ("llm", "hybrid"):
        from app.services.analysis.llm_gateway import get_llm_gateway

        llm_gateway = get_llm_gateway()

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        scan = await session.get(SecurityScan, sid)
        if scan is None:
            return {"status": "failed", "scan_id": scan_id, "error": "scan not found"}

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(UTC)
        await session.flush()

        try:
            engine = SASTEngine(session, llm_gateway=llm_gateway, engine_mode=engine_mode)
            findings = await engine.run_sast(pid, tid, sid)
            session.add_all(findings)
            scan.findings_count = len(findings)
            scan.status = ScanStatus.COMPLETED
            scan.completed_at = datetime.now(UTC)
            await session.commit()
            await _emit_critical_findings(tid, project_id, findings)
            return {"status": "completed", "scan_id": scan_id, "findings": len(findings)}
        except Exception as exc:
            await _mark_scan_failed(session, sid, tid, exc)
            raise



async def _emit_critical_findings(tenant_id, project_id: str, findings) -> None:
    """Webhook ``security.finding`` — tylko critical/high (Story 8.7, AC2).

    Wspólny dla wszystkich pięciu typów skanów. Średnie i niższe pomijamy
    świadomie: webhook ma budzić dyżur, a nie zalewać go szumem, który
    i tak przejrzy się w raporcie.
    """
    try:
        from app.services.integrations.event_emitter import emit_event_standalone

        for finding in findings:
            severity = getattr(finding.severity, "value", finding.severity)
            if severity not in ("critical", "high"):
                continue
            await emit_event_standalone(
                "security.finding",
                tenant_id,
                {
                    "project_id": project_id,
                    "finding_id": str(getattr(finding, "id", "")) or None,
                    "severity": severity,
                    "type": getattr(finding, "vulnerability_type", None),
                    "description": getattr(finding, "description", None),
                    "file_path": getattr(finding, "file_path", None),
                    "line": getattr(finding, "line_start", None),
                },
            )
    except Exception:
        logger.warning("Nie udało się wyemitować security.finding", exc_info=True)


@celery_app.task(bind=True, name="security.run_sast", max_retries=3, queue="security")
def run_sast(
    self,
    scan_id: str,
    project_id: str,
    tenant_id: str,
    engine_mode: str = "native",
) -> dict:
    """Execute a SAST scan and persist its findings."""
    try:
        return asyncio.run(_run_sast_impl(scan_id, project_id, tenant_id, engine_mode))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for security.run_sast (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error running SAST scan %s: %s", scan_id, exc)
        return {"status": "failed", "scan_id": scan_id, "error": str(exc)}


async def _run_taint_impl(scan_id: str, project_id: str, tenant_id: str, engine_mode: str) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.models.security_finding import ScanStatus, SecurityScan
    from app.services.security_scan.taint_analyzer import TaintAnalyzer

    sid = uuid.UUID(scan_id)
    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    llm_gateway = None
    if engine_mode in ("llm", "hybrid"):
        from app.services.analysis.llm_gateway import get_llm_gateway

        llm_gateway = get_llm_gateway()

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        scan = await session.get(SecurityScan, sid)
        if scan is None:
            return {"status": "failed", "scan_id": scan_id, "error": "scan not found"}

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(UTC)
        await session.flush()

        try:
            analyzer = TaintAnalyzer(session, llm_gateway=llm_gateway, engine_mode=engine_mode)
            findings = await analyzer.run_taint_analysis(pid, tid, sid)
            session.add_all(findings)
            scan.findings_count = len(findings)
            scan.status = ScanStatus.COMPLETED
            scan.completed_at = datetime.now(UTC)
            await session.commit()
            await _emit_critical_findings(tid, project_id, findings)
            return {"status": "completed", "scan_id": scan_id, "findings": len(findings)}
        except Exception as exc:
            await _mark_scan_failed(session, sid, tid, exc)
            raise


@celery_app.task(bind=True, name="security.run_taint_analysis", max_retries=3, queue="security")
def run_taint_analysis(
    self,
    scan_id: str,
    project_id: str,
    tenant_id: str,
    engine_mode: str = "native",
) -> dict:
    """Execute a taint-analysis scan and persist its findings."""
    try:
        return asyncio.run(_run_taint_impl(scan_id, project_id, tenant_id, engine_mode))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for security.run_taint_analysis (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error running taint scan %s: %s", scan_id, exc)
        return {"status": "failed", "scan_id": scan_id, "error": str(exc)}


async def _run_dependency_impl(scan_id: str, project_id: str, tenant_id: str) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.models.security_finding import ScanStatus, SecurityScan
    from app.services.security_scan.dependency_scanner import DependencyScanner

    sid = uuid.UUID(scan_id)
    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        scan = await session.get(SecurityScan, sid)
        if scan is None:
            return {"status": "failed", "scan_id": scan_id, "error": "scan not found"}

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(UTC)
        await session.flush()

        try:
            scanner = DependencyScanner(session)
            findings, sbom = await scanner.scan_dependencies(pid, tid, sid)
            session.add_all(findings)
            scan.findings_count = len(findings)
            scan.scan_metadata = sbom
            scan.status = ScanStatus.COMPLETED
            scan.completed_at = datetime.now(UTC)
            await session.commit()
            await _emit_critical_findings(tid, project_id, findings)
            return {"status": "completed", "scan_id": scan_id, "findings": len(findings)}
        except Exception as exc:
            await _mark_scan_failed(session, sid, tid, exc)
            raise


@celery_app.task(bind=True, name="security.run_dependency_scan", max_retries=3, queue="security")
def run_dependency_scan(self, scan_id: str, project_id: str, tenant_id: str) -> dict:
    """Execute a dependency (SCA) scan, persist findings and store the SBOM."""
    try:
        return asyncio.run(_run_dependency_impl(scan_id, project_id, tenant_id))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for security.run_dependency_scan (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error running dependency scan %s: %s", scan_id, exc)
        return {"status": "failed", "scan_id": scan_id, "error": str(exc)}


async def _run_config_impl(scan_id: str, project_id: str, tenant_id: str, engine_mode: str) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.models.security_finding import ScanStatus, SecurityScan
    from app.services.security_scan.config_scanner import ConfigScanner

    sid = uuid.UUID(scan_id)
    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    llm_gateway = None
    if engine_mode in ("llm", "hybrid"):
        from app.services.analysis.llm_gateway import get_llm_gateway

        llm_gateway = get_llm_gateway()

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        scan = await session.get(SecurityScan, sid)
        if scan is None:
            return {"status": "failed", "scan_id": scan_id, "error": "scan not found"}

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(UTC)
        await session.flush()

        try:
            scanner = ConfigScanner(session, llm_gateway=llm_gateway, engine_mode=engine_mode)
            findings = await scanner.scan_config(pid, tid, sid)
            session.add_all(findings)
            scan.findings_count = len(findings)
            scan.status = ScanStatus.COMPLETED
            scan.completed_at = datetime.now(UTC)
            await session.commit()
            await _emit_critical_findings(tid, project_id, findings)
            return {"status": "completed", "scan_id": scan_id, "findings": len(findings)}
        except Exception as exc:
            await _mark_scan_failed(session, sid, tid, exc)
            raise


@celery_app.task(bind=True, name="security.run_config_scan", max_retries=3, queue="security")
def run_config_scan(
    self,
    scan_id: str,
    project_id: str,
    tenant_id: str,
    engine_mode: str = "native",
) -> dict:
    """Execute an infrastructure-config scan and persist its findings."""
    try:
        return asyncio.run(_run_config_impl(scan_id, project_id, tenant_id, engine_mode))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for security.run_config_scan (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error running config scan %s: %s", scan_id, exc)
        return {"status": "failed", "scan_id": scan_id, "error": str(exc)}


async def _run_dast_impl(
    scan_id: str,
    project_id: str,
    tenant_id: str,
    target_url: str,
    auth_config: dict | None,
) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.models.security_finding import ScanStatus, SecurityScan
    from app.services.security_scan.dast_runner import DASTRunner

    sid = uuid.UUID(scan_id)
    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        scan = await session.get(SecurityScan, sid)
        if scan is None:
            return {"status": "failed", "scan_id": scan_id, "error": "scan not found"}

        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.now(UTC)
        await session.flush()

        try:
            runner = DASTRunner(session)
            findings = await runner.run_dast(pid, tid, sid, target_url, auth_config)
            session.add_all(findings)
            scan.findings_count = len(findings)
            scan.status = ScanStatus.COMPLETED
            scan.completed_at = datetime.now(UTC)
            await session.commit()
            await _emit_critical_findings(tid, project_id, findings)
            return {"status": "completed", "scan_id": scan_id, "findings": len(findings)}
        except Exception as exc:
            await _mark_scan_failed(session, sid, tid, exc)
            raise


@celery_app.task(
    bind=True,
    name="security.run_dast_scan",
    max_retries=3,
    queue="security",
    time_limit=2100,
    soft_time_limit=1980,
)
def run_dast_scan(
    self,
    scan_id: str,
    project_id: str,
    tenant_id: str,
    target_url: str,
    auth_config: dict | None = None,
) -> dict:
    """Execute a DAST (OWASP ZAP) scan and persist its findings.

    The hard/soft time limits give the 30-minute active scan headroom plus a
    container start/stop buffer (AC1).
    """
    try:
        return asyncio.run(_run_dast_impl(scan_id, project_id, tenant_id, target_url, auth_config))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for security.run_dast_scan (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error running DAST scan %s: %s", scan_id, exc)
        return {"status": "failed", "scan_id": scan_id, "error": str(exc)}


async def _aggregate_findings_impl(project_id: str, tenant_id: str, scan_ids: list[str]) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.security_scan.finding_aggregator import FindingAggregator

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    sids = [uuid.UUID(s) for s in scan_ids]

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        aggregator = FindingAggregator(session)
        result = await aggregator.aggregate(pid, sids, session)
        return {
            "status": "completed",
            "project_id": project_id,
            "total": result.summary["total_findings"],
            "dedup_count": result.dedup_count,
            "correlations": len(result.correlations),
        }


@celery_app.task(bind=True, name="security.aggregate_findings", max_retries=3, queue="security")
def aggregate_findings(self, project_id: str, tenant_id: str, scan_ids: list[str]) -> dict:
    """Aggregate, deduplicate and correlate findings across scans (Story 4.7)."""
    try:
        return asyncio.run(_aggregate_findings_impl(project_id, tenant_id, scan_ids))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for security.aggregate_findings (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error aggregating findings for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}
