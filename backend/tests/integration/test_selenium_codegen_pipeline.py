"""Integration tests for Selenium WebDriver code generation pipeline — Story 1.40.

Testuje pelny przeplyw generowania kodu Selenium z golden data:
- 3+ probki user flows z elementami GUI
- Generowanie -> walidacja skladni -> sprawdzenie elementow
- Metryka: >80% wygenerowanych plikow przechodzi walidacje (native path)
- 3 jezyki: Python, Java, C#
"""

import json
from pathlib import Path

import pytest

from app.services.test_generation.codegen.base import (
    CodeGenConfig,
    CodeGenRegistry,
    TestCodeFile,
)
from app.services.test_generation.codegen.selenium_generator import SeleniumCodeGenerator

# ════════════════════════════════════════════════════════════════════════
# Golden data loader
# ════════════════════════════════════════════════════════════════════════

GOLDEN_DATA_DIR = Path(__file__).resolve().parent.parent / "golden_data" / "code_samples" / "selenium"


def _load_golden_data() -> dict[str, dict]:
    """Zaladuj wszystkie probki golden data."""
    samples: dict[str, dict] = {}
    if not GOLDEN_DATA_DIR.exists():
        return samples

    for path in GOLDEN_DATA_DIR.glob("*.json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            samples[path.stem] = data
    return samples


GOLDEN_DATA = _load_golden_data()


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture(params=list(GOLDEN_DATA.keys()) if GOLDEN_DATA else ["__skip__"])
def golden_sample(request) -> tuple[str, dict]:
    if request.param == "__skip__":
        pytest.skip("Brak golden data")
    return request.param, GOLDEN_DATA[request.param]


@pytest.fixture
def python_generator() -> SeleniumCodeGenerator:
    config = CodeGenConfig(
        framework="selenium",
        language="python",
        validate_compilation=True,
    )
    return SeleniumCodeGenerator(config=config)


@pytest.fixture
def java_generator() -> SeleniumCodeGenerator:
    config = CodeGenConfig(
        framework="selenium",
        language="java",
        validate_compilation=True,
    )
    return SeleniumCodeGenerator(config=config)


@pytest.fixture
def csharp_generator() -> SeleniumCodeGenerator:
    config = CodeGenConfig(
        framework="selenium",
        language="csharp",
        validate_compilation=True,
    )
    return SeleniumCodeGenerator(config=config)


# ════════════════════════════════════════════════════════════════════════
# Testy: Golden data — Python
# ════════════════════════════════════════════════════════════════════════


class TestPythonCodeGenPipeline:
    def test_golden_data_generates_valid_content(
        self, python_generator: SeleniumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = python_generator.generate_test_file(test_cases)
        assert isinstance(result, TestCodeFile)
        assert result.content.strip()
        assert result.framework == "selenium"
        assert result.language == "python"

    def test_golden_data_python_compiles(
        self, python_generator: SeleniumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = python_generator.generate_test_file(test_cases)

        comp = result.compilation_result
        if comp:
            assert comp.success is True, f"Blad skladni Python w {name}: {comp.error_message}"

    def test_golden_data_contains_selenium_elements(
        self, python_generator: SeleniumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = python_generator.generate_test_file(test_cases)
        content = result.content

        # Importy Selenium
        assert "selenium" in content
        assert "By" in content

        # Page Object classes
        assert "class " in content

        # Setup / Teardown
        assert "setup_method" in content
        assert "teardown_method" in content
        assert "driver.quit()" in content

        # ChromeDriver config
        assert "Chrome" in content
        assert "--headless" in content


class TestPythonCompilationRate:
    def test_compilation_rate_above_80_percent(self, python_generator: SeleniumCodeGenerator):
        """Metryka: >80% plikow Python przechodzi walidacje skladniowa."""
        if not GOLDEN_DATA:
            pytest.skip("Brak golden data")

        results: list[bool] = []

        for _name, sample in GOLDEN_DATA.items():
            test_cases = sample.get("test_cases", [])
            result = python_generator.generate_test_file(test_cases)

            if result.compilation_result:
                results.append(result.compilation_result.success)
            else:
                results.append(True)

        success_rate = sum(results) / len(results) * 100 if results else 0
        assert success_rate >= 80, f"Compilation rate Python: {success_rate}% (wymagane >80%)"


# ════════════════════════════════════════════════════════════════════════
# Testy: Golden data — Java
# ════════════════════════════════════════════════════════════════════════


class TestJavaCodeGenPipeline:
    def test_golden_data_generates_java_content(
        self, java_generator: SeleniumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = java_generator.generate_test_file(test_cases)
        assert isinstance(result, TestCodeFile)
        assert result.language == "java"
        assert ".java" in result.file_path

    def test_golden_data_java_has_selenium_imports(
        self, java_generator: SeleniumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = java_generator.generate_test_file(test_cases)
        content = result.content

        assert "org.openqa.selenium" in content
        assert "ChromeDriver" in content or "Chrome" in content

    def test_golden_data_java_has_page_objects(
        self, java_generator: SeleniumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = java_generator.generate_test_file(test_cases)
        content = result.content

        assert "public class" in content
        assert "driver.quit()" in content


# ════════════════════════════════════════════════════════════════════════
# Testy: Golden data — C#
# ════════════════════════════════════════════════════════════════════════


class TestCSharpCodeGenPipeline:
    def test_golden_data_generates_csharp_content(
        self, csharp_generator: SeleniumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = csharp_generator.generate_test_file(test_cases)
        assert isinstance(result, TestCodeFile)
        assert result.language == "csharp"
        assert ".cs" in result.file_path

    def test_golden_data_csharp_has_selenium_imports(
        self, csharp_generator: SeleniumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = csharp_generator.generate_test_file(test_cases)
        content = result.content

        assert "OpenQA.Selenium" in content
        assert "ChromeDriver" in content or "Chrome" in content

    def test_golden_data_csharp_has_page_objects(
        self, csharp_generator: SeleniumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = csharp_generator.generate_test_file(test_cases)
        content = result.content

        assert "public class" in content
        assert "driver.Quit()" in content


# ════════════════════════════════════════════════════════════════════════
# Testy: Pelny przeplyw z rejestru
# ════════════════════════════════════════════════════════════════════════


class TestFullPipelineRegistry:
    def test_registry_to_generation_python(self):
        gen = CodeGenRegistry.get_instance().get_generator(
            "selenium",
            config=CodeGenConfig(
                framework="selenium",
                language="python",
                validate_compilation=False,
            ),
        )
        assert isinstance(gen, SeleniumCodeGenerator)

        tc = {
            "scenario_name": "Registry test",
            "test_type": "e2e",
            "url": "https://example.com",
            "ui_elements": [
                {
                    "name": "btn",
                    "locator_type": "id",
                    "locator_value": "submit",
                    "element_type": "button",
                    "page_name": "MainPage",
                },
            ],
        }
        result = gen.generate_test_file([tc])
        assert "By.ID" in result.content or "By.ID," in result.content
        assert "driver.quit()" in result.content
        assert "--headless" in result.content

    def test_registry_to_generation_java(self):
        gen = CodeGenRegistry.get_instance().get_generator(
            "selenium",
            config=CodeGenConfig(
                framework="selenium",
                language="java",
                validate_compilation=False,
            ),
        )
        tc = {
            "scenario_name": "Registry test",
            "test_type": "e2e",
            "ui_elements": [
                {
                    "name": "btn",
                    "locator_type": "css",
                    "locator_value": ".btn",
                    "element_type": "button",
                    "page_name": "MainPage",
                },
            ],
        }
        result = gen.generate_test_file([tc])
        assert "org.openqa.selenium" in result.content
        assert "By.cssSelector" in result.content
        assert "driver.quit()" in result.content

    def test_registry_to_generation_csharp(self):
        gen = CodeGenRegistry.get_instance().get_generator(
            "selenium",
            config=CodeGenConfig(
                framework="selenium",
                language="csharp",
                validate_compilation=False,
            ),
        )
        tc = {
            "scenario_name": "Registry test",
            "test_type": "e2e",
            "ui_elements": [
                {
                    "name": "btn",
                    "locator_type": "xpath",
                    "locator_value": "//button",
                    "element_type": "button",
                    "page_name": "MainPage",
                },
            ],
        }
        result = gen.generate_test_file([tc])
        assert "OpenQA.Selenium" in result.content
        assert "By.XPath" in result.content
        assert "driver.Quit()" in result.content


# ════════════════════════════════════════════════════════════════════════
# Testy: Cross-language consistencja
# ════════════════════════════════════════════════════════════════════════


class TestCrossLanguageConsistency:
    def test_all_languages_produce_content(self):
        """Wszystkie 3 jezyki generuja niepusty content dla tego samego TC."""
        tc = {
            "scenario_name": "Cross-lang test",
            "test_type": "e2e",
            "url": "https://example.com",
            "ui_elements": [
                {
                    "name": "search",
                    "locator_type": "id",
                    "locator_value": "search",
                    "element_type": "input",
                    "page_name": "SearchPage",
                },
            ],
        }

        for lang in ("python", "java", "csharp"):
            config = CodeGenConfig(
                framework="selenium",
                language=lang,
                validate_compilation=False,
            )
            gen = SeleniumCodeGenerator(config=config)
            result = gen.generate_test_file([tc])
            assert result.content.strip(), f"Pusty output dla jezyka {lang}"
            assert result.language == lang

    def test_all_languages_have_page_objects(self):
        """Wszystkie 3 jezyki generuja Page Object Model."""
        tc = {
            "scenario_name": "POM test",
            "test_type": "e2e",
            "ui_elements": [
                {
                    "name": "login_btn",
                    "locator_type": "css",
                    "locator_value": ".login",
                    "element_type": "button",
                    "page_name": "LoginPage",
                },
            ],
        }

        for lang in ("python", "java", "csharp"):
            config = CodeGenConfig(
                framework="selenium",
                language=lang,
                validate_compilation=False,
            )
            gen = SeleniumCodeGenerator(config=config)
            result = gen.generate_test_file([tc])
            assert "class " in result.content, f"Brak klasy POM w {lang}"

    def test_all_languages_have_driver_quit(self):
        """Wszystkie 3 jezyky generuja cleanup (driver.quit)."""
        tc = {
            "scenario_name": "Cleanup test",
            "test_type": "e2e",
        }

        for lang in ("python", "java", "csharp"):
            config = CodeGenConfig(
                framework="selenium",
                language=lang,
                validate_compilation=False,
            )
            gen = SeleniumCodeGenerator(config=config)
            result = gen.generate_test_file([tc])
            quit_cmd = "driver.quit()" if lang == "java" else ("driver.Quit()" if lang == "csharp" else "driver.quit()")
            assert quit_cmd in result.content, f"Brak {quit_cmd} w {lang}"

    def test_compilation_rate_all_languages(self):
        """Metryka: >80% plikow przechodzi walidacje dla kazdego jezyka."""
        if not GOLDEN_DATA:
            pytest.skip("Brak golden data")

        for lang in ("python", "java", "csharp"):
            config = CodeGenConfig(
                framework="selenium",
                language=lang,
                validate_compilation=True,
            )
            gen = SeleniumCodeGenerator(config=config)

            results: list[bool] = []
            for _name, sample in GOLDEN_DATA.items():
                test_cases = sample.get("test_cases", [])
                result = gen.generate_test_file(test_cases)

                if result.compilation_result:
                    results.append(result.compilation_result.success)
                else:
                    results.append(True)

            if results:
                success_rate = sum(results) / len(results) * 100
                assert success_rate >= 80, f"Compilation rate {lang}: {success_rate}% (wymagane >80%)"


# ════════════════════════════════════════════════════════════════════════
# Testy: Wiele stron POM w jednym test suite
# ════════════════════════════════════════════════════════════════════════


class TestMultiPagePOM:
    def test_multiple_pages_in_single_suite(self):
        """Test suite z elementami na roznych stronach generuje wiele klas POM."""
        tc = {
            "scenario_name": "Multi-page flow",
            "test_type": "e2e",
            "ui_elements": [
                {"name": "search_input", "locator_type": "id", "locator_value": "q", "page_name": "HomePage"},
                {"name": "result_item", "locator_type": "css", "locator_value": ".result", "page_name": "ResultsPage"},
                {
                    "name": "add_to_cart",
                    "locator_type": "css",
                    "locator_value": ".add-cart",
                    "page_name": "ProductPage",
                },
            ],
        }
        config = CodeGenConfig(framework="selenium", language="python", validate_compilation=False)
        gen = SeleniumCodeGenerator(config=config)
        result = gen.generate_test_file([tc])

        assert "HomePage" in result.content
        assert "ResultsPage" in result.content
        assert "ProductPage" in result.content

    def test_multiple_test_cases_shared_pages(self):
        """Wiele testow dzieli strony POM."""
        tcs = [
            {
                "scenario_name": "Test 1",
                "test_type": "e2e",
                "ui_elements": [
                    {"name": "btn1", "locator_type": "id", "locator_value": "b1", "page_name": "CommonPage"},
                ],
            },
            {
                "scenario_name": "Test 2",
                "test_type": "e2e",
                "ui_elements": [
                    {"name": "btn2", "locator_type": "id", "locator_value": "b2", "page_name": "CommonPage"},
                ],
            },
        ]
        config = CodeGenConfig(framework="selenium", language="python", validate_compilation=False)
        gen = SeleniumCodeGenerator(config=config)
        result = gen.generate_test_file(tcs)

        # CommonPage powinna byc tylko raz
        assert result.content.count("class CommonPage") == 1
