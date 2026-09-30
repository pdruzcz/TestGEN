"""Celery tasks for code error detection — Epic 5, Stories 5.4 + 5.10.

Fetches source files from DB + MinIO, parses each with tree-sitter,
runs the four per-file detectors (syntax / logic / semantic /
conformance), then the project-wide dead-code detector (5.10), and
persists CodeError rows. Findings dismissed as false_positive survive
rescans and suppress re-detection of the same code state (AC4).
"""

import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)
_MAX_CONTENT_BYTES = 1_048_576  # 1 MB

_DEFAULT_CATEGORIES = ["syntax", "logic", "semantic", "conformance", "dead_code"]


async def _run_code_error_detection_impl(
    project_id: str,
    tenant_id: str,
    categories: list[str],
) -> dict:
    from sqlalchemy import select, text

    from app.core.config import get_settings
    from app.core.database import task_session
    from app.core.storage import download_file_bytes
    from app.models.code_error import CodeError, CodeErrorStatus, ErrorCategory
    from app.models.source_file import FileCategory, SourceFile
    from app.services.analysis.ast.registry import ASTParserRegistry
    from app.services.gap_analysis.error_detectors import (
        ConformanceDetector,
        DeadCodeDetector,
        LogicDetector,
        ParsedFile,
        SemanticDetector,
        SyntaxDetector,
    )

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    settings = get_settings()

    # Map category strings to per-file detector instances (dead_code runs
    # as a separate project-wide pass — see below)
    detector_map = {
        ErrorCategory.SYNTAX: SyntaxDetector(),
        ErrorCategory.LOGIC: LogicDetector(),
        ErrorCategory.SEMANTIC: SemanticDetector(),
        ErrorCategory.CONFORMANCE: ConformanceDetector(),
    }
    active_categories = {ErrorCategory(c) for c in categories}
    detectors = [det for cat, det in detector_map.items() if cat in active_categories]

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        # --- 1. Fetch code source files ------------------------------------
        result = await session.execute(
            select(SourceFile).where(
                SourceFile.project_id == pid,
                SourceFile.file_category == FileCategory.CODE,
                SourceFile.is_cleaned_up == False,  # noqa: E712
            )
        )
        source_files = result.scalars().all()

        if not source_files:
            logger.warning(
                "Code error detection: no source files for project %s",
                project_id,
            )
            return {
                "status": "completed",
                "project_id": project_id,
                "total_errors": 0,
                "message": "No source files found",
            }

        # --- 2. Keep dismissed findings, clear the rest (AC4) --------------
        dismissed_result = await session.execute(
            select(CodeError.fingerprint).where(
                CodeError.project_id == pid,
                CodeError.tenant_id == tid,
                CodeError.status == CodeErrorStatus.FALSE_POSITIVE,
                CodeError.fingerprint.is_not(None),
            )
        )
        dismissed_fingerprints = {fp for fp in dismissed_result.scalars().all() if isinstance(fp, str)}

        await session.execute(
            text(
                f"DELETE FROM code_errors "
                f"WHERE project_id = '{pid}' AND tenant_id = '{tid}' "
                f"AND status != 'false_positive'"
            )
        )

        # --- 3. Parse + detect ---------------------------------------------
        registry = ASTParserRegistry.get_instance()
        all_errors = []
        parsed_files: list[ParsedFile] = []

        for sf in source_files:
            lang = (sf.detected_language or "").lower()
            if not lang or lang in ("unknown", "none"):
                continue
            if sf.file_size and sf.file_size > _MAX_CONTENT_BYTES:
                continue
            if not registry.is_supported(lang):
                continue

            # Download content from MinIO
            try:
                raw = download_file_bytes(
                    settings.minio_bucket_name,
                    sf.storage_key,
                )
                content = raw.decode("utf-8", errors="replace")
            except Exception as exc:
                logger.warning("Failed to download %s: %s", sf.storage_key, exc)
                continue

            file_path = sf.original_path or sf.filename

            # Parse with tree-sitter
            try:
                parser = registry.get_parser(lang)
                tree = parser.parse(content, file_path)
            except Exception as exc:
                logger.error("Parse failed for %s: %s", file_path, exc)
                continue

            parsed_files.append(ParsedFile(tree=tree, file_path=file_path, content=content))

            # Run active per-file detectors
            for detector in detectors:
                try:
                    detected = detector.detect(tree, file_path)
                    for d in detected:
                        all_errors.append(
                            CodeError(
                                tenant_id=tid,
                                project_id=pid,
                                source_file_id=sf.id,
                                category=d.category,
                                message=d.message,
                                file_path=d.file_path,
                                line_start=d.line_start,
                                line_end=d.line_end,
                                severity=d.severity,
                                rule_id=d.rule_id,
                                suggestion=d.suggestion,
                                context=d.context or None,
                            )
                        )
                except Exception as exc:
                    logger.error(
                        "Detector %s failed on %s: %s",
                        type(detector).__name__,
                        file_path,
                        exc,
                    )

        # --- 3b. Project-wide dead code pass (Story 5.10) ------------------
        if ErrorCategory.DEAD_CODE in active_categories:
            try:
                for d in DeadCodeDetector().detect_project(parsed_files):
                    fingerprint = (d.context or {}).get("fingerprint")
                    if fingerprint and fingerprint in dismissed_fingerprints:
                        continue  # dismissed for this code state — stays out
                    all_errors.append(
                        CodeError(
                            tenant_id=tid,
                            project_id=pid,
                            source_file_id=None,
                            category=d.category,
                            message=d.message,
                            file_path=d.file_path,
                            line_start=d.line_start,
                            line_end=d.line_end,
                            severity=d.severity,
                            rule_id=d.rule_id,
                            suggestion=d.suggestion,
                            context=d.context or None,
                            status=CodeErrorStatus.OPEN.value,
                            fingerprint=fingerprint,
                        )
                    )
            except Exception as exc:
                logger.error("DeadCodeDetector failed: %s", exc)

        # --- 4. Persist ----------------------------------------------------
        for err in all_errors:
            session.add(err)

        await session.commit()

        return {
            "status": "completed",
            "project_id": project_id,
            "total_errors": len(all_errors),
            "files_scanned": len(source_files),
        }


@celery_app.task(
    bind=True,
    name="code_error_detection.run",
    max_retries=3,
    queue="default",
)
def run_code_error_detection(
    self,
    project_id: str,
    tenant_id: str,
    categories: list[str] | None = None,
) -> dict:
    """Run code error detection for a project."""
    if categories is None:
        categories = list(_DEFAULT_CATEGORIES)

    try:
        return asyncio.run(
            _run_code_error_detection_impl(
                project_id,
                tenant_id,
                categories,
            )
        )
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for code_error_detection.run (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error(
            "Error running code error detection for project %s: %s",
            project_id,
            exc,
        )
        return {
            "status": "failed",
            "project_id": project_id,
            "error": str(exc),
        }
