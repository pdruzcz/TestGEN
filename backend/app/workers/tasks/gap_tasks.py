"""Celery tasks for functional gap analysis — Epic 5, Story 5.1.

Runs gap analysis asynchronously: fetches requirements from document analysis
and code entities from Epic 1 logic_structures, runs ComparatorService,
and persists GapFinding rows.
"""

import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)


async def _run_gap_analysis_impl(
    project_id: str,
    document_ids: list[str],
    tenant_id: str,
    engine_mode: str,
) -> dict:
    from sqlalchemy import select, text

    from app.core.database import task_session
    from app.models.analysis_result import AnalysisResult, AnalysisStatus
    from app.models.gap_finding import GapFinding
    from app.models.source_file import SourceFile
    from app.services.analysis.document.requirement_extractor import from_result_data
    from app.services.analysis.gap_analyzer import code_entities_from_logic_structures
    from app.services.gap_analysis.comparator import (
        ComparatorService,
        RequirementData,
    )

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        # Phase 1: Collect requirements from document analysis results
        req_query = select(AnalysisResult).where(
            AnalysisResult.project_id == pid,
            AnalysisResult.module == "requirements",
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
        if document_ids:
            req_query = req_query.where(
                AnalysisResult.source_file_id.in_([uuid.UUID(d) for d in document_ids])
            )

        req_results = (await session.execute(req_query)).scalars().all()

        requirements: list[RequirementData] = []
        for ar in req_results:
            for raw in from_result_data(ar.result_data):
                requirements.append(RequirementData(
                    req_id=raw.get("req_id", ""),
                    text=raw.get("text", ""),
                    category=raw.get("category", ""),
                    priority=raw.get("priority", "medium"),
                    source_section_id=raw.get("source_section_id"),
                ))

        # Phase 2: Fetch code entities from Epic 1 logic_structures
        ls_query = select(AnalysisResult).where(
            AnalysisResult.project_id == pid,
            AnalysisResult.module == "logic_structures",
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
        ls_result = (await session.execute(ls_query)).scalars().first()
        code_entities = code_entities_from_logic_structures(
            ls_result.result_data if ls_result else None
        )

        if not requirements:
            logger.warning(
                "Gap analysis: no requirements found for project %s "
                "(completed requirements modules: %d)",
                project_id,
                len(req_results),
            )
            return {
                "status": "completed",
                "project_id": project_id,
                "total_findings": 0,
                "message": "No requirements found to analyze",
            }

        if not code_entities:
            logger.warning(
                "Gap analysis: no code entities found for project %s", project_id
            )

        # Phase 3: Run comparison (native + optional LLM dual-path)
        service = ComparatorService()
        native_findings, summary = service.compare(requirements, code_entities)

        comparison_report = None
        engine_used = engine_mode or "native"

        if engine_used in ("hybrid", "llm"):
            try:
                from app.services.gap_analysis.llm_gap_analyzer import LLMGapAnalyzer
                from app.services.gap_analysis.dual_path_orchestrator import (
                    GapDualPathOrchestrator,
                )

                llm_analyzer = LLMGapAnalyzer()
                llm_findings, _ = await llm_analyzer.analyze(
                    requirements, code_entities, tenant_id=tid,
                )

                if engine_used == "llm":
                    findings_data = llm_findings
                else:
                    orchestrator = GapDualPathOrchestrator()
                    result = orchestrator.run_analysis(
                        native_findings, llm_findings, "hybrid",
                    )
                    findings_data = result.findings
                    comparison_report = result.comparison_report
            except Exception as exc:
                logger.warning("LLM gap analysis failed, using native only: %s", exc)
                findings_data = native_findings
        else:
            findings_data = native_findings

        # Phase 4: Clear old findings and persist new ones
        await session.execute(
            text(
                f"DELETE FROM gap_findings "
                f"WHERE project_id = '{pid}' AND tenant_id = '{tid}'"
            )
        )

        created_findings: list[GapFinding] = []
        for fd in findings_data:
            created_findings.append(GapFinding(
                tenant_id=tid,
                project_id=pid,
                requirement_id=fd.requirement_id,
                code_entity_id=fd.code_entity_id,
                gap_type=fd.gap_type,
                description=fd.description,
                requirement_text=fd.requirement_text,
                code_reference=fd.code_reference,
                match_score=fd.match_score,
                match_method=fd.match_method,
                context=fd.context,
                severity=fd.severity,
                source=(fd.context or {}).get("source", "native"),
            ))
        session.add_all(created_findings)

        await session.commit()

        # Story 8.7 (AC2): powiadomienie systemów klienta. Emiter jest cichy —
        # nieudana dostawa nie może unieważnić wykonanej analizy luk.
        if created_findings:
            from app.services.integrations.event_emitter import emit_event_standalone

            first = created_findings[0]
            await emit_event_standalone(
                "gap.detected",
                tid,
                {
                    "project_id": project_id,
                    "gap_id": str(first.id),
                    "type": str(first.gap_type),
                    "requirement": first.requirement_id,
                    "description": first.description,
                    "total_findings": len(created_findings),
                },
            )

        result = {
            "status": "completed",
            "project_id": project_id,
            "total_findings": len(findings_data),
            "total_requirements": summary.total_requirements,
            "total_code_entities": summary.total_code_entities,
            "missing_count": summary.missing_count,
            "different_count": summary.different_count,
            "extra_count": summary.extra_count,
            "coverage_percentage": summary.coverage_percentage,
            "engine_mode": engine_used,
        }
        if comparison_report:
            result["comparison"] = {
                "native_count": comparison_report.native_count,
                "llm_count": comparison_report.llm_count,
                "merged_count": comparison_report.merged_count,
                "native_only": comparison_report.native_only_count,
                "llm_only": comparison_report.llm_only_count,
                "overlap": comparison_report.overlap_count,
                "coverage_improvement_pct": comparison_report.coverage_improvement_pct,
            }
        return result


@celery_app.task(
    bind=True,
    name="gap_analysis.run",
    max_retries=3,
    queue="default",
)
def run_gap_analysis(
    self,
    project_id: str,
    document_ids: list[str],
    tenant_id: str,
    engine_mode: str = "native",
) -> dict:
    """Run functional gap analysis for a project."""
    try:
        return asyncio.run(
            _run_gap_analysis_impl(project_id, document_ids, tenant_id, engine_mode)
        )
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for gap_analysis.run (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error running gap analysis for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}
