"""Testy jednostkowe AppiumCodeGenerator — Story 1.42.

AC: 1-11

Pokrycie:
- Task 1: Core generator (generate_test_file, imports, POM, locators, methods)
- Task 2: Desired capabilities (Android/iOS) + driver setup + teardown
- Task 3: Context switching (webview/native)
- Task 4: Gesty mobilne (tap, swipe, scroll, pinch)
- Task 5: Szablony Jinja2 (test_mobile.py.j2, conftest.py.j2)
- Task 6: Walidacja skladni (py_compile)
- Task 7: Rejestracja w CodeGenRegistry
- Task 8: Explicit waits (WebDriverWait + EC)
- Task 9: Edge cases (puste dane, brak elementow, brak gestow, brak webview)
"""

import pytest

from app.services.test_generation.codegen.appium_generator import (
    APPIUM_IMPORTS,
    DESIRED_CAPABILITIES,
    AppiumCodeGenerator,
)
from app.services.test_generation.codegen.base import (
    CodeGenConfig,
    CodeGenRegistry,
    CompilationResult,
    TestCodeFile,
)

# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def android_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="appium",
        language="python",
        file_extension=".py",
        validate_compilation=False,
        project_context={"platform": "android"},
    )


@pytest.fixture
def ios_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="appium",
        language="python",
        file_extension=".py",
        validate_compilation=False,
        project_context={"platform": "ios"},
    )


@pytest.fixture
def generator(android_config: CodeGenConfig) -> AppiumCodeGenerator:
    return AppiumCodeGenerator(config=android_config)


@pytest.fixture
def ios_generator(ios_config: CodeGenConfig) -> AppiumCodeGenerator:
    return AppiumCodeGenerator(config=ios_config)


@pytest.fixture
def login_android_test_case() -> dict:
    """Login flow na Androidzie — podstawowy golden data."""
    return {
        "scenario_name": "User login on Android",
        "test_type": "e2e",
        "ui_elements": [
            {
                "name": "username_field",
                "locator_type": "accessibility_id",
                "locator_value": "username-input",
                "element_type": "input",
                "page_name": "LoginScreen",
            },
            {
                "name": "password_field",
                "locator_type": "accessibility_id",
                "locator_value": "password-input",
                "element_type": "input",
                "page_name": "LoginScreen",
            },
            {
                "name": "login_button",
                "locator_type": "accessibility_id",
                "locator_value": "login-btn",
                "element_type": "button",
                "page_name": "LoginScreen",
            },
        ],
        "user_flow": {
            "name": "Login flow",
            "steps": [
                {"action": "fill", "element": {"name": "username_field"}, "value": "testuser"},
                {"action": "fill", "element": {"name": "password_field"}, "value": "pass123"},
                {"action": "click", "element": {"name": "login_button"}},
            ],
        },
        "expected_result": "Dashboard",
        "comparison_type": "text_contains",
    }


@pytest.fixture
def gesture_test_case() -> dict:
    """Test case z gestami mobilnymi."""
    return {
        "scenario_name": "Swipe to navigate",
        "test_type": "e2e",
        "ui_elements": [
            {
                "name": "carousel",
                "locator_type": "accessibility_id",
                "locator_value": "image-carousel",
                "element_type": "generic",
                "page_name": "HomeScreen",
            },
        ],
        "steps": [
            {
                "action": "swipe",
                "gesture": "swipe",
                "start_x": 500,
                "start_y": 800,
                "end_x": 100,
                "end_y": 800,
                "duration": 300,
            },
        ],
        "expected_result": "next image visible",
    }


@pytest.fixture
def webview_test_case() -> dict:
    """Test case z elementami webview."""
    return {
        "scenario_name": "Hybrid webview login",
        "test_type": "e2e",
        "ui_elements": [
            {
                "name": "web_email",
                "locator_type": "id",
                "locator_value": "email",
                "element_type": "input",
                "page_name": "WebLoginScreen",
            },
        ],
        "webview_elements": [
            {"name": "login_form", "context": "WEBVIEW"},
        ],
        "steps": [
            {"action": "navigate", "value": "https://app.example.com", "context": "webview"},
        ],
    }


# ════════════════════════════════════════════════════════════════════════
# AC 1: Generator registration — AppiumCodeGenerator
# ════════════════════════════════════════════════════════════════════════


class TestGeneratorRegistration:
    def test_registry_has_appium_generator(self):
        assert CodeGenRegistry.get_instance().is_supported("appium")

    def test_registry_get_appium_generator(self):
        gen = CodeGenRegistry.get_instance().get_generator("appium")
        assert isinstance(gen, AppiumCodeGenerator)

    def test_framework_constants(self, generator: AppiumCodeGenerator):
        assert generator.FRAMEWORK == "appium"
        assert generator.LANGUAGE == "python"
        assert generator.FILE_EXTENSION == ".py"


# ════════════════════════════════════════════════════════════════════════
# AC 2: Importy Appium
# ════════════════════════════════════════════════════════════════════════


class TestImports:
    def test_appium_imports_contain_webdriver(self, generator: AppiumCodeGenerator, android_config: CodeGenConfig):
        imports = generator._build_imports([{}], android_config)
        assert any("from appium import webdriver" in imp for imp in imports)

    def test_appium_imports_contain_appium_by(self, generator: AppiumCodeGenerator, android_config: CodeGenConfig):
        imports = generator._build_imports([{}], android_config)
        assert any("AppiumBy" in imp for imp in imports)

    def test_appium_imports_contain_touch_action(self, generator: AppiumCodeGenerator, android_config: CodeGenConfig):
        imports = generator._build_imports([{}], android_config)
        assert any("TouchAction" in imp for imp in imports)

    def test_appium_imports_contain_webdriver_wait(self, generator: AppiumCodeGenerator, android_config: CodeGenConfig):
        imports = generator._build_imports([{}], android_config)
        assert any("WebDriverWait" in imp for imp in imports)

    def test_appium_imports_contain_expected_conditions(
        self, generator: AppiumCodeGenerator, android_config: CodeGenConfig
    ):
        imports = generator._build_imports([{}], android_config)
        assert any("expected_conditions" in imp for imp in imports)

    def test_explicit_imports_from_test_case(self, generator: AppiumCodeGenerator, android_config: CodeGenConfig):
        tc = {"imports": ["import custom_module"]}
        imports = generator._build_imports([tc], android_config)
        assert any("custom_module" in imp for imp in imports)


# ════════════════════════════════════════════════════════════════════════
# AC 3: Lokatory Appium — AppiumBy.ACCESSIBILITY_ID, XPATH, ID
# ════════════════════════════════════════════════════════════════════════


class TestLocators:
    @pytest.mark.parametrize(
        "locator_type,expected_fragment",
        [
            ("accessibility_id", "AppiumBy.ACCESSIBILITY_ID"),
            ("id", "AppiumBy.ID"),
            ("xpath", "AppiumBy.XPATH"),
            ("class_name", "AppiumBy.CLASS_NAME"),
        ],
    )
    def test_appium_locator_syntax(self, generator: AppiumCodeGenerator, locator_type, expected_fragment):
        elem = {
            "name": "test_element",
            "locator_type": locator_type,
            "locator_value": "test-value",
            "element_type": "generic",
            "page_name": "TestScreen",
        }
        locator = generator._generate_locator(elem)
        assert expected_fragment in locator["code"]

    def test_normalize_locator_type_accessibility(self):
        assert AppiumCodeGenerator._normalize_locator_type("accessibility_id") == "accessibility_id"

    def test_normalize_locator_type_accessibility_alias(self):
        assert AppiumCodeGenerator._normalize_locator_type("accessibility") == "accessibility_id"

    def test_normalize_locator_type_content_desc(self):
        assert AppiumCodeGenerator._normalize_locator_type("content_desc") == "accessibility_id"

    def test_normalize_locator_type_resource_id(self):
        assert AppiumCodeGenerator._normalize_locator_type("resource_id") == "id"

    def test_normalize_locator_type_uiautomator(self):
        assert AppiumCodeGenerator._normalize_locator_type("uiautomator") == "uiautomator"

    def test_normalize_locator_type_ios_class_chain(self):
        assert AppiumCodeGenerator._normalize_locator_type("ios_class_chain") == "ios_class_chain"

    def test_unknown_locator_type_defaults_to_accessibility_id(self):
        assert AppiumCodeGenerator._normalize_locator_type("unknown_type") == "accessibility_id"


# ════════════════════════════════════════════════════════════════════════
# AC 4: Gesty mobilne — tap, swipe, scroll, pinch
# ════════════════════════════════════════════════════════════════════════


class TestGestures:
    def test_generate_tap_with_element(self, generator: AppiumCodeGenerator):
        step = {
            "element": {"name": "login_btn", "locator_type": "accessibility_id", "locator_value": "login"},
        }
        code = generator._generate_tap(step)
        assert "element.click()" in code

    def test_generate_tap_with_coordinates(self, generator: AppiumCodeGenerator):
        step = {"x": 200, "y": 400}
        code = generator._generate_tap(step)
        assert "TouchAction" in code
        assert "tap(x=200, y=400)" in code

    def test_generate_swipe_with_coordinates(self, generator: AppiumCodeGenerator):
        step = {"start_x": 500, "start_y": 1500, "end_x": 500, "end_y": 500, "duration": 500}
        code = generator._generate_swipe(step)
        assert "TouchAction" in code
        assert "press(x=500, y=1500)" in code
        assert "move_to(x=500, y=500)" in code
        assert "release()" in code
        assert "perform()" in code

    def test_generate_swipe_with_defaults(self, generator: AppiumCodeGenerator):
        step = {}
        code = generator._generate_swipe(step)
        assert "TouchAction" in code
        assert "press" in code

    def test_generate_scroll_with_target_element(self, generator: AppiumCodeGenerator):
        step = {"scroll_to": "settings-item"}
        code = generator._generate_scroll(step)
        assert "mobile: scroll" in code
        assert "settings-item" in code

    def test_generate_scroll_with_coordinates(self, generator: AppiumCodeGenerator):
        step = {"start_x": 100, "start_y": 1000, "end_x": 100, "end_y": 200}
        code = generator._generate_scroll(step)
        assert "TouchAction" in code

    def test_generate_pinch(self, generator: AppiumCodeGenerator):
        step = {"center_x": 300, "center_y": 400, "offset": 50}
        code = generator._generate_pinch("pinch", step)
        assert "TouchAction" in code
        assert "press(x=300, y=400)" in code

    def test_generate_zoom(self, generator: AppiumCodeGenerator):
        step = {"center_x": 300, "center_y": 400, "offset": 50}
        code = generator._generate_pinch("zoom", step)
        assert "TouchAction" in code
        assert "press(x=300, y=400)" in code

    def test_generate_gesture_unknown_type(self, generator: AppiumCodeGenerator):
        code = generator._generate_gesture("unknown_gesture", {})
        assert "Nieobsługiwany gest" in code

    def test_detect_gestures_positive(self, generator: AppiumCodeGenerator):
        tcs = [{"gestures": ["swipe"]}]
        assert generator._detect_gestures(tcs) is True

    def test_detect_gestures_negative(self, generator: AppiumCodeGenerator):
        tcs = [{"scenario_name": "no gestures"}]
        assert generator._detect_gestures(tcs) is False

    def test_detect_gestures_in_steps(self, generator: AppiumCodeGenerator):
        tcs = [{"steps": [{"gesture": "swipe"}]}]
        assert generator._detect_gestures(tcs) is True


# ════════════════════════════════════════════════════════════════════════
# AC 5: Desired capabilities — Android (UiAutomator2) / iOS (XCUITest)
# ════════════════════════════════════════════════════════════════════════


class TestDesiredCapabilities:
    def test_android_caps_platform_name(self, generator: AppiumCodeGenerator):
        caps = generator._generate_desired_capabilities("android", {})
        assert caps["platformName"] == "Android"

    def test_android_caps_device_name(self, generator: AppiumCodeGenerator):
        caps = generator._generate_desired_capabilities("android", {})
        assert caps["deviceName"] == "emulator-5554"

    def test_android_caps_automation_name(self, generator: AppiumCodeGenerator):
        caps = generator._generate_desired_capabilities("android", {})
        assert caps["automationName"] == "UiAutomator2"

    def test_android_caps_app_path(self, generator: AppiumCodeGenerator):
        caps = generator._generate_desired_capabilities("android", {})
        assert ".apk" in caps["app"]

    def test_ios_caps_platform_name(self, generator: AppiumCodeGenerator):
        caps = generator._generate_desired_capabilities("ios", {})
        assert caps["platformName"] == "iOS"

    def test_ios_caps_device_name(self, generator: AppiumCodeGenerator):
        caps = generator._generate_desired_capabilities("ios", {})
        assert "iPhone" in caps["deviceName"]

    def test_ios_caps_automation_name(self, generator: AppiumCodeGenerator):
        caps = generator._generate_desired_capabilities("ios", {})
        assert caps["automationName"] == "XCUITest"

    def test_ios_caps_app_path(self, generator: AppiumCodeGenerator):
        caps = generator._generate_desired_capabilities("ios", {})
        assert ".ipa" in caps["app"]

    def test_ios_caps_platform_version(self, generator: AppiumCodeGenerator):
        caps = generator._generate_desired_capabilities("ios", {})
        assert "platformVersion" in caps

    def test_caps_override_from_test_case(self, generator: AppiumCodeGenerator):
        tc = {"desired_caps": {"deviceName": "Pixel_7", "app": "/custom/path.apk"}}
        caps = generator._generate_desired_capabilities("android", tc)
        assert caps["deviceName"] == "Pixel_7"
        assert caps["app"] == "/custom/path.apk"

    def test_get_platform_android(self, generator: AppiumCodeGenerator):
        assert generator._get_platform() == "android"

    def test_get_platform_ios(self, ios_generator: AppiumCodeGenerator):
        assert ios_generator._get_platform() == "ios"

    def test_get_platform_default(self):
        config = CodeGenConfig(framework="appium", language="python")
        gen = AppiumCodeGenerator(config=config)
        assert gen._get_platform() == "android"


# ════════════════════════════════════════════════════════════════════════
# AC 6: Driver setup + teardown
# ════════════════════════════════════════════════════════════════════════


class TestDriverSetup:
    def test_driver_setup_android(self, generator: AppiumCodeGenerator):
        caps = DESIRED_CAPABILITIES["android"]
        setup = generator._generate_driver_setup("android", caps)
        assert setup["platform"] == "android"
        assert setup["hub_url"] == "http://localhost:4723/wd/hub"
        assert any("platformName" in line for line in setup["caps_lines"])
        assert any("UiAutomator2" in line for line in setup["caps_lines"])

    def test_driver_setup_ios(self, generator: AppiumCodeGenerator):
        caps = DESIRED_CAPABILITIES["ios"]
        setup = generator._generate_driver_setup("ios", caps)
        assert setup["platform"] == "ios"
        assert any("XCUITest" in line for line in setup["caps_lines"])

    def test_setup_method_in_android_output(self, generator: AppiumCodeGenerator, login_android_test_case: dict):
        result = generator.generate_test_file([login_android_test_case])
        assert "setup_method" in result.content
        assert "webdriver.Remote" in result.content
        assert "desired_caps" in result.content

    def test_teardown_method_in_android_output(self, generator: AppiumCodeGenerator, login_android_test_case: dict):
        result = generator.generate_test_file([login_android_test_case])
        assert "teardown_method" in result.content
        assert "driver.quit()" in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 7: Context switching (webview/native)
# ════════════════════════════════════════════════════════════════════════


class TestContextSwitching:
    def test_detect_webview_positive(self, generator: AppiumCodeGenerator):
        tcs = [{"webview_elements": [{"name": "form"}]}]
        assert generator._detect_webview(tcs) is True

    def test_detect_webview_from_steps(self, generator: AppiumCodeGenerator):
        tcs = [{"steps": [{"context": "webview"}]}]
        assert generator._detect_webview(tcs) is True

    def test_detect_webview_negative(self, generator: AppiumCodeGenerator):
        tcs = [{"scenario_name": "native only"}]
        assert generator._detect_webview(tcs) is False

    def test_context_switch_webview_code(self, generator: AppiumCodeGenerator):
        code = generator._generate_context_switch_code("webview")
        assert "driver.contexts" in code
        assert "WEBVIEW" in code
        assert "switch_to.context" in code

    def test_context_switch_native_code(self, generator: AppiumCodeGenerator):
        code = generator._generate_context_switch_code("native")
        assert "NATIVE_APP" in code
        assert "switch_to.context" in code

    def test_webview_helpers_in_output(self, generator: AppiumCodeGenerator, webview_test_case: dict):
        result = generator.generate_test_file([webview_test_case])
        assert "_switch_to_webview" in result.content
        assert "_switch_to_native" in result.content

    def test_no_webview_helpers_when_native_only(self, generator: AppiumCodeGenerator, login_android_test_case: dict):
        result = generator.generate_test_file([login_android_test_case])
        assert "_switch_to_webview" not in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 8: Explicit waits — WebDriverWait + expected_conditions (no time.sleep)
# ════════════════════════════════════════════════════════════════════════


class TestExplicitWaits:
    def test_wait_code_presence(self, generator: AppiumCodeGenerator):
        code = generator._render_explicit_wait_code("submit_btn", "presence")
        assert "EC.presence_of_element_located" in code

    def test_wait_code_clickable(self, generator: AppiumCodeGenerator):
        code = generator._render_explicit_wait_code("submit_btn", "clickable")
        assert "EC.element_to_be_clickable" in code

    def test_wait_code_visible(self, generator: AppiumCodeGenerator):
        code = generator._render_explicit_wait_code("submit_btn", "visible")
        assert "EC.visibility_of_element_located" in code

    def test_no_time_sleep_in_output(self, generator: AppiumCodeGenerator, login_android_test_case: dict):
        result = generator.generate_test_file([login_android_test_case])
        assert "time.sleep" not in result.content

    def test_explicit_waits_from_test_case(self, generator: AppiumCodeGenerator):
        tc = {
            "scenario_name": "Wait test",
            "test_type": "e2e",
            "explicit_waits": [
                {"element": "loading_spinner", "condition": "visible", "timeout": 5},
            ],
            "ui_elements": [
                {
                    "name": "loading_spinner",
                    "locator_type": "accessibility_id",
                    "locator_value": "spinner",
                    "page_name": "MainScreen",
                },
            ],
        }
        result = generator.generate_test_file([tc])
        assert "EC." in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 9: Walidacja skladni (py_compile)
# ════════════════════════════════════════════════════════════════════════


class TestValidateSyntax:
    def test_valid_python_code_passes(self, generator: AppiumCodeGenerator):
        code = """
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class TestLogin:
    def setup_method(self):
        desired_caps = {"platformName": "Android"}
        self.driver = webdriver.Remote("http://localhost:4723/wd/hub", desired_caps)

    def teardown_method(self):
        self.driver.quit()

    def test_login(self):
        assert True
"""
        result = generator.validate_syntax(code)
        assert result.success is True

    def test_invalid_python_code_fails(self, generator: AppiumCodeGenerator):
        code = "def broken(\n"
        result = generator.validate_syntax(code)
        assert result.success is False

    def test_empty_code_fails(self, generator: AppiumCodeGenerator):
        result = generator.validate_syntax("")
        assert result.success is False
        assert "Pusty" in result.error_message

    def test_warnings_for_missing_appium_markers(self, generator: AppiumCodeGenerator):
        code = "x = 1\nprint(x)\n"
        result = generator.validate_syntax(code)
        assert any("appium" in w.lower() for w in result.warnings)

    def test_appium_markers_detected(self, generator: AppiumCodeGenerator):
        code = """
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
desired_caps = {"platformName": "Android"}
driver.quit()
"""
        result = generator.validate_syntax(code)
        assert result.success is True
        # Brak warningow — wszystkie markery obecne
        assert not any("Appium" in w for w in result.warnings)


# ════════════════════════════════════════════════════════════════════════
# AC 10: Asserty
# ════════════════════════════════════════════════════════════════════════


class TestAssertions:
    def test_assert_element_visible(self, generator: AppiumCodeGenerator):
        result = generator.generate_assertion("login_btn", 'AppiumBy.ACCESSIBILITY_ID, "login"', "element_visible")
        assert "visibility_of_element_located" in result

    def test_assert_text_equals(self, generator: AppiumCodeGenerator):
        result = generator.generate_assertion("Welcome", "header.text", "text_equals")
        assert "assert" in result.lower()
        assert "Welcome" in result

    def test_assert_text_contains(self, generator: AppiumCodeGenerator):
        result = generator.generate_assertion("Dashboard", "page.text", "text_contains")
        assert "Dashboard" in result

    def test_assert_element_present(self, generator: AppiumCodeGenerator):
        result = generator.generate_assertion("btn", 'AppiumBy.ID, "btn"', "element_present")
        assert "presence_of_element_located" in result

    def test_assert_element_enabled(self, generator: AppiumCodeGenerator):
        result = generator.generate_assertion("submit", "btn_element", "element_enabled")
        assert "is_enabled" in result

    def test_assert_element_selected(self, generator: AppiumCodeGenerator):
        result = generator.generate_assertion("checkbox", "cb_element", "element_selected")
        assert "is_selected" in result

    def test_assert_fallback_equals(self, generator: AppiumCodeGenerator):
        result = generator.generate_assertion("expected_val", "actual_val", "unknown_type")
        assert "assert" in result

    def test_assert_with_message(self, generator: AppiumCodeGenerator):
        result = generator.generate_assertion("val", "actual", "unknown_type", message="Custom error")
        assert "Custom error" in result


# ════════════════════════════════════════════════════════════════════════
# AC 11: Szablony Jinja2
# ════════════════════════════════════════════════════════════════════════


class TestTemplates:
    def test_template_renders_test_class(self, generator: AppiumCodeGenerator, login_android_test_case: dict):
        result = generator.generate_test_file([login_android_test_case])
        assert "class " in result.content
        assert "def " in result.content

    def test_template_includes_desired_caps(self, generator: AppiumCodeGenerator, login_android_test_case: dict):
        result = generator.generate_test_file([login_android_test_case])
        assert "desired_caps" in result.content
        assert "Android" in result.content

    def test_template_includes_driver_remote(self, generator: AppiumCodeGenerator, login_android_test_case: dict):
        result = generator.generate_test_file([login_android_test_case])
        assert "webdriver.Remote" in result.content

    def test_conftest_renders(self, generator: AppiumCodeGenerator):
        conftest = generator.generate_setup({"platform": "android"})
        assert "import pytest" in conftest
        assert "from appium import webdriver" in conftest
        assert "pytest_addoption" in conftest
        assert "driver" in conftest

    def test_conftest_android(self, generator: AppiumCodeGenerator):
        conftest = generator.generate_setup({"platform": "android"})
        assert "UiAutomator2" in conftest

    def test_conftest_ios(self, ios_generator: AppiumCodeGenerator):
        conftest = ios_generator.generate_setup({"platform": "ios"})
        assert "XCUITest" in conftest


# ════════════════════════════════════════════════════════════════════════
# Pełny przepływ — golden data
# ════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    def test_full_login_flow_android(self, generator: AppiumCodeGenerator, login_android_test_case: dict):
        result = generator.generate_test_file([login_android_test_case])
        assert isinstance(result, TestCodeFile)
        assert result.content.strip()
        assert result.framework == "appium"
        assert result.language == "python"
        assert "LoginScreen" in result.content
        assert "setup_method" in result.content
        assert "teardown_method" in result.content
        assert "driver.quit()" in result.content

    def test_full_flow_ios(self, ios_generator: AppiumCodeGenerator):
        tc = {
            "scenario_name": "iOS login",
            "test_type": "e2e",
            "ui_elements": [
                {
                    "name": "email_field",
                    "locator_type": "accessibility_id",
                    "locator_value": "email",
                    "element_type": "input",
                    "page_name": "LoginScreen",
                },
            ],
        }
        result = ios_generator.generate_test_file([tc])
        assert "iOS" in result.content
        assert "XCUITest" in result.content
        assert "driver.quit()" in result.content

    def test_full_flow_with_gestures(self, generator: AppiumCodeGenerator, gesture_test_case: dict):
        result = generator.generate_test_file([gesture_test_case])
        assert isinstance(result, TestCodeFile)
        assert "TouchAction" in result.content

    def test_file_path_structure_android(self, generator: AppiumCodeGenerator, login_android_test_case: dict):
        result = generator.generate_test_file([login_android_test_case])
        assert "tests/mobile/" in result.file_path
        assert "android" in result.file_path
        assert ".py" in result.file_path

    def test_file_path_structure_ios(self, ios_generator: AppiumCodeGenerator):
        tc = {
            "scenario_name": "iOS test",
            "test_type": "e2e",
            "ui_elements": [
                {"name": "btn", "locator_type": "accessibility_id", "locator_value": "btn", "page_name": "MainScreen"},
            ],
        }
        result = ios_generator.generate_test_file([tc])
        assert "ios" in result.file_path

    def test_compilation_result_included_when_enabled(
        self, generator: AppiumCodeGenerator, login_android_test_case: dict
    ):
        config = CodeGenConfig(
            framework="appium", language="python", validate_compilation=True, project_context={"platform": "android"}
        )
        gen = AppiumCodeGenerator(config=config)
        result = gen.generate_test_file([login_android_test_case])
        assert result.compilation_result is not None
        assert isinstance(result.compilation_result, CompilationResult)

    def test_registry_full_pipeline(self):
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
            "scenario_name": "Registry test",
            "test_type": "e2e",
            "ui_elements": [
                {
                    "name": "btn",
                    "locator_type": "accessibility_id",
                    "locator_value": "submit",
                    "page_name": "TestScreen",
                }
            ],
        }
        result = gen.generate_test_file([tc])
        assert "AppiumBy.ACCESSIBILITY_ID" in result.content
        assert "driver.quit()" in result.content


# ════════════════════════════════════════════════════════════════════════
# Edge cases
# ════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_test_case_list(self, generator: AppiumCodeGenerator):
        result = generator.generate_test_file([])
        assert "Brak test case" in result.content

    def test_no_ui_elements_generates_empty_pom(self, generator: AppiumCodeGenerator):
        tc = {
            "scenario_name": "No elements test",
            "test_type": "e2e",
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)
        assert "class " in result.content

    def test_empty_locator_value(self, generator: AppiumCodeGenerator):
        tc = {
            "scenario_name": "Empty locator",
            "test_type": "e2e",
            "ui_elements": [
                {"name": "elem", "locator_type": "accessibility_id", "locator_value": "", "page_name": "TestScreen"},
            ],
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)

    def test_very_long_scenario_name(self, generator: AppiumCodeGenerator):
        tc = {
            "scenario_name": "A" * 200,
            "test_type": "e2e",
            "ui_elements": [
                {"name": "btn", "locator_type": "accessibility_id", "locator_value": "btn", "page_name": "TestScreen"}
            ],
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)

    def test_none_fields_in_test_case(self, generator: AppiumCodeGenerator):
        tc = {
            "scenario_name": None,
            "test_type": None,
            "ui_elements": None,
            "user_flow": None,
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)
        assert "class " in result.content

    def test_user_flow_without_element_refs(self, generator: AppiumCodeGenerator):
        tc = {
            "scenario_name": "Flow without elements",
            "test_type": "e2e",
            "user_flow": {
                "name": "Simple flow",
                "steps": [
                    {"action": "navigate", "value": "https://example.com"},
                ],
            },
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)

    def test_setup_returns_string(self, generator: AppiumCodeGenerator):
        result = generator.generate_setup()
        assert isinstance(result, str)

    def test_no_gestures_no_webview(self, generator: AppiumCodeGenerator):
        """Brak gestow i webview — czysty native test."""
        tc = {
            "scenario_name": "Simple native test",
            "test_type": "e2e",
            "ui_elements": [
                {"name": "btn", "locator_type": "id", "locator_value": "my-btn", "page_name": "HomeScreen"},
            ],
        }
        result = generator.generate_test_file([tc])
        assert "_switch_to_webview" not in result.content
        assert isinstance(result, TestCodeFile)

    def test_unsupported_platform_defaults_to_android(self):
        config = CodeGenConfig(framework="appium", language="python", project_context={"platform": "windows"})
        gen = AppiumCodeGenerator(config=config)
        assert gen._get_platform() == "android"


# ════════════════════════════════════════════════════════════════════════
# Metody pomocnicze
# ════════════════════════════════════════════════════════════════════════


class TestHelperMethods:
    def test_make_class_name(self):
        assert AppiumCodeGenerator._make_class_name("login_screen") == "LoginScreen"
        assert AppiumCodeGenerator._make_class_name("user-profile") == "UserProfile"
        assert AppiumCodeGenerator._make_class_name("Calculator") == "Calculator"
        assert AppiumCodeGenerator._make_class_name("") == "Unnamed"

    def test_normalize_element_name(self):
        assert AppiumCodeGenerator._normalize_element_name("Submit Button") == "submit_button"
        assert AppiumCodeGenerator._normalize_element_name("username-input") == "username_input"
        assert AppiumCodeGenerator._normalize_element_name("") == "element"

    def test_normalize_test_method_name(self):
        result = AppiumCodeGenerator._normalize_test_method_name("User login flow")
        assert result.startswith("test_")
        assert "user" in result

    def test_normalize_test_method_name_max_length(self):
        result = AppiumCodeGenerator._normalize_test_method_name("A" * 200)
        assert len(result) <= 60

    def test_extract_module_name(self):
        assert AppiumCodeGenerator._extract_module_name({"scenario_name": "Login test"}) == "Login_test"
        assert AppiumCodeGenerator._extract_module_name({"scenario_name": None}) == "unnamed"

    def test_build_file_path_android(self):
        result = AppiumCodeGenerator._build_file_path("LoginTest", "android")
        assert result == "tests/mobile/android/LoginTest.py"

    def test_build_file_path_ios(self):
        result = AppiumCodeGenerator._build_file_path("LoginTest", "ios")
        assert result == "tests/mobile/ios/LoginTest.py"

    def test_fallback_render(self, generator: AppiumCodeGenerator):
        context = {
            "module_name": "TestModule",
            "imports": APPIUM_IMPORTS,
            "page_objects": [],
            "test_class_name": "TestMobile",
            "driver_setup": {
                "caps_lines": ['desired_caps = {"platformName": "Android"}'],
                "hub_url": "http://localhost:4723/wd/hub",
            },
            "test_methods": [
                {
                    "name": "test_example",
                    "url": "",
                    "steps": [],
                    "assertions": [],
                    "waits": [],
                    "scenario": "example",
                }
            ],
            "platform": "android",
            "has_webview": False,
        }
        result = generator._fallback_render(context)
        assert "class TestMobile" in result
        assert "driver.quit()" in result

    def test_fallback_render_conftest(self, generator: AppiumCodeGenerator):
        caps = DESIRED_CAPABILITIES["android"]
        result = generator._fallback_render_conftest("android", caps)
        assert "import pytest" in result
        assert "from appium import webdriver" in result
        assert "UiAutomator2" in result

    def test_parse_compile_error(self):
        msg = 'File "test.py", line 42'
        line, col = AppiumCodeGenerator._parse_compile_error(msg)
        assert line == 42
        assert col is None

    def test_parse_compile_error_with_column(self):
        msg = 'File "test.py", line 10, column 5'
        line, col = AppiumCodeGenerator._parse_compile_error(msg)
        assert line == 10
        assert col == 5
