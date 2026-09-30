"""Pipeline orchestrator — sequential step execution in Celery workers.

Each step is a pure function: ``step_func(context: PipelineContext) -> StepResult``.
The orchestrator updates progress in Redis after every step and handles
partial failures gracefully.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from celery.exceptions import SoftTimeLimitExceeded

from app.core.database import get_sync_session, set_rls_context
from app.services.task_progress_service import TaskProgressService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    task_id: str
    tenant_id: str
    project_id: str
    engine_mode: str
    modules: list[str]
    test_framework: str | None = None
    llm_model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    intermediate_results: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class PipelineStep:
    name: str
    func: Callable[[PipelineContext], StepResult]
    weight: int  # progress weight (percent)


def run_pipeline_steps(
    ctx: PipelineContext,
    steps: list[PipelineStep],
    continue_on_failure: bool = False,
) -> list[StepResult]:
    """Execute pipeline steps sequentially, updating progress in Redis."""
    progress_svc = TaskProgressService()
    total_weight = sum(s.weight for s in steps)
    completed_weight = 0
    results: list[StepResult] = []
    failed_steps: list[str] = []

    for step in steps:
        logger.info("task=%s step=%s — starting", ctx.task_id, step.name)
        result = step.func(ctx)
        results.append(result)

        if result.success:
            completed_weight += step.weight
            if result.data:
                ctx.intermediate_results[step.name] = result.data
        else:
            failed_steps.append(step.name)
            logger.warning(
                "task=%s step=%s — failed: %s",
                ctx.task_id,
                step.name,
                result.error,
            )
            if not continue_on_failure:
                progress_svc.fail_task(ctx.task_id, f"Step '{step.name}' failed: {result.error}")
                return results

        progress_pct = min(int((completed_weight / total_weight) * 100), 100)
        progress_svc.update_progress(ctx.task_id, progress_pct, step.name)

    if failed_steps:
        progress_svc.partial_failure(
            ctx.task_id,
            error=f"Steps failed: {', '.join(failed_steps)}",
            completed_steps=[s.name for s in steps if s.name not in failed_steps],
        )
    else:
        progress_svc.complete_task(ctx.task_id, f"/api/v1/tasks/{ctx.task_id}/result")

    return results


# ── Framework resolution: language + FrameworkDetector → codegen (Story 1.55) ─


def _resolve_test_framework(language: str, detected_frameworks: list[str] | None = None):
    """Rozwiąż framework kodu testowego z języka + wykryć preprocessingu.

    Story 1.55 (FR24/FR12): wykryty phpunit/pest z ``FrameworkDetector``
    (krok preprocessingu, ``intermediate_results["preprocessing"]["frameworks"]``)
    faktycznie steruje codegenem — zamiast fallbacku PYTEST dla PHP.
    Pest (DSL nad PHPUnit) ma priorytet, mirror ``_detect_php``.
    Wykrycia innych języków nie przejmują sterowania (projekty mieszane).
    """
    from app.models.test_case import TestFramework as FrameworkEnum

    framework_map = {
        "python": FrameworkEnum.PYTEST,
        "javascript": FrameworkEnum.MOCHA,
        "typescript": FrameworkEnum.JEST,
        "java": FrameworkEnum.JUNIT,
        "c#": FrameworkEnum.NUNIT,
        "php": FrameworkEnum.PHPUNIT,  # domyślnie PHPUnit; Pest nadpisuje detekcją
    }
    framework = framework_map.get(language.lower(), FrameworkEnum.PYTEST)

    detected = [d.lower() for d in (detected_frameworks or [])]
    lang = language.lower()
    if lang == "php":
        # Story 1.55: Pest (DSL nad PHPUnit) ma priorytet, mirror _detect_php
        if "pest" in detected:
            framework = FrameworkEnum.PEST
        elif "phpunit" in detected:
            framework = FrameworkEnum.PHPUNIT
    # Story 1.57 (AC2): wykryte natywne frameworki projektu (FrameworkDetector)
    # sterują codegenem — „— Automatyczny —" mapuje na framework projektu,
    # nie na domyślny językowy. Detekcja obcego języka nie przejmuje.
    elif lang == "python" and ("unittest" in detected or "nose2" in detected):
        framework = FrameworkEnum.UNITTEST
    elif lang == "java" and "testng" in detected:
        framework = FrameworkEnum.TESTNG
    elif lang == "c#" and "mstest" in detected:
        framework = FrameworkEnum.MSTEST
    return framework


def _user_selected_framework(value):
    """Rozwiąż framework wybrany przez użytkownika w „Parametrach analizy".

    Story 1.56 (AC3): ``test_framework`` z ``AnalysisRequest`` (przeniesiony
    do ``PipelineContext``) ma pierwszeństwo nad rozpoznaniem z języka.
    Zwraca ``None`` dla braku/nieznanej wartości — wtedy caller spada
    do ``_resolve_test_framework`` (zachowanie sprzed story).
    """
    if not value:
        return None

    from app.models.test_case import TestFramework as FrameworkEnum

    try:
        return FrameworkEnum(value)
    except ValueError:
        logger.warning("Nieznany test_framework=%r — fallback na rozpoznanie z języka", value)
        return None


def _llm_framework_for(framework):
    """Mapuj modelowy TestFramework na LLMTestFramework (ścieżka LLM, Story 1.55).

    Mapowanie po ``framework.name`` (nie ``.value``) — przed Story 1.55 klucze
    uppercase nigdy nie trafiały w lowercase'owe ``.value`` i każdy framework
    wypadał jako PYTEST.
    """
    from app.services.generators.llm_test_generator import LLMTestFramework

    llm_fw_map = {
        "PYTEST": LLMTestFramework.PYTEST,
        "JUNIT": LLMTestFramework.JUNIT,
        "NUNIT": LLMTestFramework.NUNIT,
        "MOCHA": LLMTestFramework.MOCHA,
        "JEST": LLMTestFramework.JEST,
        "PHPUNIT": LLMTestFramework.PHPUNIT,
        "PEST": LLMTestFramework.PEST,
        # Story 1.56 (AC3) — wybór e2e użytkownika na ścieżce llm/hybrid
        "SELENIUM": LLMTestFramework.SELENIUM,
        "PLAYWRIGHT": LLMTestFramework.PLAYWRIGHT,
        "APPIUM": LLMTestFramework.APPIUM,
        # Story 1.57 — natywne frameworki wykrywane w projektach
        "UNITTEST": LLMTestFramework.UNITTEST,
        "TESTNG": LLMTestFramework.TESTNG,
        "MSTEST": LLMTestFramework.MSTEST,
    }
    return llm_fw_map.get(framework.name, LLMTestFramework.PYTEST)


# ── Step 1: Preprocessing (language/framework detection) ─────────────────────


def _step_preprocessing(ctx: PipelineContext) -> StepResult:
    """Run real preprocessing — language detection, framework detection, LOC counting."""

    async def _run() -> Any:
        from sqlalchemy import text

        from app.core.database import task_session
        from app.services.project.preprocessing_service import PreprocessingService

        service = PreprocessingService()
        async with task_session() as session:
            await session.execute(text(f"SET LOCAL app.current_tenant = '{ctx.tenant_id}'"))
            report = await service.run_preprocessing(session, uuid.UUID(ctx.project_id))
            await session.commit()
        return report

    try:
        report = asyncio.run(_run())
    except Exception as exc:
        logger.error("Preprocessing failed: %s", exc)
        return StepResult(success=False, error=str(exc))

    file_count = sum(ls.count for ls in report.languages)
    ctx.intermediate_results["preprocessing"] = {
        "total_loc": report.total_loc,
        "languages": [{"language": ls.language, "count": ls.count, "loc": ls.loc} for ls in report.languages],
        "frameworks": report.detected_frameworks,
        "file_count": file_count,
    }
    return StepResult(success=True, data=ctx.intermediate_results["preprocessing"])


# ── Step 2: AST parsing — validate files & check parser support ─────────────


def _step_ast_parsing(ctx: PipelineContext) -> StepResult:
    """Load source files from MinIO and validate AST parser support."""
    from app.services.analysis.ast.registry import ASTParserRegistry
    from app.services.analysis.pipeline_helpers import fetch_project_source_files

    try:
        with get_sync_session() as session:
            set_rls_context(session, ctx.tenant_id)
            source_files, warnings = fetch_project_source_files(session, ctx.project_id, ctx.tenant_id)
    except Exception as exc:
        logger.error("AST parsing — file retrieval failed: %s", exc)
        return StepResult(success=False, error=str(exc))

    if not source_files:
        return StepResult(success=False, error="No valid source files found for analysis")

    # Check which files have supported AST parsers
    registry = ASTParserRegistry.get_instance()
    supported = [f for f in source_files if registry.is_supported(f.language)]
    unsupported = [f for f in source_files if not registry.is_supported(f.language)]

    if unsupported:
        unsupported_langs = {f.language for f in unsupported}
        warnings.append(f"Skipped {len(unsupported)} files — no parser for: {', '.join(unsupported_langs)}")

    if not supported:
        return StepResult(
            success=False,
            error=f"No files with supported languages. Supported: {registry.supported_languages()}",
        )

    data = {
        "total_files": len(source_files),
        "supported_files": len(supported),
        "unsupported_files": len(unsupported),
        "warnings": warnings,
        # Cache loaded files for next step to avoid re-downloading
        "loaded_files": [
            {
                "file_path": f.file_path,
                "content": f.content,
                "language": f.language,
                "source_file_id": f.source_file_id,
            }
            for f in supported
        ],
    }
    ctx.intermediate_results["ast_parsing"] = data
    return StepResult(success=True, data=data)


# ── Step 3: Analysis — run native analysis orchestrator ──────────────────────


def _step_analysis(ctx: PipelineContext) -> StepResult:
    """Run full native analysis (AST → logic structures, entry points, deps, data flow, biz logic)."""
    from app.models.analysis_result import AnalysisResult, AnalysisStatus, EngineMode
    from app.services.analysis.native_analysis import NativeAnalysisOrchestrator

    # Use cached files from ast_parsing step
    ast_data = ctx.intermediate_results.get("ast_parsing", {})
    loaded_files = ast_data.get("loaded_files", [])

    if not loaded_files:
        return StepResult(success=False, error="No files available from AST parsing step")

    logger.info("task=%s — analysis: %d files to analyze", ctx.task_id, len(loaded_files))

    # Build dicts for NativeAnalysisOrchestrator
    file_dicts = [
        {"file_path": f["file_path"], "content": f["content"], "language": f["language"]} for f in loaded_files
    ]

    # File path → source_file_id mapping (needed by test generation step)
    source_file_ids = {f["file_path"]: f["source_file_id"] for f in loaded_files}

    start = time.monotonic()
    try:
        logger.info("task=%s — analysis: calling NativeAnalysisOrchestrator", ctx.task_id)
        orchestrator = NativeAnalysisOrchestrator()
        result = orchestrator.analyze_project(
            file_dicts,
            project_id=0,  # not used when save_to_db=False
            save_to_db=False,
        )
        logger.info(
            "task=%s — analysis: orchestrator done in %dms", ctx.task_id, int((time.monotonic() - start) * 1000)
        )
    except Exception as exc:
        logger.error("Native analysis failed: %s", exc)
        return StepResult(success=False, error=str(exc))
    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Save AnalysisResult to DB with proper RLS context
    logger.info("task=%s — analysis: saving AnalysisResult to DB", ctx.task_id)
    analysis_result_id: str | None = None
    try:
        with get_sync_session() as session:
            set_rls_context(session, ctx.tenant_id)
            ar = AnalysisResult(
                tenant_id=uuid.UUID(ctx.tenant_id),
                project_id=uuid.UUID(ctx.project_id),
                engine_mode=EngineMode(ctx.engine_mode),
                module="native_analysis",
                status=AnalysisStatus.COMPLETED,
                result_data=result.to_dict(),
                duration_ms=elapsed_ms,
            )
            session.add(ar)
            session.commit()
            session.refresh(ar)
            analysis_result_id = str(ar.id)
            logger.info("task=%s — AnalysisResult saved id=%s", ctx.task_id, analysis_result_id)
    except Exception as exc:
        logger.error("Failed to save AnalysisResult: %s", exc)
        return StepResult(success=False, error=f"Failed to save analysis result: {exc}")

    # Determine primary language for test generation
    language = result.language if result.language != "multi" else "python"

    data = {
        "analysis_result_id": analysis_result_id,
        "language": language,
        "source_file_ids": source_file_ids,
        "analysis_dict": result.to_dict(),
        "duration_ms": elapsed_ms,
        "statistics": result.get_statistics(),
        "combined_metrics": result.get_combined_metrics(),
    }
    ctx.intermediate_results["analysis"] = data
    return StepResult(success=True, data=data)


# ── Step 4: Test generation — generate test cases & save to DB ───────────────

# Max source files for LLM generation (prevent excessive API costs)
_LLM_MAX_FILES = 10


def _llm_available() -> tuple[bool, str]:
    """Check if LLM API keys are configured. Returns (available, provider)."""
    from app.core.config import get_settings

    settings = get_settings()
    openai_key = settings.openai_api_key.get_secret_value()
    anthropic_key = settings.anthropic_api_key.get_secret_value()
    if openai_key:
        return True, "openai"
    if anthropic_key:
        return True, "anthropic"
    return False, ""


def _run_native_generation(
    analysis_dict: dict,
    language: str,
    framework,  # TestFramework enum from test_case model
    gen_framework,  # TestFramework enum from native_test_generator
) -> dict:
    """Run native (template-based) test generation. Returns intermediate results."""
    from app.services.generators.native_test_generator import (
        NativeTestGenerator,
    )
    from app.services.generators.native_test_generator import (
        TestType as GenTestType,
    )
    from app.services.generators.negative_scenarios import NegativeScenarioGenerator
    from app.services.generators.positive_scenarios import PositiveScenarioGenerator

    # Extract structures from analysis
    entry_points_raw = analysis_dict.get("entry_points") or {}
    logic_structures_raw = analysis_dict.get("logic_structures") or {}
    endpoints = entry_points_raw.get("endpoints", []) if isinstance(entry_points_raw, dict) else []
    functions = logic_structures_raw.get("functions", []) if isinstance(logic_structures_raw, dict) else []
    classes = logic_structures_raw.get("classes", []) if isinstance(logic_structures_raw, dict) else []

    # NativeTestGenerator (code-level tests)
    generator = NativeTestGenerator()
    test_suite = generator.generate_tests(
        analysis_result=analysis_dict,
        framework=gen_framework,
        test_type=GenTestType.POSITIVE,
    )

    # Positive scenario generator
    pos_gen = PositiveScenarioGenerator()
    positive_scenarios = []
    for func in functions[:20]:
        positive_scenarios.extend(pos_gen.generate_from_function(func, language, framework))
    for ep in endpoints[:20]:
        positive_scenarios.extend(pos_gen.generate_from_endpoint(ep, language, framework))
    for cls in classes[:10]:
        positive_scenarios.extend(pos_gen.generate_from_class(cls, language, framework))

    # Negative scenario generator
    neg_gen = NegativeScenarioGenerator()
    negative_scenarios = []
    for func in functions[:20]:
        negative_scenarios.extend(neg_gen.generate_all_negative_scenarios(func, language, framework))
    for ep in endpoints[:20]:
        negative_scenarios.extend(neg_gen.generate_all_endpoint_scenarios(ep, language, framework))

    return {
        "test_suite": test_suite,
        "positive_scenarios": positive_scenarios,
        "negative_scenarios": negative_scenarios,
    }


def _run_llm_generation(
    source_files: list[dict],
    language: str,
    framework,  # TestFramework enum from test_case model
    analysis_dict: dict,
    provider: str,
    tenant_id: str | None = None,
    project_id: str | None = None,
    analysis_result_id: str | None = None,
    use_llm_detection: bool = True,
) -> list:
    """Run LLM-based test generation. Returns list of LLMGeneratedTest.

    Story 1.54 (FR72): when anonymization is enabled and tenant/project
    context is present, source code is tokenized (secrets/URLs/domain
    identifiers) before it leaves the tenant boundary; the mapping is
    persisted encrypted (AES-256-GCM, RLS) and the LLM output is
    detokenized before persistence. Anonymization runs inside the same
    event loop as the LLM call (shared gateway HTTP client).
    """
    from app.core.config import get_settings
    from app.models.llm_usage import LLMProvider
    from app.services.generators.llm_test_generator import get_llm_test_generator

    llm_generator = get_llm_test_generator()

    # Map framework enum to LLM framework (Story 1.55: po .name, z PHPUNIT/PEST)
    llm_framework = _llm_framework_for(framework)
    llm_provider = LLMProvider.OPENAI if provider == "openai" else LLMProvider.ANTHROPIC

    files = source_files[:_LLM_MAX_FILES]
    anonymize = bool(tenant_id and project_id and get_settings().anonymization_enabled)
    anon_state: dict = {}

    async def _generate():
        llm_source_files = [(f["file_path"], f["content"]) for f in files]
        if anonymize:
            from app.services.analysis.anonymization import AnonymizationService

            service = AnonymizationService(llm_gateway=_optional_llm_gateway() if use_llm_detection else None)
            token_count = secret_count = 0
            anon_pairs = []
            for f in files:
                ast_tree = _try_parse_ast(f["content"], f.get("language"), f["file_path"])
                result = await service.anonymize_with_stats(
                    f["content"],
                    ast_tree=ast_tree,
                    use_llm_detection=use_llm_detection,
                )
                anon_pairs.append((f["file_path"], result.source))
                token_count += result.token_count
                secret_count += result.secret_count
            anon_state.update(service=service, token_count=token_count, secret_count=secret_count)
            if anon_pairs:
                llm_source_files = anon_pairs

        suite = await llm_generator.generate_test_suite(
            source_files=llm_source_files,
            language=language,
            framework=llm_framework,
            analysis_results=analysis_dict,
            provider=llm_provider,
        )

        service = anon_state.get("service")
        if service is not None and service.mapping:
            await _deanonymize_llm_tests(suite.test_cases, service.mapping)
        return suite

    try:
        suite = asyncio.run(_generate())
    except Exception:
        # Fail-closed (FR72): jeżeli cokolwiek w anonymizacji wywaliło,
        # kod NIE wychodzi z tenanta — wyjątek idzie wyżej, a step
        # test_generation ma istniejący fallback na native.
        if anonymize and not anon_state:
            logger.exception("Anonymization failed — aborting LLM generation")
        raise

    service = anon_state.get("service")
    if anonymize and service is not None and service.mapping:
        try:
            _persist_anonymization_mapping(
                tenant_id=tenant_id,
                project_id=project_id,
                analysis_result_id=analysis_result_id,
                mapping=service.mapping,
                token_count=anon_state["token_count"],
                secret_count=anon_state["secret_count"],
            )
        except Exception as exc:
            # Mapping nie wyciekł (nie ma wiersza = nie ma danych); testy już
            # detokenizowane — degradacja dostępności retencji, nie bezpieczeństwa.
            logger.error("Anonymization mapping persist failed: %s", exc)

    return suite.test_cases, suite.total_tokens_used


def _try_parse_ast(content: str, language: str | None, file_path: str):
    """Best-effort AST parse; None when the language is unsupported."""
    if not language:
        return None
    try:
        from app.services.analysis.ast.registry import ASTParserRegistry

        registry = ASTParserRegistry.get_instance()
        if not registry.is_supported(language):
            return None
        return registry.get_parser(language).parse(content, source_path=file_path)
    except Exception as exc:  # parsing is optional enrichment — never fatal
        logger.warning("AST parse failed for anonymization (%s): %s", file_path, exc)
        return None


def _optional_llm_gateway():
    """Gateway for contextual identifier detection; None when unavailable."""
    try:
        from app.services.analysis.llm_gateway import get_llm_gateway

        return get_llm_gateway()
    except Exception:
        return None


def _persist_anonymization_mapping(
    tenant_id: str,
    project_id: str,
    analysis_result_id: str | None,
    mapping: dict[str, str],
    token_count: int,
    secret_count: int,
):
    """Persist the encrypted mapping + counts-only audit row (RLS context)."""
    import json
    from datetime import UTC, datetime, timedelta

    from app.core.config import get_settings
    from app.core.encryption import encrypt_bytes_for_tenant
    from app.models.anonymization_map import AnonymizationMap
    from app.models.audit_log import AuditLog

    tid = uuid.UUID(tenant_id)
    expires_at = datetime.now(UTC) + timedelta(hours=get_settings().anonymization_retention_hours)

    with get_sync_session() as session:
        set_rls_context(session, tenant_id)
        session.add(
            AnonymizationMap(
                tenant_id=tid,
                project_id=uuid.UUID(project_id),
                analysis_id=(uuid.UUID(analysis_result_id) if analysis_result_id else None),
                encrypted_map=encrypt_bytes_for_tenant(json.dumps(mapping).encode(), tid),
                token_count=token_count,
                secret_count=secret_count,
                expires_at=expires_at,
            )
        )
        # Audit log (Story 1.47): liczby, bez wartości sekretów/nazw.
        from app.schemas.anonymization import AnonymizationStats

        stats = AnonymizationStats(
            anonymized=True,
            token_count=token_count,
            secret_count=secret_count,
            analysis_id=analysis_result_id,
        )
        session.add(
            AuditLog(
                tenant_id=tid,
                action="anonymization_run",
                resource_type="project",
                resource_id=uuid.UUID(project_id),
                details=stats.model_dump(),
            )
        )
        session.commit()


async def _deanonymize_llm_tests(test_cases: list, mapping: dict[str, str]):
    """Detokenize text fields of LLM-generated tests before persistence."""
    from app.services.analysis.anonymization import AnonymizationService

    service = AnonymizationService()
    for tc in test_cases:
        for attr in ("name", "description", "code", "source_function", "source_endpoint"):
            value = getattr(tc, attr, None)
            if isinstance(value, str):
                setattr(tc, attr, await service.deanonymize(value, mapping))
        scenario = getattr(tc, "scenario", None)
        if scenario is not None:
            for attr in ("description", "rationale"):
                value = getattr(scenario, attr, None)
                if isinstance(value, str):
                    setattr(scenario, attr, await service.deanonymize(value, mapping))


def _step_test_generation(ctx: PipelineContext) -> StepResult:
    """Generate test cases from analysis results and persist them in the database."""
    from app.models.test_case import (
        GenerationEngine,
        TestCase,
        TestCaseStatus,
    )
    from app.models.test_case import TestFramework as FrameworkEnum
    from app.models.test_case import (
        TestType as ModelTestType,
    )
    from app.services.generators.native_test_generator import (
        TestFramework as GenFramework,
    )

    analysis_data = ctx.intermediate_results.get("analysis", {})
    analysis_result_id = analysis_data.get("analysis_result_id")
    analysis_dict = analysis_data.get("analysis_dict", {})
    source_file_ids: dict[str, str] = analysis_data.get("source_file_ids", {})
    language = analysis_data.get("language", "python")

    if not analysis_result_id:
        return StepResult(success=False, error="No analysis result ID — analysis step may have failed")

    engine_mode = ctx.engine_mode.lower()
    logger.info("task=%s — test_generation: engine_mode=%s", ctx.task_id, engine_mode)

    # Determine framework: wybór użytkownika z „Parametrów analizy" ma
    # pierwszeństwo (Story 1.56, AC3); bez niego — język + FrameworkDetector
    # (Story 1.55: bez tego PHP wypada jako pytest)
    detected_frameworks = (ctx.intermediate_results.get("preprocessing") or {}).get("frameworks") or []
    framework = _user_selected_framework(ctx.test_framework) or _resolve_test_framework(language, detected_frameworks)

    gen_framework_map = {
        FrameworkEnum.PYTEST: GenFramework.PYTEST,
        FrameworkEnum.JUNIT: GenFramework.JUNIT,
        FrameworkEnum.NUNIT: GenFramework.NUNIT,
        FrameworkEnum.MOCHA: GenFramework.MOCHA,
        FrameworkEnum.JEST: GenFramework.JEST,
        FrameworkEnum.PHPUNIT: GenFramework.PHPUNIT,
        FrameworkEnum.PEST: GenFramework.PEST,
        # Story 1.56 (AC3) — generatory e2e osiągalne z analizy
        FrameworkEnum.SELENIUM: GenFramework.SELENIUM,
        FrameworkEnum.PLAYWRIGHT: GenFramework.PLAYWRIGHT,
        FrameworkEnum.APPIUM: GenFramework.APPIUM,
        # Story 1.57 (AC2/AC3) — natywne frameworki projektu
        FrameworkEnum.UNITTEST: GenFramework.UNITTEST,
        FrameworkEnum.TESTNG: GenFramework.TESTNG,
        FrameworkEnum.MSTEST: GenFramework.MSTEST,
    }
    gen_framework = gen_framework_map.get(framework, GenFramework.PYTEST)

    # ── Native generation (always runs for native & hybrid, fallback for llm) ──
    native_results = None
    if engine_mode in ("native", "hybrid"):
        native_results = _run_native_generation(analysis_dict, language, framework, gen_framework)
        logger.info(
            "task=%s — test_generation: native produced %d + %d pos + %d neg",
            ctx.task_id,
            len(native_results["test_suite"].test_cases),
            len(native_results["positive_scenarios"]),
            len(native_results["negative_scenarios"]),
        )

    # ── LLM generation ──────────────────────────────────────────────────────
    llm_tests: list = []
    llm_tokens = 0
    llm_fallback = False

    if engine_mode in ("llm", "hybrid"):
        available, provider = _llm_available()
        if not available:
            logger.warning("task=%s — LLM unavailable (no API keys), falling back to native", ctx.task_id)
            llm_fallback = True
            if native_results is None:
                native_results = _run_native_generation(analysis_dict, language, framework, gen_framework)
                engine_mode = "native"  # effective mode
        else:
            # Get source files from ast_parsing step cache
            ast_data = ctx.intermediate_results.get("ast_parsing", {})
            loaded_files = ast_data.get("loaded_files", [])
            if loaded_files:
                try:
                    llm_tests, llm_tokens = _run_llm_generation(
                        source_files=loaded_files,
                        language=language,
                        framework=framework,
                        analysis_dict=analysis_dict,
                        provider=provider,
                        # Story 1.54 (FR72): kontekst do persystencji mappingu
                        tenant_id=ctx.tenant_id,
                        project_id=ctx.project_id,
                        analysis_result_id=analysis_result_id,
                    )
                    logger.info(
                        "task=%s — test_generation: LLM produced %d tests (%d tokens)",
                        ctx.task_id,
                        len(llm_tests),
                        llm_tokens,
                    )
                except Exception as exc:
                    logger.error("task=%s — LLM generation failed: %s, falling back to native", ctx.task_id, exc)
                    llm_fallback = True
                    if native_results is None:
                        native_results = _run_native_generation(analysis_dict, language, framework, gen_framework)
                        engine_mode = "native"
            else:
                logger.warning("task=%s — no source files for LLM generation", ctx.task_id)
                llm_fallback = True
                if native_results is None:
                    native_results = _run_native_generation(analysis_dict, language, framework, gen_framework)
                    engine_mode = "native"

    # For engine_mode=llm without fallback, ensure native_results is at least empty
    if native_results is None:
        native_results = {
            "test_suite": type("TS", (), {"test_cases": []})(),
            "positive_scenarios": [],
            "negative_scenarios": [],
        }

    # ── Persist all test cases to DB ──────────────────────────────────────
    test_suite = native_results["test_suite"]
    positive_scenarios = native_results["positive_scenarios"]
    negative_scenarios = native_results["negative_scenarios"]

    logger.info(
        "task=%s — test_generation: saving to DB (%d native, %d positive, %d negative, %d LLM)",
        ctx.task_id,
        len(test_suite.test_cases),
        len(positive_scenarios),
        len(negative_scenarios),
        len(llm_tests),
    )
    saved_count = 0
    try:
        with get_sync_session() as session:
            set_rls_context(session, ctx.tenant_id)

            # Story 7.8 (AC1/AC3): limit ``test_cases`` per plan — nadmiar
            # wygenerowanych przypadków przycinany do pozostałego budżetu
            # (w kolejności: native, positive, negative, LLM).
            from app.models.usage import CounterType
            from app.services.billing.quota_service import increment_usage_sync, remaining_quota_sync

            tenant_uuid = uuid.UUID(ctx.tenant_id)
            remaining = remaining_quota_sync(session, tenant_uuid, CounterType.TEST_CASES)
            native_cases = list(test_suite.test_cases)
            total_generated = len(native_cases) + len(positive_scenarios) + len(negative_scenarios) + len(llm_tests)
            if remaining is not None and total_generated > remaining:
                logger.warning(
                    "task=%s — limit test_cases planu: zapisuję %d z %d wygenerowanych",
                    ctx.task_id,
                    remaining,
                    total_generated,
                )
                budget = remaining
                native_cases = native_cases[:budget]
                budget -= len(native_cases)
                positive_scenarios = positive_scenarios[:budget]
                budget -= len(positive_scenarios)
                negative_scenarios = negative_scenarios[:budget]
                budget -= len(negative_scenarios)
                llm_tests = llm_tests[:budget]

            # Helper to resolve source_file_id from function/endpoint name
            def _resolve_sf_id(file_path: str | None) -> uuid.UUID | None:
                if not file_path:
                    return None
                sf_id = source_file_ids.get(file_path)
                return uuid.UUID(sf_id) if sf_id else None

            # 1) NativeTestGenerator test cases
            for tc in native_cases:
                db_tc = TestCase(
                    tenant_id=uuid.UUID(ctx.tenant_id),
                    analysis_result_id=uuid.UUID(analysis_result_id),
                    source_file_id=_resolve_sf_id(tc.source_file),
                    title=tc.name,
                    description=tc.description,
                    type=ModelTestType.UNIT,
                    framework=framework.value,
                    language=tc.language,
                    generation_engine=GenerationEngine.NATIVE,
                    source_function=tc.source_function,
                    test_code=tc.code,
                    test_data=tc.test_data,
                    status=TestCaseStatus.DRAFT,
                )
                session.add(db_tc)
                saved_count += 1

            # 2) Positive scenarios
            for s in positive_scenarios:
                db_tc = TestCase(
                    tenant_id=uuid.UUID(ctx.tenant_id),
                    analysis_result_id=uuid.UUID(analysis_result_id),
                    source_file_id=_resolve_sf_id(
                        getattr(s, "source_function", None) or getattr(s, "source_endpoint", None)
                    ),
                    title=s.name,
                    description=s.description,
                    type=ModelTestType.POSITIVE,
                    framework=framework.value,
                    language=language,
                    generation_engine=GenerationEngine.NATIVE,
                    source_function=s.source_function,
                    source_endpoint=s.source_endpoint,
                    preconditions={"items": s.preconditions} if s.preconditions else None,
                    steps={"items": s.test_steps} if s.test_steps else None,
                    expected_result=s.expected_result,
                    test_data=s.test_data,
                    status=TestCaseStatus.DRAFT,
                    tags=s.tags if s.tags else None,
                )
                session.add(db_tc)
                saved_count += 1

            # 3) Negative scenarios
            for s in negative_scenarios:
                db_tc = TestCase(
                    tenant_id=uuid.UUID(ctx.tenant_id),
                    analysis_result_id=uuid.UUID(analysis_result_id),
                    source_file_id=_resolve_sf_id(
                        getattr(s, "source_function", None) or getattr(s, "source_endpoint", None)
                    ),
                    title=s.name,
                    description=s.description,
                    type=ModelTestType.NEGATIVE,
                    framework=framework.value,
                    language=language,
                    generation_engine=GenerationEngine.NATIVE,
                    source_function=s.source_function,
                    source_endpoint=s.source_endpoint,
                    preconditions={"items": s.preconditions} if s.preconditions else None,
                    steps={"items": s.test_steps} if s.test_steps else None,
                    expected_result=s.error_message,
                    test_data=s.test_data,
                    status=TestCaseStatus.DRAFT,
                    tags=s.tags if s.tags else None,
                    meta={"scenario_type": s.scenario_type} if hasattr(s, "scenario_type") else None,
                )
                session.add(db_tc)
                saved_count += 1

            # 4) LLM-generated tests
            for llm_tc in llm_tests:
                db_tc = TestCase(
                    tenant_id=uuid.UUID(ctx.tenant_id),
                    analysis_result_id=uuid.UUID(analysis_result_id),
                    source_file_id=_resolve_sf_id(llm_tc.source_file),
                    title=llm_tc.name,
                    description=llm_tc.description,
                    type=ModelTestType.UNIT,
                    framework=framework.value,
                    language=llm_tc.language or language,
                    generation_engine=GenerationEngine.LLM,
                    source_function=llm_tc.source_function,
                    test_code=llm_tc.code,
                    confidence_score=llm_tc.confidence,
                    scenario_description=llm_tc.scenario.description if llm_tc.scenario else None,
                    scenario_rationale=llm_tc.scenario.rationale if llm_tc.scenario else None,
                    test_data=llm_tc.scenario.test_data if llm_tc.scenario else None,
                    status=TestCaseStatus.DRAFT,
                    tags=[llm_tc.test_type] if llm_tc.test_type else None,
                )
                session.add(db_tc)
                saved_count += 1

            # Story 7.8 (AC3): licznik ``test_cases`` po udanym zapisie.
            if saved_count:
                increment_usage_sync(session, tenant_uuid, CounterType.TEST_CASES, saved_count)

            session.commit()
            logger.info(
                "task=%s — test_generation: committed %d test cases to DB (native=%d, pos=%d, neg=%d, llm=%d)",
                ctx.task_id,
                saved_count,
                len(test_suite.test_cases),
                len(positive_scenarios),
                len(negative_scenarios),
                len(llm_tests),
            )
    except Exception as exc:
        logger.error("Failed to save test cases: %s", exc)
        return StepResult(success=False, error=f"Failed to save test cases: {exc}")

    data = {
        "total_test_cases": saved_count,
        "from_native_generator": len(test_suite.test_cases),
        "positive_scenarios": len(positive_scenarios),
        "negative_scenarios": len(negative_scenarios),
        "from_llm_generator": len(llm_tests),
        "total_tokens_used": llm_tokens,
        "engine_mode": engine_mode,
        "llm_fallback_to_native": llm_fallback,
        "framework": framework.value,
        "language": language,
    }
    ctx.intermediate_results["test_generation"] = data
    return StepResult(success=True, data=data)


# ── Step 5: Export — placeholder for future implementation ────────────────────


def _step_export(ctx: PipelineContext) -> StepResult:
    """Export step — placeholder for future export to file/ci integration."""
    return StepResult(success=True, data={"status": "exported", "note": "placeholder"})


# ── Step 5b: Code generation — Story 1.36 ──────────────────────────────────────


def _step_code_generation(ctx: PipelineContext) -> StepResult:
    """Generate test code files from persisted test cases using CodeGenRegistry.

    Story 1.36: Routing framework → PytestCodeGenerator (and future generators).
    Groups test cases by source_file and generates one TestCodeFile per group.
    """
    from app.models.test_case import TestCase as TestCaseModel
    from app.models.test_code import TestCode
    from app.services.test_generation.codegen.base import CodeGenConfig, CodeGenRegistry

    analysis_data = ctx.intermediate_results.get("analysis", {})
    analysis_result_id = analysis_data.get("analysis_result_id")
    if not analysis_result_id:
        return StepResult(success=False, error="No analysis_result_id for code generation")

    language = analysis_data.get("language", "python")
    framework = ctx.intermediate_results.get("test_generation", {}).get("framework", "pytest")

    # Check if generator is available
    registry = CodeGenRegistry.get_instance()
    if not registry.is_supported(framework):
        logger.info("task=%s — code_generation: no generator for framework=%s, skipping", ctx.task_id, framework)
        return StepResult(success=True, data={"status": "skipped", "reason": f"no generator for {framework}"})

    config = CodeGenConfig(
        framework=framework,
        language=language,
        validate_compilation=True,
    )

    saved_count = 0
    error_count = 0

    try:
        with get_sync_session() as session:
            set_rls_context(session, ctx.tenant_id)

            # Load test cases grouped by source_file for batch code generation
            test_cases_q = (
                session.query(TestCaseModel)
                .filter(
                    TestCaseModel.analysis_result_id == uuid.UUID(analysis_result_id),
                    TestCaseModel.tenant_id == uuid.UUID(ctx.tenant_id),
                )
                .all()
            )

            if not test_cases_q:
                return StepResult(success=True, data={"status": "skipped", "reason": "no test cases"})

            # Group by source_file for suite generation (6.3)
            groups: dict[str, list[dict]] = {}
            for tc in test_cases_q:
                sf = tc.source_function or tc.source_class or "unknown"
                groups.setdefault(sf, []).append(tc.to_dict())

            generator = registry.get_generator(framework, config=config)

            for group_key, tc_dicts in groups.items():
                try:
                    result = generator.generate_test_file(tc_dicts, config=config)

                    # Persist one TestCode per test case in the group
                    for tc_dict in tc_dicts:
                        tc_id = tc_dict.get("id")
                        if not tc_id:
                            continue

                        code_record = TestCode(
                            tenant_id=uuid.UUID(ctx.tenant_id),
                            test_case_id=uuid.UUID(tc_id),
                            framework=framework,
                            language=language,
                            code=result.content,
                            file_path=result.file_path,
                        )
                        session.add(code_record)
                        saved_count += 1

                except Exception as exc:
                    logger.error("task=%s — code_generation failed for group %s: %s", ctx.task_id, group_key, exc)
                    error_count += 1

            session.commit()

    except Exception as exc:
        logger.error("task=%s — code_generation DB error: %s", ctx.task_id, exc)
        return StepResult(success=False, error=f"Code generation DB error: {exc}")

    data = {
        "status": "completed",
        "test_codes_saved": saved_count,
        "errors": error_count,
        "framework": framework,
        "language": language,
        "groups_processed": len(groups),
    }
    ctx.intermediate_results["code_generation"] = data
    return StepResult(success=True, data=data)


# ── Step weights ─────────────────────────────────────────────────────────────


DEFAULT_STEPS = [
    PipelineStep(name="preprocessing", func=_step_preprocessing, weight=10),
    PipelineStep(name="ast_parsing", func=_step_ast_parsing, weight=5),
    PipelineStep(name="analysis", func=_step_analysis, weight=30),
    PipelineStep(name="test_generation", func=_step_test_generation, weight=35),
    PipelineStep(name="code_generation", func=_step_code_generation, weight=10),
    PipelineStep(name="export", func=_step_export, weight=10),
]


def _emit_analysis_completed(tenant_id: str, project_id: str, summary: dict[str, Any]) -> None:
    """Webhook ``analysis.completed`` dla systemów klienta (Story 8.7, AC2).

    Emisja jest opcjonalna i cicha: pipeline zakończył pracę, a nieudane
    powiadomienie nie może zmienić jego wyniku ani wywrócić zadania.
    """
    try:
        import asyncio as _asyncio
        import uuid as _uuid

        from app.services.integrations.event_emitter import emit_event_standalone

        _asyncio.run(
            emit_event_standalone(
                "analysis.completed",
                _uuid.UUID(tenant_id),
                {
                    "project_id": project_id,
                    "task_id": summary.get("task_id"),
                    "status": summary.get("status"),
                    "summary": {
                        "steps_completed": summary.get("steps_completed"),
                        "steps_total": summary.get("steps_total"),
                        "test_cases_generated": summary.get("test_cases_generated"),
                    },
                },
            )
        )
    except Exception:
        logger.warning("Nie udało się wyemitować analysis.completed", exc_info=True)


# ── Celery task ──────────────────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    name="analysis.run_pipeline",
    queue="analysis",
    soft_time_limit=300,
    time_limit=330,
    max_retries=2,
    default_retry_delay=60,
)
def run_pipeline(
    self,
    tenant_id: str,
    project_id: str,
    engine_mode: str = "native",
    modules: list[str] | None = None,
    test_framework: str | None = None,
    llm_model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Celery task — orchestrate analysis pipeline steps.

    Each step opens its own DB session with RLS context — we do NOT hold a
    session open for the whole pipeline to avoid exhausting the connection pool.
    """
    logger.info("task=%s tenant=%s — pipeline starting", self.request.id, tenant_id)

    try:
        ctx = PipelineContext(
            task_id=self.request.id,
            tenant_id=tenant_id,
            project_id=project_id,
            engine_mode=engine_mode,
            modules=modules or ["code_analysis"],
            test_framework=test_framework,
            llm_model=llm_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        results = run_pipeline_steps(ctx, DEFAULT_STEPS)

        steps_ok = sum(1 for r in results if r.success)
        summary = {
            "task_id": ctx.task_id,
            "status": "completed" if steps_ok == len(results) else "partial_failure",
            "steps_completed": steps_ok,
            "steps_total": len(results),
            "test_cases_generated": ctx.intermediate_results.get("test_generation", {}).get("total_test_cases", 0),
        }
        _emit_analysis_completed(tenant_id, project_id, summary)
        return summary
    except SoftTimeLimitExceeded:
        progress_svc = TaskProgressService()
        progress_svc.timeout_task(self.request.id)
        logger.warning("task=%s — soft time limit exceeded", self.request.id)
        raise
