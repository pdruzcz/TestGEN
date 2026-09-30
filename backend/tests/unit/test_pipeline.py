"""Tests for pipeline orchestrator — Celery task and step execution (Story 1.10 Task 4)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.workers.pipeline import (
    PipelineContext,
    PipelineStep,
    StepResult,
    run_pipeline_steps,
)


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def project_id():
    return uuid.uuid4()


@pytest.fixture
def task_id():
    return str(uuid.uuid4())


@pytest.fixture
def ctx(tenant_id, project_id, task_id):
    return PipelineContext(
        task_id=task_id,
        tenant_id=str(tenant_id),
        project_id=str(project_id),
        engine_mode="native",
        modules=["code_analysis"],
        intermediate_results={},
    )


class TestPipelineContext:
    def test_context_fields(self, ctx, tenant_id, project_id, task_id):
        assert ctx.task_id == task_id
        assert ctx.tenant_id == str(tenant_id)
        assert ctx.project_id == str(project_id)
        assert ctx.engine_mode == "native"
        assert ctx.modules == ["code_analysis"]
        assert ctx.intermediate_results == {}


class TestStepResult:
    def test_success_result(self):
        result = StepResult(success=True, data={"ast_nodes": 42})
        assert result.success is True
        assert result.data["ast_nodes"] == 42

    def test_failure_result(self):
        result = StepResult(success=False, error="AST parse error")
        assert result.success is False
        assert result.error == "AST parse error"


class TestRunPipelineSteps:
    @patch("app.workers.pipeline.TaskProgressService")
    def test_all_steps_succeed(self, mock_progress_cls, ctx):
        mock_svc = MagicMock()
        mock_progress_cls.return_value = mock_svc

        def success_step(context):
            return StepResult(success=True, data={"done": True})

        steps = [
            PipelineStep(name="preprocessing", func=success_step, weight=20),
            PipelineStep(name="ast_parsing", func=success_step, weight=20),
            PipelineStep(name="analysis", func=success_step, weight=20),
            PipelineStep(name="test_generation", func=success_step, weight=20),
            PipelineStep(name="export", func=success_step, weight=20),
        ]

        results = run_pipeline_steps(ctx, steps)

        assert len(results) == 5
        assert all(r.success for r in results)
        mock_svc.update_progress.assert_called()
        mock_svc.complete_task.assert_called_once()

    @patch("app.workers.pipeline.TaskProgressService")
    def test_step_failure_continues(self, mock_progress_cls, ctx):
        mock_svc = MagicMock()
        mock_progress_cls.return_value = mock_svc

        call_count = 0

        def failing_step(context):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return StepResult(success=False, error="Parse error")
            return StepResult(success=True, data={"ok": True})

        steps = [
            PipelineStep(name="preprocessing", func=failing_step, weight=20),
            PipelineStep(name="ast_parsing", func=failing_step, weight=20),
            PipelineStep(name="analysis", func=failing_step, weight=20),
        ]

        results = run_pipeline_steps(ctx, steps, continue_on_failure=True)

        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True
        mock_svc.partial_failure.assert_called_once()

    @patch("app.workers.pipeline.TaskProgressService")
    def test_step_failure_stops(self, mock_progress_cls, ctx):
        mock_svc = MagicMock()
        mock_progress_cls.return_value = mock_svc

        def fail_step(context):
            return StepResult(success=False, error="Fatal error")

        def success_step(context):
            return StepResult(success=True, data={})

        steps = [
            PipelineStep(name="preprocessing", func=success_step, weight=20),
            PipelineStep(name="ast_parsing", func=fail_step, weight=20),
            PipelineStep(name="analysis", func=success_step, weight=20),
        ]

        results = run_pipeline_steps(ctx, steps, continue_on_failure=False)

        assert len(results) == 2  # stopped after failure
        assert results[1].success is False
        mock_svc.fail_task.assert_called_once()

    @patch("app.workers.pipeline.TaskProgressService")
    def test_progress_updates_per_step(self, mock_progress_cls, ctx):
        mock_svc = MagicMock()
        mock_progress_cls.return_value = mock_svc

        def success_step(context):
            return StepResult(success=True, data={})

        steps = [
            PipelineStep(name="preprocessing", func=success_step, weight=20),
            PipelineStep(name="ast_parsing", func=success_step, weight=30),
        ]

        run_pipeline_steps(ctx, steps)

        progress_calls = mock_svc.update_progress.call_args_list
        assert len(progress_calls) >= 2
        # First step: 20%, Second step: 50%
        first_progress = progress_calls[0][0][1]
        second_progress = progress_calls[1][0][1]
        assert second_progress > first_progress

    @patch("app.workers.pipeline.TaskProgressService")
    def test_intermediate_results_passed_between_steps(self, mock_progress_cls, ctx):
        mock_svc = MagicMock()
        mock_progress_cls.return_value = mock_svc

        def step_one(context):
            context.intermediate_results["key1"] = "value1"
            return StepResult(success=True, data={"step": 1})

        received = {}

        def step_two(context):
            received["key1"] = context.intermediate_results.get("key1")
            return StepResult(success=True, data={"step": 2})

        steps = [
            PipelineStep(name="step_one", func=step_one, weight=50),
            PipelineStep(name="step_two", func=step_two, weight=50),
        ]

        run_pipeline_steps(ctx, steps)

        assert received["key1"] == "value1"


class TestPipelineStepWeight:
    def test_step_has_name_and_weight(self):
        step = PipelineStep(name="test", func=lambda ctx: StepResult(success=True), weight=30)
        assert step.name == "test"
        assert step.weight == 30


class TestPhpFrameworkWiring:
    """Story 1.55 (FR24) — spięcie FrameworkDetector → _step_test_generation.

    §Test 5 (kluczowy): projekt PHP z composer.json (pest/phpunit) → codegen
    używa PHPUnit/PEST, NIE pytest. §Test 6: ścieżka LLM. §Test 7: brak regresji.
    """

    def test_php_with_pest_detected_resolves_pest(self):
        from app.workers.pipeline import _resolve_test_framework

        fw = _resolve_test_framework("php", ["pest"])
        assert fw.value == "pest"

    def test_php_with_phpunit_detected_resolves_phpunit(self):
        from app.workers.pipeline import _resolve_test_framework

        fw = _resolve_test_framework("php", ["phpunit"])
        assert fw.value == "phpunit"

    def test_php_with_both_detected_prefers_pest(self):
        """Pest (DSL nad PHPUnit) ma priorytet, mirror priorytetu _detect_php."""
        from app.workers.pipeline import _resolve_test_framework

        fw = _resolve_test_framework("php", ["phpunit", "pest"])
        assert fw.value == "pest"

    def test_php_without_detection_defaults_to_phpunit_not_pytest(self):
        from app.workers.pipeline import _resolve_test_framework

        fw = _resolve_test_framework("php", [])
        assert fw.value == "phpunit"

    def test_php_detection_ignores_foreign_frameworks(self):
        """Wykrycia innych języków (np. projekt mieszany) nie przejmują sterowania."""
        from app.workers.pipeline import _resolve_test_framework

        fw = _resolve_test_framework("php", ["pytest", "vitest"])
        assert fw.value == "phpunit"

    def test_non_php_language_ignores_php_detection(self):
        """Python z resztkami composer.json → nadal pytest (brak przejęcia)."""
        from app.workers.pipeline import _resolve_test_framework

        fw = _resolve_test_framework("python", ["pest"])
        assert fw.value == "pytest"

    def test_regression_python_resolves_pytest(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("python", ["pytest"]).value == "pytest"

    def test_regression_java_resolves_junit(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("java", ["junit5"]).value == "junit"

    def test_regression_unknown_language_falls_back_to_pytest(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("ruby", []).value == "pytest"


class TestDetectorAutoMapping:
    """Story 1.57 (AC2) — wykryty framework (FrameworkDetector) steruje codegenem.

    „— Automatyczny —" (test_framework=None) + projekt unittest/TestNG/MSTest
    → kod w natywnym frameworku projektu, nie w domyślnym językowym.
    """

    def test_python_with_unittest_detected_resolves_unittest(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("python", ["unittest"]).value == "unittest"

    def test_python_with_nose2_detected_resolves_unittest(self):
        """nose2 uruchamia testy w konwencji unittest — ten sam generator."""
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("python", ["nose2"]).value == "unittest"

    def test_python_with_pytest_detected_stays_pytest(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("python", ["pytest"]).value == "pytest"

    def test_python_without_detection_stays_pytest(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("python", []).value == "pytest"

    def test_java_with_testng_detected_resolves_testng(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("java", ["testng"]).value == "testng"

    def test_java_with_junit5_detected_stays_junit(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("java", ["junit5"]).value == "junit"

    def test_csharp_with_mstest_detected_resolves_mstest(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("c#", ["mstest"]).value == "mstest"

    def test_csharp_with_nunit_detected_stays_nunit(self):
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("c#", ["nunit"]).value == "nunit"

    def test_foreign_detection_does_not_take_over(self):
        """Python z resztkami pom.xml (testng) — detekcja obcego języka nie przejmuje."""
        from app.workers.pipeline import _resolve_test_framework

        assert _resolve_test_framework("python", ["testng"]).value == "pytest"


class TestUserSelectedFramework:
    """Story 1.56 (AC3) — test_framework z AnalysisRequest steruje codegenem.

    Wybór użytkownika („Framework testowy" w parametrach analizy) ma
    pierwszeństwo nad rozpoznaniem z języka; nieznana wartość → fallback
    na rozpoznanie z języka (zachowanie sprzed story).
    """

    def test_selected_e2e_framework_resolves(self):
        from app.workers.pipeline import _user_selected_framework

        for fw in ("selenium", "playwright", "appium"):
            assert _user_selected_framework(fw).value == fw

    def test_selected_framework_resolves_all_model_values(self):
        from app.models.test_case import TestFramework as ModelFramework
        from app.workers.pipeline import _user_selected_framework

        for fw in ModelFramework:
            assert _user_selected_framework(fw.value) == fw

    def test_none_returns_none(self):
        from app.workers.pipeline import _user_selected_framework

        assert _user_selected_framework(None) is None

    def test_invalid_falls_back_to_none(self):
        from app.workers.pipeline import _user_selected_framework

        assert _user_selected_framework("bogus") is None

    def test_selected_framework_maps_to_native_generator(self):
        """GenFramework (native_test_generator) pokrywa wybór e2e użytkownika."""
        from app.services.generators.native_test_generator import TestFramework as GenFramework

        assert GenFramework.SELENIUM.value == "selenium"
        assert GenFramework.PLAYWRIGHT.value == "playwright"
        assert GenFramework.APPIUM.value == "appium"

    def test_selected_framework_maps_to_llm_generator(self):
        """LLMTestFramework pokrywa wybór e2e użytkownika (ścieżka llm/hybrid)."""
        from app.services.generators.llm_test_generator import LLMTestFramework

        assert LLMTestFramework.SELENIUM.value == "selenium"
        assert LLMTestFramework.PLAYWRIGHT.value == "playwright"
        assert LLMTestFramework.APPIUM.value == "appium"


class TestLlmFrameworkMapping:
    """§Test 6 — ścieżka LLM: PHP → LLMTestFramework.PHPUNIT/PEST."""

    def test_phpunit_maps_to_llm_phpunit(self):
        from app.models.test_case import TestFramework
        from app.services.generators.llm_test_generator import LLMTestFramework
        from app.workers.pipeline import _llm_framework_for

        assert _llm_framework_for(TestFramework.PHPUNIT) is LLMTestFramework.PHPUNIT

    def test_pest_maps_to_llm_pest(self):
        from app.models.test_case import TestFramework
        from app.services.generators.llm_test_generator import LLMTestFramework
        from app.workers.pipeline import _llm_framework_for

        assert _llm_framework_for(TestFramework.PEST) is LLMTestFramework.PEST

    def test_regression_junit_maps_to_llm_junit(self):
        """Mapowanie po .name (nie .value) — przed Story 1.55 JUNIT wypadał jako PYTEST."""
        from app.models.test_case import TestFramework
        from app.services.generators.llm_test_generator import LLMTestFramework
        from app.workers.pipeline import _llm_framework_for

        assert _llm_framework_for(TestFramework.JUNIT) is LLMTestFramework.JUNIT
        assert _llm_framework_for(TestFramework.MOCHA) is LLMTestFramework.MOCHA
