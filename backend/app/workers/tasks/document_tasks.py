"""Celery tasks for document parsing — Epic 2 documentation analysis.

Tasks for asynchronous document processing, parsing, and storage.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid

from billiard.exceptions import SoftTimeLimitExceeded

from app.services.task_progress_service import TaskProgressService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)


async def _mark_file_failed(source_file_id: str, tenant_id: str, error_msg: str) -> None:
    """Mark a source file as FAILED with an error message.

    Uses ``task_session()`` (a fresh async engine per call) so it is safe to
    invoke from an ``except`` handler after the main ``asyncio.run()`` has
    torn down its loop. See ``task_session`` for the cross-loop rationale.
    """
    from sqlalchemy import select, text

    from app.core.database import task_session
    from app.models.source_file import FileProcessingStatus, SourceFile

    pid = uuid.UUID(source_file_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        result = await session.execute(select(SourceFile).where(SourceFile.id == pid))
        sf = result.scalar_one_or_none()
        if sf:
            sf.processing_status = FileProcessingStatus.FAILED
            sf.error_message = error_msg[:1000]
            await session.commit()


async def _parse_document_impl(source_file_id: str, tenant_id: str) -> dict:
    """Implementation of document parsing task.

    Args:
        source_file_id: UUID of the source file to parse.
        tenant_id: UUID of the tenant (for RLS).

    Returns:
        Dictionary with parsing result and parsed document data.
    """
    from sqlalchemy import select, text

    from app.core.config import get_settings
    from app.core.database import task_session
    from app.core.storage import download_file_bytes
    from app.models.analysis_result import AnalysisResult, AnalysisStatus, EngineMode
    from app.models.source_file import FileCategory, FileProcessingStatus, SourceFile
    from app.services.analysis.document import parse_and_preprocess_document

    pid = uuid.UUID(source_file_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        # Fetch source file
        result = await session.execute(
            select(SourceFile).where(
                SourceFile.id == pid,
                SourceFile.file_category == FileCategory.DOCUMENTATION,
                SourceFile.is_cleaned_up.is_(False),
            )
        )
        source_file = result.scalar_one_or_none()

        if not source_file:
            raise ValueError(f"Source file {source_file_id} not found or not a documentation file")

        # Mark as PROCESSING
        source_file.processing_status = FileProcessingStatus.PROCESSING
        await session.commit()

        # Download file from MinIO to a temporary file for parsing
        settings = get_settings()
        raw_bytes = download_file_bytes(settings.minio_bucket_name, source_file.storage_key)

        ext = os.path.splitext(source_file.filename)[1] or ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        try:
            doc_structure = parse_and_preprocess_document(tmp_path)
        finally:
            os.unlink(tmp_path)

        # Store preprocessing result in analysis_results
        analysis_result = AnalysisResult(
            tenant_id=tid,
            project_id=source_file.project_id,
            source_file_id=pid,
            engine_mode=EngineMode.NATIVE,
            module="document_preprocessing",
            status=AnalysisStatus.COMPLETED,
            result_data={
                "document_structure": {
                    "filename": doc_structure.metadata.get("filename", source_file.filename),
                    "format": doc_structure.metadata.get("format", ""),
                    "sections_count": doc_structure.metadata.get("sections_count", 0),
                    "tables_count": doc_structure.metadata.get("tables_count", 0),
                    "processing_time_ms": doc_structure.metadata.get("processing_time_ms", 0),
                    "artifact_count": doc_structure.metadata.get("artifact_count", 0),
                    "polish_char_issues_fixed": doc_structure.metadata.get("polish_char_issues_fixed", 0),
                    "compression_ratio": doc_structure.metadata.get("compression_ratio", 1.0),
                },
                "sections": _serialize_sections(doc_structure.sections),
                "tables": [
                    {
                        "table_id": t.table_id,
                        "headers": t.headers,
                        "rows": t.rows,
                        "source_section_id": t.source_section_id,
                    }
                    for t in doc_structure.tables
                ],
            },
            duration_ms=doc_structure.metadata.get("processing_time_ms", 0),
        )

        session.add(analysis_result)

        # Classification (Story 2.3 closure) — non-fatal: any failure is logged
        # and the file still reaches READY. Runs by the global engine_mode and
        # persists the result as AnalysisResult(module="classification").
        try:
            from app.services.analysis.document.classifier import (
                DocumentClassifier,
                classify_document_async,
            )

            cls_engine = settings.engine_mode.value
            classifier = DocumentClassifier()
            classification = await classify_document_async(doc_structure, cls_engine, tenant_id=tid)
            session.add(
                AnalysisResult(
                    tenant_id=tid,
                    project_id=source_file.project_id,
                    source_file_id=pid,
                    engine_mode=EngineMode(cls_engine),
                    module="classification",
                    status=AnalysisStatus.COMPLETED,
                    result_data={
                        "doc_type": classification.doc_type.value,
                        "confidence": classification.confidence,
                        "source": classification.source.value,
                        "reasoning": classification.reasoning,
                        "native_confidence": classification.native_confidence,
                        "llm_confidence": classification.llm_confidence,
                        "all_scores": classifier._native_scores(doc_structure),
                    },
                )
            )
        except Exception as cls_exc:
            logger.warning(
                "Classification failed for %s (non-fatal): %s",
                source_file_id,
                cls_exc,
            )

        # ``reqs`` default so the inconsistency block (Story 2.7) can reuse the
        # already-extracted requirements even when the extraction below fails.
        reqs: list = []

        # Requirement extraction (Story 2.5 closure) — non-fatal: any failure is
        # logged and the file still reaches READY. Routes by the global
        # ``engine_mode`` (native / llm; hybrid → warning + native). Each element
        # carries its ``source`` (native|llm) and optional ``reasoning``.
        try:
            from app.services.analysis.document.requirement_extractor import (
                extract_requirements_async,
                requirements_to_result_data,
            )

            req_engine = settings.engine_mode.value
            reqs = await extract_requirements_async(doc_structure, req_engine, tenant_id=tid)
            session.add(
                AnalysisResult(
                    tenant_id=tid,
                    project_id=source_file.project_id,
                    source_file_id=pid,
                    engine_mode=EngineMode(req_engine),
                    module="requirements",
                    status=AnalysisStatus.COMPLETED,
                    result_data=requirements_to_result_data(reqs),
                )
            )
        except Exception as req_exc:  # non-fatal
            logger.warning(
                "Requirements extraction failed for %s (non-fatal): %s",
                source_file_id,
                req_exc,
            )

        # Glossary extraction (Story 2.6 closure) — non-fatal: any failure is
        # logged and the file still reaches READY. Native extraction persisted as
        # AnalysisResult(module="glossary"). Term→code mapping is a separate,
        # endpoint-triggered step (requires project code analysis availability).
        try:
            from app.services.analysis.document.glossary_extractor import (
                extract_glossary,
                glossary_terms_to_result_data,
            )

            glossary_terms = extract_glossary(doc_structure)
            session.add(
                AnalysisResult(
                    tenant_id=tid,
                    project_id=source_file.project_id,
                    source_file_id=pid,
                    engine_mode=EngineMode.NATIVE,
                    module="glossary",
                    status=AnalysisStatus.COMPLETED,
                    result_data=glossary_terms_to_result_data(glossary_terms),
                )
            )
        except Exception as glos_exc:  # non-fatal
            logger.warning(
                "Glossary extraction failed for %s (non-fatal): %s",
                source_file_id,
                glos_exc,
            )

        # Inconsistency detection (Story 2.7 closure) — non-fatal: any failure is
        # logged and the file still reaches READY. Reuses the requirements already
        # extracted above (NO re-extraction) via ``convert_to_schema`` and persists
        # AnalysisResult(module="inconsistencies"). The AC4 workflow status lives
        # inside result_data (default ``open`` per element).
        try:
            from app.services.analysis.document.inconsistency_detector import (
                detect_inconsistencies,
                inconsistencies_to_result_data,
            )
            from app.services.analysis.document.requirement_extractor import (
                convert_to_schema,
            )

            requirements_dicts = [convert_to_schema(r) for r in reqs]
            inconsistency_items = detect_inconsistencies(doc_structure, requirements_dicts)
            session.add(
                AnalysisResult(
                    tenant_id=tid,
                    project_id=source_file.project_id,
                    source_file_id=pid,
                    engine_mode=EngineMode.NATIVE,
                    module="inconsistencies",
                    status=AnalysisStatus.COMPLETED,
                    result_data=inconsistencies_to_result_data(inconsistency_items),
                )
            )
        except Exception as inc_exc:  # non-fatal
            logger.warning(
                "Inconsistency detection failed for %s (non-fatal): %s",
                source_file_id,
                inc_exc,
            )

        # Gap analysis (Story 2.8 closure) — non-fatal: any failure is logged
        # and the file still reaches READY. Maps the requirements already
        # extracted above (NO re-extraction) onto code entities read from the
        # project's persisted ``logic_structures`` AnalysisResult (Epic 1) via
        # the native ``GapAnalyzer``, then persists
        # AnalysisResult(module="gap_analysis"). No code analysis available ->
        # empty code entities -> every requirement resolves to
        # ``not_implemented`` (honest, non-fatal).
        try:
            from app.services.analysis.document.requirement_extractor import (
                convert_to_schema,
            )
            from app.services.analysis.gap_analyzer import (
                GapAnalyzer,
                code_entities_from_logic_structures,
                gap_analysis_to_result_data,
            )

            requirements_dicts = [convert_to_schema(r) for r in reqs]

            # Read code entities from the project's logic_structures (Epic 1).
            ls_result = await session.execute(
                select(AnalysisResult).where(
                    AnalysisResult.project_id == source_file.project_id,
                    AnalysisResult.module == "logic_structures",
                    AnalysisResult.status == AnalysisStatus.COMPLETED,
                )
            )
            ls_ar = ls_result.scalars().first()
            code_entities = code_entities_from_logic_structures(ls_ar.result_data if ls_ar else None)

            analyzer = GapAnalyzer()
            report, gap_items = analyzer.analyze_detailed(doc_structure, requirements_dicts, code_entities)
            session.add(
                AnalysisResult(
                    tenant_id=tid,
                    project_id=source_file.project_id,
                    source_file_id=pid,
                    engine_mode=EngineMode.NATIVE,
                    module="gap_analysis",
                    status=AnalysisStatus.COMPLETED,
                    result_data=gap_analysis_to_result_data(report, gap_items),
                )
            )
        except Exception as gap_exc:  # non-fatal
            logger.warning(
                "Gap analysis failed for %s (non-fatal): %s",
                source_file_id,
                gap_exc,
            )

        # Traceability matrix (Story 2.9 closure) — non-fatal: any failure is
        # logged and the file still reaches READY. Builds the document-centric
        # traceability matrix (requirement ↔ code ↔ test) reusing the
        # requirements already extracted above (NO re-extraction) and code
        # entities read from the project's persisted ``logic_structures``
        # AnalysisResult (Epic 1) via the native ``TraceabilityMatrixGenerator``
        # (name matching). ``test_cases`` is empty in v1 (Story 2.10 is
        # separate), so coverage is code-only: a code match → ``partial``, no
        # match → ``none`` (``full`` awaits test wiring). No code analysis
        # available → ``code_entities=[]`` → every requirement ``none``
        # (honest, non-fatal). Persisted in the flat frontend shape as
        # AnalysisResult(module="traceability").
        try:
            from app.services.analysis.document.requirement_extractor import (
                convert_to_schema,
            )
            from app.services.analysis.gap_analyzer import (
                code_entities_from_logic_structures,
            )
            from app.services.analysis.traceability import (
                generate_traceability_matrix,
                traceability_to_result_data,
            )

            requirements_dicts = [convert_to_schema(r) for r in reqs]

            # Read code entities from the project's logic_structures (Epic 1).
            ls_result = await session.execute(
                select(AnalysisResult).where(
                    AnalysisResult.project_id == source_file.project_id,
                    AnalysisResult.module == "logic_structures",
                    AnalysisResult.status == AnalysisStatus.COMPLETED,
                )
            )
            ls_ar = ls_result.scalars().first()
            code_entities = code_entities_from_logic_structures(ls_ar.result_data if ls_ar else None)

            matrix = generate_traceability_matrix(doc_structure, requirements_dicts, code_entities, [])
            session.add(
                AnalysisResult(
                    tenant_id=tid,
                    project_id=source_file.project_id,
                    source_file_id=pid,
                    engine_mode=EngineMode.NATIVE,
                    module="traceability",
                    status=AnalysisStatus.COMPLETED,
                    result_data=traceability_to_result_data(matrix),
                )
            )
        except Exception as trace_exc:  # non-fatal
            logger.warning(
                "Traceability matrix failed for %s (non-fatal): %s",
                source_file_id,
                trace_exc,
            )

        # Test generation (Story 2.10 closure) — non-fatal: any failure is
        # logged and the file still reaches READY. Generates test cases from
        # the requirements already extracted above (NO re-extraction) via the
        # native ``TestGenerator`` and persists
        # AnalysisResult(module="test_generation") in the flat frontend shape.
        # At least one positive case per requirement; complex requirements add
        # a negative case. Empty requirements → empty ``tests`` (non-fatal).
        # This wires the previously dead generator (its only other call site
        # was a live-dead API branch that never fired).
        try:
            from app.services.analysis.document.requirement_extractor import (
                convert_to_schema,
            )
            from app.services.analysis.test_generator import (
                generate_tests_from_requirements,
                test_generation_to_result_data,
            )

            requirements_dicts = [convert_to_schema(r) for r in reqs]
            tg_result = generate_tests_from_requirements(doc_structure, requirements_dicts)
            session.add(
                AnalysisResult(
                    tenant_id=tid,
                    project_id=source_file.project_id,
                    source_file_id=pid,
                    engine_mode=EngineMode.NATIVE,
                    module="test_generation",
                    status=AnalysisStatus.COMPLETED,
                    result_data=test_generation_to_result_data(tg_result),
                )
            )
        except Exception as tg_exc:  # non-fatal
            logger.warning(
                "Test generation failed for %s (non-fatal): %s",
                source_file_id,
                tg_exc,
            )

        # Mark file as READY — parsing complete
        source_file.processing_status = FileProcessingStatus.READY
        await session.commit()
        await session.refresh(analysis_result)

        return {
            "status": "completed",
            "source_file_id": source_file_id,
            "analysis_id": str(analysis_result.id),
            "document_structure": {
                "filename": doc_structure.metadata.get("filename", source_file.filename),
                "format": doc_structure.metadata.get("format", ""),
                "sections_count": doc_structure.metadata.get("sections_count", 0),
                "tables_count": doc_structure.metadata.get("tables_count", 0),
                "processing_time_ms": doc_structure.metadata.get("processing_time_ms", 0),
            },
        }


def _serialize_sections(sections: list) -> list[dict]:
    """Serialize hierarchical sections to a flat list for JSON storage.

    Walks the hierarchy depth-first (pre-order), so ``position`` reflects the
    order of appearance in the document and ``parent_section_id`` lets the
    ``/sections`` endpoint reconstruct the tree. Root-level sections are capped
    at 50 (see story 2.2 known limitation). Content is truncated per node to
    keep the JSONB payload bounded.
    """
    result: list[dict] = []
    position = 0

    def _walk(section_list: list, depth: int) -> None:
        nonlocal position
        limit = 50 if depth == 0 else None  # cap roots only
        for index, section in enumerate(section_list):
            if limit is not None and index >= limit:
                break
            max_len = 1000 if depth == 0 else 500
            content = section.content or ""
            result.append(
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "level": section.level,
                    "content": (content[:max_len] + "..." if len(content) > max_len else content),
                    "page_number": getattr(section, "page_number", None),
                    "position": position,
                    "section_type": getattr(section, "section_type", "unclassified"),
                    "parent_section_id": section.parent_section_id,
                    "children_count": len(section.children),
                }
            )
            position += 1
            if section.children:
                _walk(section.children, depth + 1)

    _walk(sections, 0)
    return result


@celery_app.task(
    bind=True,
    name="document.preprocess_document",
    max_retries=3,
    queue="analysis",
)
def parse_document_task(
    self,
    source_file_id: str,
    tenant_id: str,
) -> dict:
    """Parse and preprocess a documentation file asynchronously.

    Args:
        source_file_id: UUID of the source file to parse.
        tenant_id: UUID of the tenant (for RLS).

    Returns:
        Dictionary with preprocessing status and results.
    """
    task_id = self.request.id
    progress_svc = TaskProgressService()

    try:
        progress_svc.update_progress(task_id, 10, "Parsowanie dokumentu")
        result = asyncio.run(_parse_document_impl(source_file_id, tenant_id))

        progress_svc.complete_task(
            task_id,
            result_url=f"/api/v1/projects/{result.get('source_file_id', '')}/documents/{source_file_id}",
        )
        return result
    except SoftTimeLimitExceeded:
        logger.warning("Soft time limit exceeded for document preprocessing source_file=%s", source_file_id)
        asyncio.run(_mark_file_failed(source_file_id, tenant_id, "Processing time limit exceeded"))
        progress_svc.fail_task(task_id, "Processing time limit exceeded")
        return {
            "status": "timeout",
            "source_file_id": source_file_id,
            "error": "Processing time limit exceeded",
        }
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for document.preprocess_document (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error preprocessing document %s: %s", source_file_id, exc)
        asyncio.run(_mark_file_failed(source_file_id, tenant_id, str(exc)))
        progress_svc.fail_task(task_id, str(exc))
        return {
            "status": "failed",
            "source_file_id": source_file_id,
            "error": str(exc),
        }
