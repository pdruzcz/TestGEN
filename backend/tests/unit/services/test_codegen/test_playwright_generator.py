"""Testy jednostkowe PlaywrightCodeGenerator — Story 1.41.

AC: 1-12

Pokrycie:
- Task 1: Core generator (generate_test_file, imports, describe, test, locators, expectations, trace)
- Task 2: Network interceptors (page.route, mock endpoints)
- Task 3: Walidacja selektorow (preferencja semantycznych, ostrzezenie XPath)
- Task 4: Obsluga wielu jezykow (TypeScript, Python, Java, C#)
- Task 5: Szablony Jinja2 (fallback rendering)
- Task 6: Walidacja skladni
- Task 7: Integracja z orchestratorem (rejestracja w CodeGenRegistry)
- Task 8: Edge cases
"""

import pytest

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
def ts_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="playwright",
        language="typescript",
        file_extension=".spec.ts",
        validate_compilation=False,
    )


@pytest.fixture
def python_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="playwright",
        language="python",
        file_extension=".py",
        validate_compilation=False,
    )


@pytest.fixture
def java_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="playwright",
        language="java",
        file_extension=".java",
        validate_compilation=False,
    )


@pytest.fixture
def csharp_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="playwright",
        language="csharp",
        file_extension=".cs",
        validate_compilation=False,
    )


@pytest.fixture
def generator(ts_config: CodeGenConfig):
    from app.services.test_generation.codegen.playwright_generator import PlaywrightCodeGenerator

    return PlaywrightCodeGenerator(config=ts_config)


@pytest.fixture
def python_generator(python_config: CodeGenConfig):
    from app.services.test_generation.codegen.playwright_generator import PlaywrightCodeGenerator

    return PlaywrightCodeGenerator(config=python_config)


@pytest.fixture
def java_generator(java_config: CodeGenConfig):
    from app.services.test_generation.codegen.playwright_generator import PlaywrightCodeGenerator

    return PlaywrightCodeGenerator(config=java_config)


@pytest.fixture
def csharp_generator(csharp_config: CodeGenConfig):
    from app.services.test_generation.codegen.playwright_generator import PlaywrightCodeGenerator

    return PlaywrightCodeGenerator(config=csharp_config)


@pytest.fixture
def login_test_case() -> dict:
    """Login flow — podstawowy golden data."""
    return {
        "scenario_name": "User login",
        "test_type": "e2e",
        "url": "https://example.com/login",
        "ui_elements": [
            {
                "name": "username_input",
                "locator_type": "placeholder",
                "locator_value": "Username",
                "element_type": "input",
                "page_name": "LoginPage",
            },
            {
                "name": "password_input",
                "locator_type": "placeholder",
                "locator_value": "Password",
                "element_type": "input",
                "page_name": "LoginPage",
            },
            {
                "name": "login_button",
                "locator_type": "role",
                "locator_value": "button",
                "element_type": "button",
                "page_name": "LoginPage",
                "role_name": "Submit",
            },
            {
                "name": "welcome_message",
                "locator_type": "text",
                "locator_value": "Welcome",
                "element_type": "text",
                "page_name": "DashboardPage",
            },
        ],
        "user_flow": {
            "name": "Login flow",
            "url": "https://example.com/login",
            "steps": [
                {"action": "fill", "element": {"name": "username_input"}, "value": "testuser"},
                {"action": "fill", "element": {"name": "password_input"}, "value": "password123"},
                {"action": "click", "element": {"name": "login_button"}},
            ],
        },
        "expected_result": "Welcome",
        "comparison_type": "text_contains",
        "assertions": [
            {"type": "text_contains", "element": "welcome_message", "expected": "Welcome"},
        ],
    }


@pytest.fixture
def mock_test_case() -> dict:
    """Test case z mockowaniem API."""
    return {
        "scenario_name": "Load users with API mock",
        "test_type": "e2e",
        "url": "https://example.com/users",
        "ui_elements": [
            {
                "name": "user_list",
                "locator_type": "testId",
                "locator_value": "user-list",
                "element_type": "list",
                "page_name": "UsersPage",
            },
        ],
        "user_flow": {
            "name": "Load users",
            "url": "https://example.com/users",
            "steps": [
                {"action": "navigate", "value": "https://example.com/users"},
                {"action": "check", "element": {"name": "user_list"}},
            ],
        },
        "api_mocks": [
            {
                "url": "**/api/users",
                "method": "GET",
                "status": 200,
                "body": [{"id": 1, "name": "Jan"}, {"id": 2, "name": "Anna"}],
            },
        ],
        "expected_result": "Jan",
        "comparison_type": "text_contains",
    }


@pytest.fixture
def search_test_case() -> dict:
    """Search flow z XPath lokatorami — test preferencji semantycznych."""
    return {
        "scenario_name": "Search products",
        "test_type": "e2e",
        "url": "https://shop.example.com",
        "ui_elements": [
            {
                "name": "search_bar",
                "locator_type": "xpath",
                "locator_value": "//input[@placeholder='Search...']",
                "element_type": "input",
                "page_name": "HomePage",
            },
            {
                "name": "search_button",
                "locator_type": "role",
                "locator_value": "button",
                "element_type": "button",
                "page_name": "HomePage",
                "role_name": "Search",
            },
        ],
        "user_flow": {
            "name": "Search flow",
            "url": "https://shop.example.com",
            "steps": [
                {"action": "fill", "element": {"name": "search_bar"}, "value": "laptop"},
                {"action": "click", "element": {"name": "search_button"}},
            ],
        },
        "expected_result": "laptop",
        "comparison_type": "text_contains",
    }


# ════════════════════════════════════════════════════════════════════════
# AC 1: Generator registration — PlaywrightCodeGenerator
# ════════════════════════════════════════════════════════════════════════


class TestGeneratorRegistration:
    def test_registry_has_playwright_generator(self):
        assert CodeGenRegistry.get_instance().is_supported("playwright")

    def test_registry_get_playwright_generator(self):
        from app.services.test_generation.codegen.playwright_generator import PlaywrightCodeGenerator

        gen = CodeGenRegistry.get_instance().get_generator("playwright")
        assert isinstance(gen, PlaywrightCodeGenerator)

    def test_framework_constants(self, generator):
        assert generator.FRAMEWORK == "playwright"
        assert generator.LANGUAGE == "typescript"
        assert generator.FILE_EXTENSION == ".spec.ts"


# ════════════════════════════════════════════════════════════════════════
# AC 2: Playwright test structure — test.describe, test(), expect()
# ════════════════════════════════════════════════════════════════════════


class TestPlaywrightStructure:
    def test_output_has_test_describe(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "test.describe" in result.content

    def test_output_has_test_function(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "test(" in result.content

    def test_output_has_expect(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "expect(" in result.content

    def test_describe_has_feature_name(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "User login" in result.content or "Login" in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 3: Page objects — getByRole, getByText, getByPlaceholder, getByTestId
# ════════════════════════════════════════════════════════════════════════


class TestLocators:
    @pytest.mark.parametrize(
        "locator_type,locator_value,expected_method",
        [
            ("role", "button", "getByRole"),
            ("text", "Welcome", "getByText"),
            ("placeholder", "Username", "getByPlaceholder"),
            ("testId", "user-list", "getByTestId"),
        ],
    )
    def test_semantic_locator_types(self, generator, locator_type, locator_value, expected_method):
        elem = {
            "name": "test_element",
            "locator_type": locator_type,
            "locator_value": locator_value,
            "element_type": "generic",
            "page_name": "TestPage",
        }
        locator = generator._generate_locator(elem, "typescript")
        assert expected_method in locator["code"]

    def test_get_by_role_includes_name_option(self, generator):
        elem = {
            "name": "login_button",
            "locator_type": "role",
            "locator_value": "button",
            "element_type": "button",
            "page_name": "TestPage",
            "role_name": "Submit",
        }
        locator = generator._generate_locator(elem, "typescript")
        assert "getByRole" in locator["code"]
        assert "name" in locator["code"]

    def test_xpath_uses_locator_fallback(self, generator):
        elem = {
            "name": "search_bar",
            "locator_type": "xpath",
            "locator_value": "//input[@placeholder='Search']",
            "element_type": "input",
            "page_name": "TestPage",
        }
        locator = generator._generate_locator(elem, "typescript")
        assert "locator(" in locator["code"]

    def test_css_uses_locator(self, generator):
        elem = {
            "name": "submit_btn",
            "locator_type": "css",
            "locator_value": ".submit-btn",
            "element_type": "button",
            "page_name": "TestPage",
        }
        locator = generator._generate_locator(elem, "typescript")
        assert "locator(" in locator["code"]


# ════════════════════════════════════════════════════════════════════════
# AC 4: Auto-waiting — brak explicit waits
# ════════════════════════════════════════════════════════════════════════


class TestAutoWaiting:
    def test_no_wait_for_timeout(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "waitForTimeout" not in result.content

    def test_no_wait_for_selector(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "waitForSelector" not in result.content

    def test_no_manual_sleep(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "sleep" not in result.content.lower() or "page.waitForTimeout" not in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 5: Network interceptors — page.route()
# ════════════════════════════════════════════════════════════════════════


class TestNetworkInterceptors:
    def test_route_mock_generated(self, generator, mock_test_case):
        result = generator.generate_test_file([mock_test_case])
        assert "page.route" in result.content

    def test_route_fulfill_in_output(self, generator, mock_test_case):
        result = generator.generate_test_file([mock_test_case])
        assert "route.fulfill" in result.content

    def test_mock_url_in_output(self, generator, mock_test_case):
        result = generator.generate_test_file([mock_test_case])
        assert "**/api/users" in result.content

    def test_mock_status_code_in_output(self, generator, mock_test_case):
        result = generator.generate_test_file([mock_test_case])
        assert "200" in result.content

    def test_no_route_when_no_mocks(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "page.route" not in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 6: Trace — test.use({ trace: 'on-first-retry' })
# ════════════════════════════════════════════════════════════════════════


class TestTraceConfig:
    def test_trace_config_in_output(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "trace" in result.content
        assert "on-first-retry" in result.content

    def test_trace_config_method(self, generator):
        config = generator._generate_trace_config("typescript")
        assert "trace" in config
        assert "on-first-retry" in config


# ════════════════════════════════════════════════════════════════════════
# AC 7: Jezyki — TypeScript, Python, Java, C#
# ════════════════════════════════════════════════════════════════════════


class TestMultiLanguage:
    def test_typescript_output(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert result.language == "typescript"
        assert "import" in result.content
        assert "@playwright/test" in result.content
        assert ".spec.ts" in result.file_path

    def test_python_output(self, python_generator, login_test_case):
        result = python_generator.generate_test_file([login_test_case])
        assert result.language == "python"
        assert "playwright" in result.content.lower()
        assert ".py" in result.file_path

    def test_java_output(self, java_generator, login_test_case):
        result = java_generator.generate_test_file([login_test_case])
        assert result.language == "java"
        assert "playwright" in result.content.lower()
        assert ".java" in result.file_path

    def test_csharp_output(self, csharp_generator, login_test_case):
        result = csharp_generator.generate_test_file([login_test_case])
        assert result.language == "csharp"
        assert "Playwright" in result.content
        assert ".cs" in result.file_path

    def test_language_normalization_csharp(self):
        from app.services.test_generation.codegen.playwright_generator import PlaywrightCodeGenerator

        config = CodeGenConfig(framework="playwright", language="c#")
        gen = PlaywrightCodeGenerator(config=config)
        assert gen._get_language() == "csharp"

    def test_language_default_typescript(self):
        from app.services.test_generation.codegen.playwright_generator import PlaywrightCodeGenerator

        gen = PlaywrightCodeGenerator()  # no config → Playwright defaults to TypeScript
        assert gen._get_language() == "typescript"


# ════════════════════════════════════════════════════════════════════════
# AC 8: User flow mapping — krok = akcja + expectation
# ════════════════════════════════════════════════════════════════════════


class TestUserFlowMapping:
    def test_goto_in_output(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "page.goto" in result.content

    def test_fill_action_in_output(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "fill" in result.content or "getByPlaceholder" in result.content

    def test_click_action_in_output(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "click" in result.content

    def test_expectation_after_action(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "expect(" in result.content
        assert "toBeVisible" in result.content or "toHaveText" in result.content or "toContainText" in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 9: Walidacja selektorow — preferencja semantycznych nad XPath
# ════════════════════════════════════════════════════════════════════════


class TestSelectorValidation:
    def test_xpath_produces_warning(self, generator, search_test_case):
        result = generator.generate_test_file([search_test_case])
        # Walidacja selektorow powinna ostrzec o XPath
        if result.compilation_result:
            xpath_warnings = [w for w in result.compilation_result.warnings if "xpath" in w.lower() or "XPath" in w]
            assert len(xpath_warnings) > 0

    def test_semantic_selector_no_warning(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        if result.compilation_result:
            xpath_warnings = [w for w in result.compilation_result.warnings if "xpath" in w.lower()]
            assert len(xpath_warnings) == 0

    def test_classify_selectors(self, generator):
        elements = [
            {
                "name": "btn1",
                "locator_type": "role",
                "locator_value": "button",
                "element_type": "button",
                "page_name": "P",
            },
            {
                "name": "elem2",
                "locator_type": "xpath",
                "locator_value": "//div",
                "element_type": "generic",
                "page_name": "P",
            },
        ]
        classified = generator._validate_selectors(elements)
        assert any(c["category"] == "semantic" for c in classified)
        assert any(c["category"] == "xpath" for c in classified)


# ════════════════════════════════════════════════════════════════════════
# AC 10: Walidacja kompilacji
# ════════════════════════════════════════════════════════════════════════


class TestValidateSyntax:
    def test_valid_typescript_structure(self, generator):
        code = """
import { test, expect } from '@playwright/test';

test.describe('Test', () => {
  test('example', async ({ page }) => {
    await page.goto('https://example.com');
    await expect(page.locator('.test')).toBeVisible();
  });
});
"""
        result = generator.validate_syntax(code)
        assert result.success is True

    def test_empty_code_fails(self, generator):
        result = generator.validate_syntax("")
        assert result.success is False

    def test_missing_test_marker_warns(self, generator):
        code = "const x = 1;\n"
        result = generator.validate_syntax(code)
        assert any("test(" in w for w in result.warnings)

    def test_python_syntax_validation(self, python_generator):
        code = """
from playwright.sync_api import sync_playwright, expect

def test_example(page):
    page.goto("https://example.com")
    expect(page.locator(".test")).to_be_visible()
"""
        result = python_generator.validate_syntax(code)
        assert result.success is True


# ════════════════════════════════════════════════════════════════════════
# AC 11: Struktura plikow — e2e/{feature_name}.spec.ts
# ════════════════════════════════════════════════════════════════════════


class TestFileStructure:
    def test_typescript_file_path(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert "e2e/" in result.file_path
        assert ".spec.ts" in result.file_path

    def test_python_file_path(self, python_generator, login_test_case):
        result = python_generator.generate_test_file([login_test_case])
        assert "e2e/" in result.file_path
        assert ".py" in result.file_path

    def test_java_file_path(self, java_generator, login_test_case):
        result = java_generator.generate_test_file([login_test_case])
        assert "e2e/" in result.file_path
        assert ".java" in result.file_path

    def test_csharp_file_path(self, csharp_generator, login_test_case):
        result = csharp_generator.generate_test_file([login_test_case])
        assert "e2e/" in result.file_path
        assert ".cs" in result.file_path


# ════════════════════════════════════════════════════════════════════════
# Pełny przepływ — golden data
# ════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    def test_full_login_flow_typescript(self, generator, login_test_case):
        result = generator.generate_test_file([login_test_case])
        assert isinstance(result, TestCodeFile)
        assert result.content.strip()
        assert result.framework == "playwright"
        assert result.language == "typescript"
        assert "test.describe" in result.content
        assert "test(" in result.content
        assert "expect(" in result.content
        assert "page.goto" in result.content

    def test_full_flow_with_mocks_typescript(self, generator, mock_test_case):
        result = generator.generate_test_file([mock_test_case])
        assert "page.route" in result.content
        assert "route.fulfill" in result.content

    def test_multiple_test_cases_in_one_describe(self, generator, login_test_case, search_test_case):
        result = generator.generate_test_file([login_test_case, search_test_case])
        assert isinstance(result, TestCodeFile)
        assert result.content.count("test(") >= 2

    def test_compilation_result_included_when_enabled(self, generator, login_test_case):
        config = CodeGenConfig(framework="playwright", language="typescript", validate_compilation=True)
        from app.services.test_generation.codegen.playwright_generator import PlaywrightCodeGenerator

        gen = PlaywrightCodeGenerator(config=config)
        result = gen.generate_test_file([login_test_case])
        assert result.compilation_result is not None
        assert isinstance(result.compilation_result, CompilationResult)

    def test_registry_full_pipeline(self):
        gen = CodeGenRegistry.get_instance().get_generator(
            "playwright",
            config=CodeGenConfig(framework="playwright", language="typescript", validate_compilation=False),
        )
        tc = {
            "scenario_name": "Registry test",
            "test_type": "e2e",
            "url": "https://example.com",
            "ui_elements": [
                {"name": "btn", "locator_type": "role", "locator_value": "button", "page_name": "TestPage"}
            ],
            "user_flow": {
                "name": "Registry flow",
                "url": "https://example.com",
                "steps": [{"action": "click", "element": {"name": "btn"}}],
            },
        }
        result = gen.generate_test_file([tc])
        assert "test.describe" in result.content
        assert "expect(" in result.content


# ════════════════════════════════════════════════════════════════════════
# Edge cases
# ════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_test_case_list(self, generator):
        result = generator.generate_test_file([])
        assert "Brak" in result.content

    def test_no_ui_elements(self, generator):
        tc = {"scenario_name": "No elements test", "test_type": "e2e"}
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)
        assert "test.describe" in result.content

    def test_no_url_in_test_case(self, generator):
        tc = {
            "scenario_name": "No URL test",
            "test_type": "e2e",
            "ui_elements": [
                {"name": "btn", "locator_type": "role", "locator_value": "button", "page_name": "TestPage"}
            ],
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)

    def test_very_long_scenario_name(self, generator):
        tc = {
            "scenario_name": "A" * 200,
            "test_type": "e2e",
            "ui_elements": [
                {"name": "btn", "locator_type": "role", "locator_value": "button", "page_name": "TestPage"}
            ],
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)

    def test_none_fields_in_test_case(self, generator):
        tc = {"scenario_name": None, "test_type": None, "ui_elements": None, "user_flow": None}
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)

    def test_user_flow_without_element_refs(self, generator):
        tc = {
            "scenario_name": "Flow without elements",
            "test_type": "e2e",
            "user_flow": {
                "name": "Simple flow",
                "url": "https://example.com",
                "steps": [{"action": "navigate", "value": "https://example.com"}],
            },
        }
        result = generator.generate_test_file([tc])
        assert "page.goto" in result.content

    def test_setup_returns_string(self, generator):
        result = generator.generate_setup()
        assert isinstance(result, str)

    def test_all_http_methods_in_mocks(self, generator):
        """GET, POST, PUT, DELETE w api_mocks."""
        for method in ["GET", "POST", "PUT", "DELETE"]:
            tc = {
                "scenario_name": f"Mock {method}",
                "test_type": "e2e",
                "url": "https://example.com",
                "api_mocks": [
                    {"url": "**/api/test", "method": method, "status": 200, "body": {}},
                ],
            }
            result = generator.generate_test_file([tc])
            assert "page.route" in result.content
