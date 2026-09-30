"""Integration tests for Appium mobile code generation pipeline — Story 1.42.

Testuje pelny przeplyw generowania kodu Appium z golden data:
- 3+ probki mobilnych user flows (Android + iOS)
- Generowanie -> walidacja skladni -> sprawdzenie elementow
- Metryka: >80% wygenerowanych plikow przechodzi walidacje (native path)
- Android (UiAutomator2) / iOS (XCUITest)
- Gesty mobilne, context switching, explicit waits
"""

import json
from pathlib import Path

import pytest

from app.services.test_generation.codegen.appium_generator import AppiumCodeGenerator
from app.services.test_generation.codegen.base import (
    CodeGenConfig,
    CodeGenRegistry,
    TestCodeFile,
)

# ════════════════════════════════════════════════════════════════════════
# Golden data loader
# ════════════════════════════════════════════════════════════════════════

GOLDEN_DATA_DIR = Path(__file__).resolve().parent.parent / "golden_data" / "code_samples" / "appium"


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
def android_generator() -> AppiumCodeGenerator:
    config = CodeGenConfig(
        framework="appium",
        language="python",
        validate_compilation=True,
        project_context={"platform": "android"},
    )
    return AppiumCodeGenerator(config=config)


@pytest.fixture
def ios_generator() -> AppiumCodeGenerator:
    config = CodeGenConfig(
        framework="appium",
        language="python",
        validate_compilation=True,
        project_context={"platform": "ios"},
    )
    return AppiumCodeGenerator(config=config)


# ════════════════════════════════════════════════════════════════════════
# Testy: Golden data — Android
# ════════════════════════════════════════════════════════════════════════


class TestAndroidCodeGenPipeline:
    def test_golden_data_generates_valid_content(
        self, android_generator: AppiumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = android_generator.generate_test_file(test_cases)
        assert isinstance(result, TestCodeFile)
        assert result.content.strip()
        assert result.framework == "appium"
        assert result.language == "python"

    def test_golden_data_android_compiles(
        self, android_generator: AppiumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = android_generator.generate_test_file(test_cases)

        comp = result.compilation_result
        if comp:
            assert comp.success is True, f"Blad skladni Python w {name}: {comp.error_message}"

    def test_golden_data_contains_appium_elements(
        self, android_generator: AppiumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = android_generator.generate_test_file(test_cases)
        content = result.content

        # Importy Appium
        assert "from appium import webdriver" in content
        assert "AppiumBy" in content

        # Page Object classes (ekrany)
        assert "class " in content

        # Setup / Teardown
        assert "setup_method" in content
        assert "teardown_method" in content
        assert "driver.quit()" in content

        # Desired capabilities
        assert "desired_caps" in content
        assert "Android" in content
        assert "UiAutomator2" in content


class TestAndroidCompilationRate:
    def test_compilation_rate_above_80_percent(self, android_generator: AppiumCodeGenerator):
        """Metryka: >80% plikow przechodzi walidacje skladniowa."""
        if not GOLDEN_DATA:
            pytest.skip("Brak golden data")

        results: list[bool] = []

        for _name, sample in GOLDEN_DATA.items():
            test_cases = sample.get("test_cases", [])
            result = android_generator.generate_test_file(test_cases)

            if result.compilation_result:
                results.append(result.compilation_result.success)
            else:
                results.append(True)

        success_rate = sum(results) / len(results) * 100 if results else 0
        assert success_rate >= 80, f"Compilation rate Android: {success_rate}% (wymagane >80%)"


# ════════════════════════════════════════════════════════════════════════
# Testy: Golden data — iOS
# ════════════════════════════════════════════════════════════════════════


class TestIOSCodeGenPipeline:
    def test_golden_data_generates_ios_content(
        self, ios_generator: AppiumCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = ios_generator.generate_test_file(test_cases)
        assert isinstance(result, TestCodeFile)
        assert result.language == "python"
        assert "ios" in result.file_path

    def test_golden_data_ios_has_xcuitest(self, ios_generator: AppiumCodeGenerator, golden_sample: tuple[str, dict]):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = ios_generator.generate_test_file(test_cases)
        content = result.content

        assert "iOS" in content
        assert "XCUITest" in content

    def test_golden_data_ios_compiles(self, ios_generator: AppiumCodeGenerator, golden_sample: tuple[str, dict]):
        name, sample = golden_sample
        test_cases = sample.get("test_cases", [])

        result = ios_generator.generate_test_file(test_cases)

        comp = result.compilation_result
        if comp:
            assert comp.success is True, f"Blad skladni iOS w {name}: {comp.error_message}"


# ════════════════════════════════════════════════════════════════════════
# Testy: Pelny przeplyw z rejestru
# ════════════════════════════════════════════════════════════════════════


class TestFullPipelineRegistry:
    def test_registry_to_generation_android(self):
        gen = CodeGenRegistry.get_instance().get_generator(
            "appium",
            config=CodeGenConfig(
                framework="appium",
                language="python",
                validate_compilation=False,
                project_context={"platform": "android"},
            ),
        )
        assert isinstance(gen, AppiumCodeGenerator)

        tc = {
            "scenario_name": "Registry Android test",
            "test_type": "e2e",
            "ui_elements": [
                {
                    "name": "btn",
                    "locator_type": "accessibility_id",
                    "locator_value": "submit",
                    "element_type": "button",
                    "page_name": "MainScreen",
                },
            ],
        }
        result = gen.generate_test_file([tc])
        assert "AppiumBy.ACCESSIBILITY_ID" in result.content
        assert "driver.quit()" in result.content
        assert "UiAutomator2" in result.content

    def test_registry_to_generation_ios(self):
        gen = CodeGenRegistry.get_instance().get_generator(
            "appium",
            config=CodeGenConfig(
                framework="appium",
                language="python",
                validate_compilation=False,
                project_context={"platform": "ios"},
            ),
        )
        tc = {
            "scenario_name": "Registry iOS test",
            "test_type": "e2e",
            "ui_elements": [
                {
                    "name": "btn",
                    "locator_type": "xpath",
                    "locator_value": "//XCUIElementTypeButton[@name='submit']",
                    "element_type": "button",
                    "page_name": "MainScreen",
                },
            ],
        }
        result = gen.generate_test_file([tc])
        assert "AppiumBy.XPATH" in result.content
        assert "driver.quit()" in result.content
        assert "XCUITest" in result.content


# ════════════════════════════════════════════════════════════════════════
# Testy: Platform consistencja
# ════════════════════════════════════════════════════════════════════════


class TestPlatformConsistency:
    def test_both_platforms_produce_content(self):
        """Obie platformy generuja niepusty content."""
        tc = {
            "scenario_name": "Cross-platform test",
            "test_type": "e2e",
            "ui_elements": [
                {
                    "name": "search",
                    "locator_type": "accessibility_id",
                    "locator_value": "search",
                    "element_type": "input",
                    "page_name": "HomeScreen",
                },
            ],
        }

        for platform in ("android", "ios"):
            config = CodeGenConfig(
                framework="appium",
                language="python",
                validate_compilation=False,
                project_context={"platform": platform},
            )
            gen = AppiumCodeGenerator(config=config)
            result = gen.generate_test_file([tc])
            assert result.content.strip(), f"Pusty output dla platformy {platform}"
            assert "driver.quit()" in result.content

    def test_android_has_uiautomator2(self):
        """Android generuje UiAutomator2."""
        config = CodeGenConfig(
            framework="appium",
            language="python",
            validate_compilation=False,
            project_context={"platform": "android"},
        )
        gen = AppiumCodeGenerator(config=config)
        tc = {"scenario_name": "Test", "test_type": "e2e"}
        result = gen.generate_test_file([tc])
        assert "UiAutomator2" in result.content

    def test_ios_has_xcuitest(self):
        """iOS generuje XCUITest."""
        config = CodeGenConfig(
            framework="appium",
            language="python",
            validate_compilation=False,
            project_context={"platform": "ios"},
        )
        gen = AppiumCodeGenerator(config=config)
        tc = {"scenario_name": "Test", "test_type": "e2e"}
        result = gen.generate_test_file([tc])
        assert "XCUITest" in result.content


# ════════════════════════════════════════════════════════════════════════
# Testy: Wiele ekranow POM w jednym test suite
# ════════════════════════════════════════════════════════════════════════


class TestMultiScreenPOM:
    def test_multiple_screens_in_single_suite(self):
        """Test suite z elementami na roznych ekranach generuje wiele klas POM."""
        tc = {
            "scenario_name": "Multi-screen flow",
            "test_type": "e2e",
            "ui_elements": [
                {
                    "name": "search_input",
                    "locator_type": "accessibility_id",
                    "locator_value": "search",
                    "page_name": "HomeScreen",
                },
                {"name": "result_item", "locator_type": "id", "locator_value": "result", "page_name": "ResultsScreen"},
                {
                    "name": "details_btn",
                    "locator_type": "xpath",
                    "locator_value": "//button[@name='details']",
                    "page_name": "DetailsScreen",
                },
            ],
        }
        config = CodeGenConfig(
            framework="appium",
            language="python",
            validate_compilation=False,
            project_context={"platform": "android"},
        )
        gen = AppiumCodeGenerator(config=config)
        result = gen.generate_test_file([tc])

        assert "HomeScreen" in result.content
        assert "ResultsScreen" in result.content
        assert "DetailsScreen" in result.content

    def test_multiple_test_cases_shared_screens(self):
        """Wiele testow dzieli ekrany POM."""
        tcs = [
            {
                "scenario_name": "Test 1",
                "test_type": "e2e",
                "ui_elements": [
                    {
                        "name": "btn1",
                        "locator_type": "accessibility_id",
                        "locator_value": "b1",
                        "page_name": "CommonScreen",
                    },
                ],
            },
            {
                "scenario_name": "Test 2",
                "test_type": "e2e",
                "ui_elements": [
                    {
                        "name": "btn2",
                        "locator_type": "accessibility_id",
                        "locator_value": "b2",
                        "page_name": "CommonScreen",
                    },
                ],
            },
        ]
        config = CodeGenConfig(
            framework="appium",
            language="python",
            validate_compilation=False,
            project_context={"platform": "android"},
        )
        gen = AppiumCodeGenerator(config=config)
        result = gen.generate_test_file(tcs)

        # CommonScreen powinna byc tylko raz
        assert result.content.count("class CommonScreen") == 1


# ════════════════════════════════════════════════════════════════════════
# Testy: Gesty w golden data
# ════════════════════════════════════════════════════════════════════════


class TestGestureIntegration:
    def test_gesture_in_golden_data_search(self, android_generator: AppiumCodeGenerator):
        """Golden data 'search_android' zawiera gest swipe."""
        if "search_android" not in GOLDEN_DATA:
            pytest.skip("Brak golden data search_android")

        sample = GOLDEN_DATA["search_android"]
        test_cases = sample.get("test_cases", [])
        result = android_generator.generate_test_file(test_cases)

        assert "TouchAction" in result.content
        assert "press" in result.content
        assert "move_to" in result.content

    def test_no_time_sleep_in_any_output(self, android_generator: AppiumCodeGenerator):
        """Zaden wygenerowany kod nie zawiera time.sleep."""
        for _name, sample in GOLDEN_DATA.items():
            test_cases = sample.get("test_cases", [])
            result = android_generator.generate_test_file(test_cases)
            assert "time.sleep" not in result.content, f"time.sleep znaleziony w {_name}"
