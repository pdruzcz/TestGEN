"""Integration tests — Playwright codegen pipeline — Story 1.41.

Pelny przeplyw:
- Golden data JSON → PlaywrightCodeGenerator → TestCodeFile → walidacja skladni
- Sprawdzenie >80% wygenerowanych plikow kompiluje sie pomyslnie (native path)
"""

import json
from pathlib import Path

import pytest

from app.services.test_generation.codegen.base import (
    CodeGenConfig,
    CodeGenRegistry,
    TestCodeFile,
)
from app.services.test_generation.codegen.playwright_generator import PlaywrightCodeGenerator

GOLDEN_DATA_DIR = Path(__file__).resolve().parent.parent / "golden_data" / "code_samples" / "playwright"


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def ts_generator() -> PlaywrightCodeGenerator:
    config = CodeGenConfig(
        framework="playwright",
        language="typescript",
        file_extension=".spec.ts",
        validate_compilation=True,
    )
    return PlaywrightCodeGenerator(config=config)


@pytest.fixture
def python_generator() -> PlaywrightCodeGenerator:
    config = CodeGenConfig(
        framework="playwright",
        language="python",
        file_extension=".py",
        validate_compilation=True,
    )
    return PlaywrightCodeGenerator(config=config)


@pytest.fixture
def login_flow_data() -> dict:
    path = GOLDEN_DATA_DIR / "login_flow.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def dashboard_flow_data() -> dict:
    path = GOLDEN_DATA_DIR / "dashboard_flow.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def checkout_flow_data() -> dict:
    path = GOLDEN_DATA_DIR / "checkout_flow.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ════════════════════════════════════════════════════════════════════════
# Integration: Golden data → TypeScript generation
# ════════════════════════════════════════════════════════════════════════


class TestGoldenDataTypescript:
    def test_login_flow_generates_valid_ts(self, ts_generator, login_flow_data):
        result = ts_generator.generate_test_file(login_flow_data["test_cases"])
        assert isinstance(result, TestCodeFile)
        assert result.language == "typescript"
        assert "test.describe" in result.content
        assert "test(" in result.content
        assert "expect(" in result.content
        assert "page.goto" in result.content
        assert "getByPlaceholder" in result.content or "getByRole" in result.content
        assert "on-first-retry" in result.content
        assert result.compilation_result is not None

    def test_dashboard_flow_generates_route_mocks(self, ts_generator, dashboard_flow_data):
        result = ts_generator.generate_test_file(dashboard_flow_data["test_cases"])
        assert "page.route" in result.content
        assert "route.fulfill" in result.content
        assert "**/api/dashboard/stats" in result.content
        assert "200" in result.content

    def test_checkout_flow_warns_about_xpath(self, ts_generator, checkout_flow_data):
        result = ts_generator.generate_test_file(checkout_flow_data["test_cases"])
        assert "locator(" in result.content
        # XPath powinien byc uzyty ale z ostrzezeniem
        if result.compilation_result:
            xpath_warnings = [w for w in result.compilation_result.warnings if "xpath" in w.lower() or "XPath" in w]
            assert len(xpath_warnings) > 0

    def test_checkout_flow_has_post_mock(self, ts_generator, checkout_flow_data):
        result = ts_generator.generate_test_file(checkout_flow_data["test_cases"])
        assert "page.route" in result.content
        assert "201" in result.content
        assert "**/api/orders" in result.content


# ════════════════════════════════════════════════════════════════════════
# Integration: Golden data → Python generation
# ════════════════════════════════════════════════════════════════════════


class TestGoldenDataPython:
    def test_login_flow_generates_valid_py(self, python_generator, login_flow_data):
        result = python_generator.generate_test_file(login_flow_data["test_cases"])
        assert isinstance(result, TestCodeFile)
        assert result.language == "python"
        assert "playwright" in result.content.lower()
        assert "page.goto" in result.content or "page.get_by" in result.content

    def test_dashboard_flow_python_route_mocks(self, python_generator, dashboard_flow_data):
        result = python_generator.generate_test_file(dashboard_flow_data["test_cases"])
        assert "page.route" in result.content


# ════════════════════════════════════════════════════════════════════════
# Integration: Metric >80% compilation success (native)
# ════════════════════════════════════════════════════════════════════════


class TestCompilationMetric:
    def test_over_80_percent_compilation_success(
        self, ts_generator, login_flow_data, dashboard_flow_data, checkout_flow_data
    ):
        """Target: >80% wygenerowanych plikow kompiluje sie pomyslnie (native path)."""
        all_test_cases = []
        for data in [login_flow_data, dashboard_flow_data, checkout_flow_data]:
            all_test_cases.extend(data["test_cases"])

        results = []
        for tc in all_test_cases:
            result = ts_generator.generate_test_file([tc])
            if result.compilation_result:
                results.append(result.compilation_result.success)
            else:
                results.append(False)

        total = len(results)
        passed = sum(1 for r in results if r)
        rate = passed / total if total > 0 else 0

        assert rate >= 0.8, f"Compilation rate: {rate:.0%} ({passed}/{total}), expected >=80%"


# ════════════════════════════════════════════════════════════════════════
# Integration: Registry pipeline
# ════════════════════════════════════════════════════════════════════════


class TestRegistryPipeline:
    def test_registry_pipeline_typescript(self, login_flow_data):
        gen = CodeGenRegistry.get_instance().get_generator(
            "playwright",
            config=CodeGenConfig(framework="playwright", language="typescript", validate_compilation=True),
        )
        result = gen.generate_test_file(login_flow_data["test_cases"])
        assert isinstance(result, TestCodeFile)
        assert result.framework == "playwright"
        assert "test.describe" in result.content

    def test_registry_pipeline_python(self, login_flow_data):
        gen = CodeGenRegistry.get_instance().get_generator(
            "playwright",
            config=CodeGenConfig(framework="playwright", language="python", validate_compilation=True),
        )
        result = gen.generate_test_file(login_flow_data["test_cases"])
        assert isinstance(result, TestCodeFile)
        assert result.framework == "playwright"
        assert result.language == "python"

    def test_all_golden_data_files_exist(self):
        expected = ["login_flow.json", "dashboard_flow.json", "checkout_flow.json"]
        for name in expected:
            path = GOLDEN_DATA_DIR / name
            assert path.exists(), f"Golden data file missing: {name}"
