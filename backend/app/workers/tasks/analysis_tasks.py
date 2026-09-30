"""Celery tasks for cross-diagram UML analysis — Epic 3, Story 3.7."""

import asyncio
import logging
import uuid

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (10, 60, 300)


async def _analyze_cross_diagrams_impl(
    project_id: str, tenant_id: str, diagram_ids: list[str] | None, engine_mode: str
) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.analysis.cross_diagram_analyzer import CrossDiagramAnalyzer

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    diag_uuids = [uuid.UUID(d) for d in diagram_ids] if diagram_ids else None

    llm_gateway = None
    if engine_mode in ("llm", "hybrid"):
        from app.services.analysis.llm_gateway import get_llm_gateway

        llm_gateway = get_llm_gateway()

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        analyzer = CrossDiagramAnalyzer(
            session,
            llm_gateway=llm_gateway,
            engine_mode=engine_mode,
            diagram_ids=diag_uuids,
        )
        result = await analyzer.analyze(pid, tid)
        await session.commit()
        return {
            "status": "completed",
            "project_id": project_id,
            "flows": len(result.user_flows),
            "coverage_warnings": result.coverage_warnings,
        }


@celery_app.task(
    bind=True,
    name="analysis.analyze_cross_diagrams",
    max_retries=3,
    queue="analysis",
)
def analyze_cross_diagrams(
    self,
    project_id: str,
    tenant_id: str,
    diagram_ids: list[str] | None = None,
    engine_mode: str = "native",
) -> dict:
    """Run cross-diagram analysis for a project and persist the user flows."""
    from app.services.task_progress_service import TaskProgressService

    progress = TaskProgressService()
    task_id = self.request.id
    try:
        # Story /analyze UML-only: ekran „Konfiguracja analizy" odpyta
        # /tasks/{id}; bez tego status wisiałby wiecznie na „pending".
        if task_id:
            progress.update_progress(task_id, 10, "analysis")
        result = asyncio.run(_analyze_cross_diagrams_impl(project_id, tenant_id, diagram_ids, engine_mode))
        if task_id:
            progress.complete_task(task_id, f"/api/v1/projects/{project_id}/uml/flows")
        return result
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.analyze_cross_diagrams (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in cross-diagram analysis for project %s: %s", project_id, exc)
        if task_id:
            progress.fail_task(task_id, str(exc))
        return {"status": "failed", "project_id": project_id, "error": str(exc)}


async def _analyze_gui_screenshot_impl(screenshot_id: str, tenant_id: str) -> dict:
    from sqlalchemy import select, text

    from app.core.database import task_session
    from app.core.storage import download_file_bytes
    from app.models.gui_screenshot import (
        GUIAnalysisResult,
        GUIAnalysisStatus,
        GUIComponent,
        GUIScreenshot,
    )
    from app.services.analysis.gui.orchestrator import GUIAnalyzerOrchestrator

    sid = uuid.UUID(screenshot_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        screenshot = (await session.execute(select(GUIScreenshot).where(GUIScreenshot.id == sid))).scalar_one_or_none()
        if screenshot is None:
            return {"status": "failed", "screenshot_id": screenshot_id, "error": "not found"}

        screenshot.status = GUIAnalysisStatus.PROCESSING
        await session.flush()

        from app.core.config import get_settings

        settings = get_settings()
        image_bytes = await asyncio.to_thread(download_file_bytes, settings.minio_bucket_name, screenshot.storage_key)

        orchestrator = GUIAnalyzerOrchestrator()
        output = orchestrator.analyze(image_bytes)

        analysis = GUIAnalysisResult(
            screenshot_id=sid,
            ocr_text_blocks=[
                {"text": tb.text, "bbox": tb.bbox.to_dict(), "confidence": tb.confidence} for tb in output.text_blocks
            ],
            layout_tree=output.layout_tree.to_dict() if output.layout_tree else None,
            warnings=output.warnings,
            processing_time_ms=output.processing_time_ms,
        )
        session.add(analysis)
        await session.flush()

        for idx, comp in enumerate(output.components):
            session.add(
                GUIComponent(
                    analysis_id=analysis.id,
                    sequence=idx,
                    component_type=comp.component_type,
                    label=comp.label,
                    bbox=comp.bbox.to_dict(),
                    confidence=comp.confidence,
                    attributes=comp.attributes or None,
                )
            )

        screenshot.status = GUIAnalysisStatus.COMPLETED
        await session.commit()
        return {
            "status": "completed",
            "screenshot_id": screenshot_id,
            "components": len(output.components),
            "text_blocks": len(output.text_blocks),
            "warnings": output.warnings,
        }


@celery_app.task(
    bind=True,
    name="analysis.analyze_gui_screenshot",
    max_retries=3,
    queue="analysis",
)
def analyze_gui_screenshot(self, screenshot_id: str, tenant_id: str) -> dict:
    """Run the GUI analysis pipeline for a screenshot and persist the results."""
    try:
        return asyncio.run(_analyze_gui_screenshot_impl(screenshot_id, tenant_id))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.analyze_gui_screenshot (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in GUI analysis for screenshot %s: %s", screenshot_id, exc)
        _mark_gui_failed(screenshot_id, tenant_id, str(exc))
        return {"status": "failed", "screenshot_id": screenshot_id, "error": str(exc)}


async def _analyze_dom_source_impl(
    source_file_id: str,
    tenant_id: str,
    a11y_storage_key: str | None = None,
    version_label: str | None = None,
) -> dict:
    """Analyse an HTML/DOM GUI source and persist components with real attributes.

    Story 1.51-zakańczenie (Part A). Reads the uploaded ``.html`` (and an optional
    ``a11y.json`` dump) from MinIO, runs :class:`DOMComponentExtractor`, and stores
    a ``GUIAnalysisResult`` of ``source_type='dom'`` whose ``GUIComponent`` rows
    carry populated ``attributes`` — the locator contract
    :class:`SelfHealingService` reads. The result attaches to the ``source_files``
    row (``screenshot_id`` is NULL), so healing loads it by ``analysis_id``
    unchanged. ``bbox`` is NULL: HTML carries no geometry (CV merge is optional).
    """
    from sqlalchemy import select, text

    from app.core.config import get_settings
    from app.core.database import task_session
    from app.core.storage import download_file_bytes
    from app.models.gui_screenshot import (
        GUIAnalysisResult,
        GUIAnalysisSourceType,
        GUIComponent,
    )
    from app.models.source_file import FileProcessingStatus, SourceFile
    from app.services.analysis.gui.dom_extractor import DOMComponentExtractor, parse_a11y_json

    sid = uuid.UUID(source_file_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        source = (await session.execute(select(SourceFile).where(SourceFile.id == sid))).scalar_one_or_none()
        if source is None:
            return {"status": "failed", "source_file_id": source_file_id, "error": "source not found"}

        settings = get_settings()
        html_bytes = await asyncio.to_thread(download_file_bytes, settings.minio_bucket_name, source.storage_key)
        html = html_bytes.decode("utf-8", errors="replace")

        a11y_payload = None
        if a11y_storage_key:
            try:
                a11y_bytes = await asyncio.to_thread(download_file_bytes, settings.minio_bucket_name, a11y_storage_key)
                a11y_payload = parse_a11y_json(a11y_bytes.decode("utf-8", errors="replace"))
            except Exception as exc:  # a11y is best-effort enrichment — never fatal
                logger.warning("a11y download/parse failed for %s: %s", a11y_storage_key, exc)

        components = DOMComponentExtractor().extract(html, a11y_json=a11y_payload)

        analysis = GUIAnalysisResult(
            source_type=GUIAnalysisSourceType.DOM,
            source_file_id=sid,
            screenshot_id=None,
            version_label=version_label,
            warnings=([] if components else ["Nie wykryto elementów interaktywnych w źródle DOM."]),
        )
        session.add(analysis)
        await session.flush()

        for idx, comp in enumerate(components):
            session.add(
                GUIComponent(
                    analysis_id=analysis.id,
                    sequence=idx,
                    component_type=comp.component_type,
                    label=comp.label,
                    bbox=None,
                    confidence=comp.confidence,
                    # DOM components always carry non-empty attributes (the locator
                    # contract). Persist them as-is — never collapse to NULL like the
                    # screenshot path's `{} or None` did before this story.
                    attributes=comp.attributes or None,
                )
            )

        source.processing_status = FileProcessingStatus.READY
        await session.commit()
        return {
            "status": "completed",
            "source_file_id": source_file_id,
            "analysis_id": str(analysis.id),
            "components": len(components),
        }


@celery_app.task(
    bind=True,
    name="analysis.analyze_dom_source",
    max_retries=3,
    queue="analysis",
)
def analyze_dom_source(
    self,
    source_file_id: str,
    tenant_id: str,
    a11y_storage_key: str | None = None,
    version_label: str | None = None,
) -> dict:
    """Run DOM/HTML GUI source analysis and persist components with locator attributes."""
    try:
        return asyncio.run(_analyze_dom_source_impl(source_file_id, tenant_id, a11y_storage_key, version_label))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.analyze_dom_source (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in DOM analysis for source %s: %s", source_file_id, exc)
        _mark_dom_source_failed(source_file_id, tenant_id, str(exc))
        return {"status": "failed", "source_file_id": source_file_id, "error": str(exc)}


def _mark_dom_source_failed(source_file_id: str, tenant_id: str, error: str) -> None:
    """Best-effort flip of a DOM source file to ``failed`` after a fatal error."""

    async def _impl() -> None:
        from sqlalchemy import select, text

        from app.core.database import task_session
        from app.models.source_file import FileProcessingStatus, SourceFile

        async with task_session() as session:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{uuid.UUID(tenant_id)}'"))
            source = (
                await session.execute(select(SourceFile).where(SourceFile.id == uuid.UUID(source_file_id)))
            ).scalar_one_or_none()
            if source is not None:
                source.processing_status = FileProcessingStatus.FAILED
                source.error_message = error[:1000]
                await session.commit()

    try:
        asyncio.run(_impl())
    except Exception as exc:  # pragma: no cover - best-effort cleanup
        logger.error("Failed to mark DOM source %s as failed: %s", source_file_id, exc)


async def _reconstruct_gui_flows_impl(
    project_id: str, tenant_id: str, screenshot_ids: list[str] | None, engine_mode: str
) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.analysis.gui.flow_reconstructor import GUIFlowReconstructor, enrich_with_llm
    from app.services.analysis.gui.flow_service import load_screen_analyses, persist_gui_flow

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    sid_uuids = [uuid.UUID(s) for s in screenshot_ids] if screenshot_ids else None

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))

        screens, warnings = await load_screen_analyses(session, pid, sid_uuids)
        result = GUIFlowReconstructor().reconstruct(screens)
        result.warnings = warnings + result.warnings

        if engine_mode in ("llm", "hybrid") and result.steps:
            from app.services.analysis.llm_gateway import get_llm_gateway

            result = await enrich_with_llm(result, screens, get_llm_gateway(), tenant_id=tid)

        flow = await persist_gui_flow(session, pid, tid, result)
        await session.commit()
        return {
            "status": "completed",
            "project_id": project_id,
            "flow_id": str(flow.id),
            "steps": len(result.steps),
            "warnings": result.warnings,
        }


@celery_app.task(
    bind=True,
    name="analysis.reconstruct_gui_flows",
    max_retries=3,
    queue="analysis",
)
def reconstruct_gui_flows(
    self,
    project_id: str,
    tenant_id: str,
    screenshot_ids: list[str] | None = None,
    engine_mode: str = "native",
) -> dict:
    """Reconstruct a GUI user flow from a screenshot sequence and persist it."""
    try:
        return asyncio.run(_reconstruct_gui_flows_impl(project_id, tenant_id, screenshot_ids, engine_mode))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.reconstruct_gui_flows (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in GUI flow reconstruction for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}


async def _generate_gherkin_impl(
    project_id: str, tenant_id: str, flow_ids: list[str], engine_mode: str, feature_name: str | None
) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.test_generation.gherkin_service import generate_for_flow

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    flow_uuids = [uuid.UUID(f) for f in flow_ids]

    llm_gateway = None
    if engine_mode in ("llm", "hybrid"):
        from app.services.analysis.llm_gateway import get_llm_gateway

        llm_gateway = get_llm_gateway()

    generated: list[str] = []
    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        for flow_uuid in flow_uuids:
            record = await generate_for_flow(
                session,
                pid,
                flow_uuid,
                engine_mode=engine_mode,
                feature_name=feature_name,
                llm_gateway=llm_gateway,
                tenant_id=tid,
            )
            if record is not None:
                generated.append(str(record.id))
        await session.commit()

    return {
        "status": "completed",
        "project_id": project_id,
        "features": len(generated),
        "feature_ids": generated,
    }


@celery_app.task(
    bind=True,
    name="analysis.generate_gherkin",
    max_retries=3,
    queue="analysis",
)
def generate_gherkin(
    self,
    project_id: str,
    tenant_id: str,
    flow_ids: list[str],
    engine_mode: str = "native",
    feature_name: str | None = None,
) -> dict:
    """Generate and persist Gherkin features from reconstructed user flows."""
    try:
        return asyncio.run(_generate_gherkin_impl(project_id, tenant_id, flow_ids, engine_mode, feature_name))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.generate_gherkin (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in Gherkin generation for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}


async def _generate_cypress_code_impl(
    project_id: str, tenant_id: str, test_case_ids: list[str], base_url: str | None
) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.test_generation.codegen_service import generate_code_for_test_cases

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    tc_uuids = [uuid.UUID(t) for t in test_case_ids]

    generated: list[str] = []
    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        records = await generate_code_for_test_cases(
            session,
            pid,
            tc_uuids,
            framework="cypress",
            base_url=base_url,
            tenant_id=tid,
        )
        generated = [str(r.id) for r in records]
        await session.commit()

    return {
        "status": "completed",
        "project_id": project_id,
        "generated": len(generated),
        "code_ids": generated,
    }


@celery_app.task(
    bind=True,
    name="analysis.generate_cypress_code",
    max_retries=3,
    queue="analysis",
)
def generate_cypress_code(
    self,
    project_id: str,
    tenant_id: str,
    test_case_ids: list[str],
    base_url: str | None = None,
) -> dict:
    """Generate and persist Cypress test code for the given test cases."""
    try:
        return asyncio.run(_generate_cypress_code_impl(project_id, tenant_id, test_case_ids, base_url))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.generate_cypress_code (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in Cypress code generation for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}


async def _generate_sikulix_code_impl(project_id: str, tenant_id: str, test_case_ids: list[str]) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.test_generation.sikulix_pipeline import generate_sikulix_code

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    tc_uuids = [uuid.UUID(t) for t in test_case_ids]

    generated: list[str] = []
    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        records = await generate_sikulix_code(
            session,
            pid,
            tc_uuids,
            tenant_id=tid,
        )
        generated = [str(r.id) for r in records]
        await session.commit()

    return {
        "status": "completed",
        "project_id": project_id,
        "generated": len(generated),
        "code_ids": generated,
    }


@celery_app.task(
    bind=True,
    name="analysis.generate_sikulix_code",
    max_retries=3,
    queue="analysis",
)
def generate_sikulix_code(
    self,
    project_id: str,
    tenant_id: str,
    test_case_ids: list[str],
) -> dict:
    """Generate and persist SikuliX test code for the given test cases."""
    try:
        return asyncio.run(_generate_sikulix_code_impl(project_id, tenant_id, test_case_ids))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.generate_sikulix_code (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in SikuliX code generation for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}


async def _generate_database_code_impl(project_id: str, tenant_id: str, test_case_ids: list[str]) -> dict:
    """Generate and persist database-layer pytest code (Story 1.53, FR70).

    Reuses the shared codegen pipeline (``generate_code_for_test_cases``) with
    framework ``"database"`` — the ``DatabaseCodeGenerator`` renders isolated
    pytest (``db_session`` + rollback) from ``test_type = database`` cases.
    """
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.test_generation.codegen_service import generate_code_for_test_cases

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    tc_uuids = [uuid.UUID(t) for t in test_case_ids]

    generated: list[str] = []
    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        records = await generate_code_for_test_cases(
            session,
            pid,
            tc_uuids,
            framework="database",
            tenant_id=tid,
        )
        generated = [str(r.id) for r in records]
        await session.commit()

    return {
        "status": "completed",
        "project_id": project_id,
        "generated": len(generated),
        "code_ids": generated,
    }


@celery_app.task(
    bind=True,
    name="analysis.generate_database_code",
    max_retries=3,
    queue="analysis",
)
def generate_database_code(
    self,
    project_id: str,
    tenant_id: str,
    test_case_ids: list[str],
) -> dict:
    """Generate and persist database-layer pytest test code (Story 1.53, FR70)."""
    try:
        return asyncio.run(_generate_database_code_impl(project_id, tenant_id, test_case_ids))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.generate_database_code (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in DB code generation for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}


async def _generate_php_code_impl(project_id: str, tenant_id: str, test_case_ids: list[str], framework: str) -> dict:
    """Generate and persist PHPUnit/Pest test code (Story 1.55, FR24/FR12).

    Reuses the shared codegen pipeline (``generate_code_for_test_cases``) with
    framework ``"phpunit"``/``"pest"`` — registered PHP generators render
    PHPUnit classes or Pest DSL from the selected test cases.
    """
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.test_generation.codegen_service import generate_code_for_test_cases

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    tc_uuids = [uuid.UUID(t) for t in test_case_ids]

    generated: list[str] = []
    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        records = await generate_code_for_test_cases(
            session,
            pid,
            tc_uuids,
            framework=framework,
            tenant_id=tid,
        )
        generated = [str(r.id) for r in records]
        await session.commit()

    return {
        "status": "completed",
        "project_id": project_id,
        "generated": len(generated),
        "code_ids": generated,
    }


@celery_app.task(
    bind=True,
    name="analysis.generate_phpunit_code",
    max_retries=3,
    queue="analysis",
)
def generate_phpunit_code(
    self,
    project_id: str,
    tenant_id: str,
    test_case_ids: list[str],
) -> dict:
    """Generate and persist PHPUnit test code (Story 1.55, FR24/FR12)."""
    try:
        return asyncio.run(_generate_php_code_impl(project_id, tenant_id, test_case_ids, "phpunit"))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.generate_phpunit_code (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in PHPUnit code generation for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}


@celery_app.task(
    bind=True,
    name="analysis.generate_pest_code",
    max_retries=3,
    queue="analysis",
)
def generate_pest_code(
    self,
    project_id: str,
    tenant_id: str,
    test_case_ids: list[str],
) -> dict:
    """Generate and persist Pest test code (Story 1.55, FR24/FR12)."""
    try:
        return asyncio.run(_generate_php_code_impl(project_id, tenant_id, test_case_ids, "pest"))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.generate_pest_code (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error in Pest code generation for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}


async def _generate_framework_code_impl(
    project_id: str,
    tenant_id: str,
    test_case_ids: list[str],
    framework: str,
    platform: str | None = None,
) -> dict:
    """Generate and persist test code for any registered codegen framework.

    Stories 1.56/1.57: reuses the shared codegen pipeline
    (``generate_code_for_test_cases``) — registered generators render the
    code (selenium/playwright/appium, unittest/testng/mstest). ``platform``
    (Appium only) drives desired capabilities: android → UiAutomator2,
    ios → XCUITest.
    """
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.test_generation.codegen_service import generate_code_for_test_cases

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)
    tc_uuids = [uuid.UUID(t) for t in test_case_ids]

    generated: list[str] = []
    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        records = await generate_code_for_test_cases(
            session,
            pid,
            tc_uuids,
            framework=framework,
            tenant_id=tid,
            platform=platform,
        )
        generated = [str(r.id) for r in records]
        await session.commit()

    return {
        "status": "completed",
        "project_id": project_id,
        "generated": len(generated),
        "code_ids": generated,
    }


def _framework_code_task(framework: str):
    """Build a Celery task for a codegen framework (Stories 1.56/1.57)."""
    task_name = f"analysis.generate_{framework}_code"

    def _run(self, project_id: str, tenant_id: str, test_case_ids: list[str], platform: str | None = None) -> dict:
        try:
            return asyncio.run(_generate_framework_code_impl(project_id, tenant_id, test_case_ids, framework, platform))
        except (ConnectionError, OSError) as exc:
            retry_num = self.request.retries
            delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
            logger.warning(
                "Retry %d/%d for %s (delay=%ds): %s",
                retry_num + 1,
                self.max_retries,
                task_name,
                delay,
                exc,
            )
            raise self.retry(exc=exc, countdown=delay) from exc
        except Exception as exc:
            logger.error("Error in %s code generation for project %s: %s", framework, project_id, exc)
            return {"status": "failed", "project_id": project_id, "error": str(exc)}

    return celery_app.task(bind=True, name=task_name, max_retries=3, queue="analysis")(_run)


generate_selenium_code = _framework_code_task("selenium")
generate_playwright_code = _framework_code_task("playwright")
generate_appium_code = _framework_code_task("appium")
generate_unittest_code = _framework_code_task("unittest")
generate_testng_code = _framework_code_task("testng")
generate_mstest_code = _framework_code_task("mstest")


async def _build_traceability_matrix_impl(project_id: str, tenant_id: str) -> dict:
    from sqlalchemy import text

    from app.core.database import task_session
    from app.services.analysis.traceability_service import TraceabilityService

    pid = uuid.UUID(project_id)
    tid = uuid.UUID(tenant_id)

    async with task_session() as session:
        await session.execute(text(f"SET LOCAL app.current_tenant = '{tid}'"))
        service = TraceabilityService(session)
        count = await service.build_matrix(pid, tid)
        await session.commit()
        return {"status": "completed", "project_id": project_id, "elements": count}


@celery_app.task(
    bind=True,
    name="analysis.build_traceability_matrix",
    max_retries=3,
    queue="analysis",
)
def build_traceability_matrix(self, project_id: str, tenant_id: str) -> dict:
    """(Re)build the traceability matrix for a project (Story 3.15)."""
    try:
        return asyncio.run(_build_traceability_matrix_impl(project_id, tenant_id))
    except (ConnectionError, OSError) as exc:
        retry_num = self.request.retries
        delay = _RETRY_DELAYS[retry_num] if retry_num < len(_RETRY_DELAYS) else _RETRY_DELAYS[-1]
        logger.warning(
            "Retry %d/%d for analysis.build_traceability_matrix (delay=%ds): %s",
            retry_num + 1,
            self.max_retries,
            delay,
            exc,
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        logger.error("Error building traceability matrix for project %s: %s", project_id, exc)
        return {"status": "failed", "project_id": project_id, "error": str(exc)}


def _mark_gui_failed(screenshot_id: str, tenant_id: str, error: str) -> None:
    """Best-effort flip of a screenshot to ``failed`` after a fatal error."""

    async def _impl() -> None:
        from sqlalchemy import select, text

        from app.core.database import task_session
        from app.models.gui_screenshot import GUIAnalysisStatus, GUIScreenshot

        async with task_session() as session:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{uuid.UUID(tenant_id)}'"))
            screenshot = (
                await session.execute(select(GUIScreenshot).where(GUIScreenshot.id == uuid.UUID(screenshot_id)))
            ).scalar_one_or_none()
            if screenshot is not None:
                screenshot.status = GUIAnalysisStatus.FAILED
                screenshot.error_message = error[:1000]
                await session.commit()

    try:
        asyncio.run(_impl())
    except Exception as exc:  # pragma: no cover - best effort
        logger.error("Could not mark GUI screenshot %s failed: %s", screenshot_id, exc)
