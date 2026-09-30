"""Testy jednostkowe SeleniumCodeGenerator — Story 1.40.

AC: 1-10

Pokrycie:
- Task 1: Core generator (generate_test_file, imports, POM, locators, methods)
- Task 2: Wielu jezykow (Python, Java, C#)
- Task 3: Konfiguracja przegladarki (ChromeDriver, headless, teardown)
- Task 4: Szablony Jinja2 (TestPage.py.j2, .java.j2, .cs.j2)
- Task 5: Walidacja skladni (py_compile / strukturalna)
- Task 6: Rejestracja w CodeGenRegistry
- Task 7: Explicit waits (WebDriverWait + EC)
- Task 8: Edge cases (puste dane, brak elementow, brak URL)
"""

import pytest

from app.services.test_generation.codegen.base import (
    CodeGenConfig,
    CodeGenRegistry,
    CompilationResult,
    TestCodeFile,
)
from app.services.test_generation.codegen.selenium_generator import SeleniumCodeGenerator

# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def python_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="selenium",
        language="python",
        file_extension=".py",
        validate_compilation=False,
    )


@pytest.fixture
def java_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="selenium",
        language="java",
        file_extension=".java",
        validate_compilation=False,
    )


@pytest.fixture
def csharp_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="selenium",
        language="csharp",
        file_extension=".cs",
        validate_compilation=False,
    )


@pytest.fixture
def generator(python_config: CodeGenConfig) -> SeleniumCodeGenerator:
    return SeleniumCodeGenerator(config=python_config)


@pytest.fixture
def java_generator(java_config: CodeGenConfig) -> SeleniumCodeGenerator:
    return SeleniumCodeGenerator(config=java_config)


@pytest.fixture
def csharp_generator(csharp_config: CodeGenConfig) -> SeleniumCodeGenerator:
    return SeleniumCodeGenerator(config=csharp_config)


@pytest.fixture
def login_test_case() -> dict:
    """Login flow z elementami GUI — podstawowy golden data."""
    return {
        "scenario_name": "User login",
        "test_type": "e2e",
        "url": "https://example.com/login",
        "ui_elements": [
            {
                "name": "username_input",
                "locator_type": "id",
                "locator_value": "username",
                "element_type": "input",
                "page_name": "LoginPage",
            },
            {
                "name": "password_input",
                "locator_type": "id",
                "locator_value": "password",
                "element_type": "input",
                "page_name": "LoginPage",
            },
            {
                "name": "login_button",
                "locator_type": "css",
                "locator_value": "button[type='submit']",
                "element_type": "button",
                "page_name": "LoginPage",
            },
            {
                "name": "welcome_message",
                "locator_type": "css",
                "locator_value": ".welcome",
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
def search_test_case() -> dict:
    """Search flow z XPath lokatorami."""
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
                "locator_type": "css",
                "locator_value": ".search-btn",
                "element_type": "button",
                "page_name": "HomePage",
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
# AC 1: Generator registration — SeleniumCodeGenerator
# ════════════════════════════════════════════════════════════════════════


class TestGeneratorRegistration:
    def test_registry_has_selenium_generator(self):
        assert CodeGenRegistry.get_instance().is_supported("selenium")

    def test_registry_get_selenium_generator(self):
        gen = CodeGenRegistry.get_instance().get_generator("selenium")
        assert isinstance(gen, SeleniumCodeGenerator)

    def test_framework_constants(self, generator: SeleniumCodeGenerator):
        assert generator.FRAMEWORK == "selenium"
        assert generator.LANGUAGE == "python"
        assert generator.FILE_EXTENSION == ".py"


# ════════════════════════════════════════════════════════════════════════
# AC 2: Importy Selenium per jezyk
# ════════════════════════════════════════════════════════════════════════


class TestImports:
    def test_python_imports_contain_selenium(self, generator: SeleniumCodeGenerator, python_config: CodeGenConfig):
        imports = generator._build_imports([{}], python_config, "python")
        assert any("selenium" in imp for imp in imports)
        assert any("webdriver" in imp for imp in imports)
        assert any("By" in imp for imp in imports)
        assert any("WebDriverWait" in imp for imp in imports)
        assert any("expected_conditions" in imp for imp in imports)

    def test_java_imports_contain_openqa(self, java_generator: SeleniumCodeGenerator, java_config: CodeGenConfig):
        imports = java_generator._build_imports([{}], java_config, "java")
        assert any("org.openqa.selenium" in imp for imp in imports)
        assert any("chrome" in imp.lower() for imp in imports)
        assert any("support.ui" in imp for imp in imports)  # WebDriverWait jest w support.ui.*

    def test_csharp_imports_contain_openqa(self, csharp_generator: SeleniumCodeGenerator, csharp_config: CodeGenConfig):
        imports = csharp_generator._build_imports([{}], csharp_config, "csharp")
        assert any("OpenQA.Selenium" in imp for imp in imports)
        assert any("Chrome" in imp for imp in imports)
        assert any("WebDriverWait" in imp or "Support" in imp for imp in imports)

    def test_explicit_imports_from_test_case(self, generator: SeleniumCodeGenerator, python_config: CodeGenConfig):
        tc = {"imports": ["import custom_module"]}
        imports = generator._build_imports([tc], python_config, "python")
        assert any("custom_module" in imp for imp in imports)


# ════════════════════════════════════════════════════════════════════════
# AC 3: Page Object Model — lokatory i metody
# ════════════════════════════════════════════════════════════════════════


class TestPageObjectModel:
    def test_pom_class_generated(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "class LoginPage" in result.content

    def test_pom_has_locators(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        # Lokatory musza byc w wygenerowanym kodzie
        assert "By.ID" in result.content or "By.ID," in result.content

    def test_pom_has_click_method(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "click_" in result.content

    def test_pom_has_fill_method(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "fill_" in result.content

    def test_pom_has_get_text_method(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "get_" in result.content and "_text" in result.content

    def test_pom_has_is_visible_method(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "is_" in result.content and "_visible" in result.content

    def test_multiple_pages_generate_multiple_pom(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        # LoginPage i DashboardPage
        assert "LoginPage" in result.content
        assert "DashboardPage" in result.content


class TestLocators:
    @pytest.mark.parametrize(
        "locator_type,expected_fragment",
        [
            ("id", "By.ID"),
            ("css", "By.CSS_SELECTOR"),
            ("xpath", "By.XPATH"),
        ],
    )
    def test_python_locator_syntax(self, generator: SeleniumCodeGenerator, locator_type, expected_fragment):
        elem = {
            "name": "test_element",
            "locator_type": locator_type,
            "locator_value": "test-value",
            "element_type": "generic",
            "page_name": "TestPage",
        }
        locator = generator._generate_locator(elem, "python")
        assert expected_fragment in locator["code"]

    def test_java_locator_id(self, java_generator: SeleniumCodeGenerator):
        elem = {
            "name": "test_element",
            "locator_type": "id",
            "locator_value": "username",
            "element_type": "generic",
            "page_name": "TestPage",
        }
        locator = java_generator._generate_locator(elem, "java")
        assert 'By.id("username")' in locator["code"]

    def test_java_locator_css(self, java_generator: SeleniumCodeGenerator):
        elem = {
            "name": "btn",
            "locator_type": "css",
            "locator_value": ".submit-btn",
            "element_type": "button",
            "page_name": "TestPage",
        }
        locator = java_generator._generate_locator(elem, "java")
        assert 'By.cssSelector(".submit-btn")' in locator["code"]

    def test_csharp_locator_id(self, csharp_generator: SeleniumCodeGenerator):
        elem = {
            "name": "test_element",
            "locator_type": "id",
            "locator_value": "username",
            "element_type": "generic",
            "page_name": "TestPage",
        }
        locator = csharp_generator._generate_locator(elem, "csharp")
        assert 'By.Id("username")' in locator["code"]

    def test_xpath_locator_python(self, generator: SeleniumCodeGenerator):
        elem = {
            "name": "search_input",
            "locator_type": "xpath",
            "locator_value": "//input[@placeholder='Search']",
            "element_type": "input",
            "page_name": "TestPage",
        }
        locator = generator._generate_locator(elem, "python")
        assert "By.XPATH" in locator["code"]
        assert "//input[@placeholder='Search']" in locator["code"]

    def test_normalize_locator_type_css_selector(self):
        assert SeleniumCodeGenerator._normalize_locator_type("css_selector") == "css"
        assert SeleniumCodeGenerator._normalize_locator_type("CSS") == "css"

    def test_normalize_locator_type_class(self):
        assert SeleniumCodeGenerator._normalize_locator_type("class") == "class_name"


# ════════════════════════════════════════════════════════════════════════
# AC 4: Metody testowe — init driver -> navigate -> POM -> asserts -> cleanup
# ════════════════════════════════════════════════════════════════════════


class TestTestMethods:
    def test_test_method_has_navigation(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "driver.get" in result.content

    def test_test_method_has_pom_calls(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "fill_" in result.content or "click_" in result.content

    def test_test_method_has_assertion(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "assert" in result.content.lower()

    def test_multiple_test_cases_generate_multiple_methods(self, generator: SeleniumCodeGenerator):
        tcs = [
            {
                "scenario_name": "Test 1",
                "test_type": "e2e",
                "ui_elements": [{"name": "elem1", "locator_type": "id", "locator_value": "e1", "page_name": "P1"}],
            },
            {
                "scenario_name": "Test 2",
                "test_type": "e2e",
                "ui_elements": [{"name": "elem2", "locator_type": "id", "locator_value": "e2", "page_name": "P2"}],
            },
        ]
        result = generator.generate_test_file(tcs)
        assert "test_" in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 5: Explicit waits — WebDriverWait + expected_conditions
# ════════════════════════════════════════════════════════════════════════


class TestExplicitWaits:
    def test_python_wait_code_presence(self, generator: SeleniumCodeGenerator):
        code = generator._render_explicit_wait_code("submit_btn", "python", "presence")
        assert "WebDriverWait" not in code  # uzywamy self.wait (już zainicjalizowany)
        assert "EC.presence_of_element_located" in code

    def test_python_wait_code_clickable(self, generator: SeleniumCodeGenerator):
        code = generator._render_explicit_wait_code("submit_btn", "python", "clickable")
        assert "EC.element_to_be_clickable" in code

    def test_python_wait_code_visible(self, generator: SeleniumCodeGenerator):
        code = generator._render_explicit_wait_code("submit_btn", "python", "visible")
        assert "EC.visibility_of_element_located" in code

    def test_java_wait_code_presence(self, java_generator: SeleniumCodeGenerator):
        code = java_generator._render_explicit_wait_code("submitBtn", "java", "presence")
        assert "ExpectedConditions.presenceOfElementLocated" in code

    def test_csharp_wait_code_visible(self, csharp_generator: SeleniumCodeGenerator):
        code = csharp_generator._render_explicit_wait_code("submitBtn", "csharp", "visible")
        assert "ExpectedConditions.ElementIsVisible" in code

    def test_no_implicit_wait_or_sleep(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "time.sleep" not in result.content
        assert "implicitly_wait" not in result.content

    def test_explicit_waits_from_test_case(self, generator: SeleniumCodeGenerator):
        tc = {
            "scenario_name": "Wait test",
            "test_type": "e2e",
            "explicit_waits": [
                {"element": "loading_spinner", "condition": "visible", "timeout": 5},
                {"element": "result_text", "condition": "presence", "timeout": 10},
            ],
            "ui_elements": [
                {
                    "name": "loading_spinner",
                    "locator_type": "css",
                    "locator_value": ".spinner",
                    "page_name": "MainPage",
                },
            ],
        }
        result = generator.generate_test_file([tc])
        assert "EC." in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 6: Asserty po akcjach
# ════════════════════════════════════════════════════════════════════════


class TestAssertionsAfterAction:
    def test_assert_element_visible(self, generator: SeleniumCodeGenerator):
        result = generator.generate_assertion("login_btn", 'By.ID, "login"', "element_visible")
        assert "visibility_of_element_located" in result

    def test_assert_text_equals_python(self, generator: SeleniumCodeGenerator):
        result = generator.generate_assertion("Welcome", "header.text", "text_equals")
        assert "assert" in result.lower()

    def test_assert_text_equals_java(self, java_generator: SeleniumCodeGenerator):
        result = java_generator.generate_assertion("Welcome", "header.getText()", "text_equals")
        assert "assertEquals" in result

    def test_assert_text_equals_csharp(self, csharp_generator: SeleniumCodeGenerator):
        result = csharp_generator.generate_assertion("Welcome", "header.Text", "text_equals")
        assert "Assert.Equal" in result

    def test_assert_url_contains_python(self, generator: SeleniumCodeGenerator):
        result = generator.generate_assertion("login", "self.driver.current_url", "url_contains")
        assert "login" in result
        assert "driver.current_url" in result

    def test_assert_url_contains_java(self, java_generator: SeleniumCodeGenerator):
        result = java_generator.generate_assertion("login", "driver.getCurrentUrl()", "url_contains")
        assert "getCurrentUrl" in result

    def test_assert_url_contains_csharp(self, csharp_generator: SeleniumCodeGenerator):
        result = csharp_generator.generate_assertion("login", "driver.Url", "url_contains")
        assert "driver.Url" in result


# ════════════════════════════════════════════════════════════════════════
# AC 7: Konfiguracja przegladarki — ChromeDriver setup + teardown
# ════════════════════════════════════════════════════════════════════════


class TestBrowserConfiguration:
    def test_chrome_driver_setup_python(self, generator: SeleniumCodeGenerator):
        setup = generator._generate_driver_setup("python")
        assert any("ChromeOptions" in line for line in setup["options_lines"])
        assert any("--headless" in line for line in setup["options_lines"])
        assert any("window-size" in line for line in setup["options_lines"])
        assert "webdriver.Chrome" in setup["driver_init"]

    def test_chrome_driver_setup_java(self, java_generator: SeleniumCodeGenerator):
        setup = java_generator._generate_driver_setup("java")
        assert any("ChromeOptions" in line for line in setup["options_lines"])
        assert "ChromeDriver" in setup["driver_init"]

    def test_chrome_driver_setup_csharp(self, csharp_generator: SeleniumCodeGenerator):
        setup = csharp_generator._generate_driver_setup("csharp")
        assert any("ChromeOptions" in line for line in setup["options_lines"])
        assert "ChromeDriver" in setup["driver_init"]

    def test_headless_option_python(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "--headless" in result.content

    def test_window_size_option(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "window-size" in result.content or "window_size" in result.content

    def test_teardown_quit_python(self, generator: SeleniumCodeGenerator):
        teardown = generator._generate_teardown("python")
        assert "driver.quit()" in teardown["quit"]

    def test_teardown_quit_java(self, java_generator: SeleniumCodeGenerator):
        teardown = java_generator._generate_teardown("java")
        assert "driver.quit()" in teardown["quit"]

    def test_teardown_quit_csharp(self, csharp_generator: SeleniumCodeGenerator):
        teardown = csharp_generator._generate_teardown("csharp")
        assert "driver.Quit()" in teardown["quit"]

    def test_setup_method_in_python_output(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "setup_method" in result.content
        assert "Chrome" in result.content

    def test_teardown_method_in_python_output(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "teardown_method" in result.content
        assert "driver.quit()" in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 8: Walidacja skladni (Python: py_compile, Java/C#: strukturalna)
# ════════════════════════════════════════════════════════════════════════


class TestValidateSyntax:
    def test_valid_python_code_passes(self, generator: SeleniumCodeGenerator):
        code = """
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class LoginPage:
    _username = (By.ID, "username")

    def __init__(self, driver):
        self.driver = driver

class TestLogin:
    def setup_method(self):
        self.driver = webdriver.Chrome()

    def teardown_method(self):
        self.driver.quit()

    def test_login(self):
        self.driver.get("https://example.com")
        assert True
"""
        result = generator.validate_syntax(code)
        assert result.success is True

    def test_invalid_python_code_fails(self, generator: SeleniumCodeGenerator):
        code = "def broken(\n"
        result = generator.validate_syntax(code)
        assert result.success is False

    def test_empty_code_fails(self, generator: SeleniumCodeGenerator):
        result = generator.validate_syntax("")
        assert result.success is False
        assert "Pusty" in result.error_message

    def test_python_warnings_for_missing_selenium(self, generator: SeleniumCodeGenerator):
        code = "x = 1\nprint(x)\n"
        result = generator.validate_syntax(code)
        # Skompiluje sie, ale bedzie ostrzezenie o braku Selenium
        assert any("webdriver" in w for w in result.warnings)

    def test_java_structural_validation_passes(self, java_generator: SeleniumCodeGenerator):
        code = """
import org.openqa.selenium.*;
public class Test {
    private WebDriver driver;
    @Test
    void test() {
        driver.get("url");
    }
}
"""
        result = java_generator.validate_syntax(code)
        assert result.success is True

    def test_java_structural_unbalanced_braces_fails(self, java_generator: SeleniumCodeGenerator):
        code = "public class Test {\n  void test() {\n"
        result = java_generator.validate_syntax(code)
        assert result.success is False

    def test_csharp_structural_validation_passes(self, csharp_generator: SeleniumCodeGenerator):
        code = """
using OpenQA.Selenium;
public class Test {
    private IWebDriver driver;
    [Test]
    public void TestMethod() {
        driver.Url = "url";
    }
}
"""
        result = csharp_generator.validate_syntax(code)
        assert result.success is True

    def test_csharp_missing_using_warns(self, csharp_generator: SeleniumCodeGenerator):
        code = "public class Test { }\n"
        result = csharp_generator.validate_syntax(code)
        assert result.success is False


# ════════════════════════════════════════════════════════════════════════
# AC 9: Wielu jezykow (Python, Java, C#)
# ════════════════════════════════════════════════════════════════════════


class TestMultiLanguage:
    def test_python_output_has_python_syntax(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert result.language == "python"
        assert "from selenium" in result.content
        assert "def " in result.content
        assert ".py" in result.file_path

    def test_java_output_has_java_syntax(self, java_generator: SeleniumCodeGenerator, login_test_case: dict):
        result = java_generator.generate_test_file([login_test_case])
        assert result.language == "java"
        assert "org.openqa.selenium" in result.content
        assert "public class" in result.content
        assert ".java" in result.file_path

    def test_csharp_output_has_csharp_syntax(self, csharp_generator: SeleniumCodeGenerator, login_test_case: dict):
        result = csharp_generator.generate_test_file([login_test_case])
        assert result.language == "csharp"
        assert "OpenQA.Selenium" in result.content
        assert "public class" in result.content
        assert ".cs" in result.file_path

    def test_language_normalization_csharp(self):
        config = CodeGenConfig(framework="selenium", language="c#")
        gen = SeleniumCodeGenerator(config=config)
        assert gen._get_language() == "csharp"

    def test_language_normalization_cs(self):
        config = CodeGenConfig(framework="selenium", language="cs")
        gen = SeleniumCodeGenerator(config=config)
        assert gen._get_language() == "csharp"

    def test_language_normalization_java(self):
        config = CodeGenConfig(framework="selenium", language="Java")
        gen = SeleniumCodeGenerator(config=config)
        assert gen._get_language() == "java"

    def test_language_default_python(self):
        config = CodeGenConfig(framework="selenium")
        gen = SeleniumCodeGenerator(config=config)
        assert gen._get_language() == "python"


# ════════════════════════════════════════════════════════════════════════
# AC 10: Szablony Jinja2
# ════════════════════════════════════════════════════════════════════════


class TestTemplates:
    def test_python_template_renders(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        # Szablon generuje klasy POM
        assert "class " in result.content
        assert "def " in result.content

    def test_java_template_renders(self, java_generator: SeleniumCodeGenerator, login_test_case: dict):
        result = java_generator.generate_test_file([login_test_case])
        assert "public class" in result.content
        assert "void " in result.content

    def test_csharp_template_renders(self, csharp_generator: SeleniumCodeGenerator, login_test_case: dict):
        result = csharp_generator.generate_test_file([login_test_case])
        assert "public class" in result.content
        assert "public void" in result.content

    def test_template_name_selection(self):
        assert SeleniumCodeGenerator._get_template_name("python") == "TestPage.py.j2"
        assert SeleniumCodeGenerator._get_template_name("java") == "TestPage.java.j2"
        assert SeleniumCodeGenerator._get_template_name("csharp") == "TestPage.cs.j2"


# ════════════════════════════════════════════════════════════════════════
# Pełny przepływ — golden data
# ════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    def test_full_login_flow_python(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert isinstance(result, TestCodeFile)
        assert result.content.strip()
        assert result.framework == "selenium"
        assert result.language == "python"
        assert "LoginPage" in result.content
        assert "setup_method" in result.content
        assert "teardown_method" in result.content
        assert "driver.quit()" in result.content

    def test_full_search_flow_python(self, generator: SeleniumCodeGenerator, search_test_case: dict):
        result = generator.generate_test_file([search_test_case])
        assert isinstance(result, TestCodeFile)
        assert "By.XPATH" in result.content
        assert "HomePage" in result.content

    def test_full_flow_java(self, java_generator: SeleniumCodeGenerator, login_test_case: dict):
        result = java_generator.generate_test_file([login_test_case])
        assert "org.openqa.selenium" in result.content
        assert "ChromeDriver" in result.content
        assert "driver.quit()" in result.content

    def test_full_flow_csharp(self, csharp_generator: SeleniumCodeGenerator, login_test_case: dict):
        result = csharp_generator.generate_test_file([login_test_case])
        assert "OpenQA.Selenium" in result.content
        assert "ChromeDriver" in result.content
        assert "driver.Quit()" in result.content

    def test_multiple_test_cases_in_one_file(
        self, generator: SeleniumCodeGenerator, login_test_case: dict, search_test_case: dict
    ):
        result = generator.generate_test_file([login_test_case, search_test_case])
        assert isinstance(result, TestCodeFile)
        assert "test_" in result.content

    def test_file_path_structure_python(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        result = generator.generate_test_file([login_test_case])
        assert "tests/selenium/" in result.file_path
        assert ".py" in result.file_path

    def test_file_path_structure_java(self, java_generator: SeleniumCodeGenerator, login_test_case: dict):
        result = java_generator.generate_test_file([login_test_case])
        assert ".java" in result.file_path

    def test_file_path_structure_csharp(self, csharp_generator: SeleniumCodeGenerator, login_test_case: dict):
        result = csharp_generator.generate_test_file([login_test_case])
        assert ".cs" in result.file_path

    def test_registry_full_pipeline(self):
        gen = CodeGenRegistry.get_instance().get_generator(
            "selenium",
            config=CodeGenConfig(framework="selenium", language="python", validate_compilation=False),
        )
        assert isinstance(gen, SeleniumCodeGenerator)
        tc = {
            "scenario_name": "Registry test",
            "test_type": "e2e",
            "ui_elements": [{"name": "btn", "locator_type": "id", "locator_value": "submit", "page_name": "TestPage"}],
        }
        result = gen.generate_test_file([tc])
        assert "By.ID" in result.content or "By.ID," in result.content
        assert "driver.quit()" in result.content

    def test_compilation_result_included_when_enabled(self, generator: SeleniumCodeGenerator, login_test_case: dict):
        config = CodeGenConfig(framework="selenium", language="python", validate_compilation=True)
        gen = SeleniumCodeGenerator(config=config)
        result = gen.generate_test_file([login_test_case])
        assert result.compilation_result is not None
        assert isinstance(result.compilation_result, CompilationResult)


# ════════════════════════════════════════════════════════════════════════
# Edge cases
# ════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_test_case_list(self, generator: SeleniumCodeGenerator):
        result = generator.generate_test_file([])
        assert "Brak test case" in result.content

    def test_no_ui_elements_generates_empty_pom(self, generator: SeleniumCodeGenerator):
        tc = {
            "scenario_name": "No elements test",
            "test_type": "e2e",
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)
        assert "class " in result.content

    def test_empty_locator_value(self, generator: SeleniumCodeGenerator):
        tc = {
            "scenario_name": "Empty locator",
            "test_type": "e2e",
            "ui_elements": [
                {"name": "elem", "locator_type": "id", "locator_value": "", "page_name": "TestPage"},
            ],
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)

    def test_no_url_in_test_case(self, generator: SeleniumCodeGenerator):
        tc = {
            "scenario_name": "No URL test",
            "test_type": "e2e",
            "ui_elements": [{"name": "btn", "locator_type": "id", "locator_value": "btn", "page_name": "TestPage"}],
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)
        assert "class " in result.content

    def test_very_long_scenario_name(self, generator: SeleniumCodeGenerator):
        tc = {
            "scenario_name": "A" * 200,
            "test_type": "e2e",
            "ui_elements": [{"name": "btn", "locator_type": "id", "locator_value": "btn", "page_name": "TestPage"}],
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)

    def test_none_fields_in_test_case(self, generator: SeleniumCodeGenerator):
        tc = {
            "scenario_name": None,
            "test_type": None,
            "ui_elements": None,
            "user_flow": None,
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)
        assert "class " in result.content

    def test_user_flow_without_element_refs(self, generator: SeleniumCodeGenerator):
        tc = {
            "scenario_name": "Flow without elements",
            "test_type": "e2e",
            "user_flow": {
                "name": "Simple flow",
                "url": "https://example.com",
                "steps": [
                    {"action": "navigate", "value": "https://example.com"},
                ],
            },
        }
        result = generator.generate_test_file([tc])
        assert isinstance(result, TestCodeFile)
        assert "driver.get" in result.content

    def test_setup_returns_string(self, generator: SeleniumCodeGenerator):
        result = generator.generate_setup()
        assert isinstance(result, str)


# ════════════════════════════════════════════════════════════════════════
# Metody pomocnicze
# ════════════════════════════════════════════════════════════════════════


class TestHelperMethods:
    def test_make_class_name(self):
        assert SeleniumCodeGenerator._make_class_name("login_page", "python") == "LoginPage"
        assert SeleniumCodeGenerator._make_class_name("user-profile", "java") == "UserProfile"
        assert SeleniumCodeGenerator._make_class_name("Calculator", "python") == "Calculator"
        assert SeleniumCodeGenerator._make_class_name("", "python") == "Unnamed"

    def test_normalize_element_name(self):
        assert SeleniumCodeGenerator._normalize_element_name("Submit Button", "python") == "submit_button"
        assert SeleniumCodeGenerator._normalize_element_name("username-input", "python") == "username_input"
        assert SeleniumCodeGenerator._normalize_element_name("", "python") == "element"

    def test_normalize_test_method_name_python(self):
        result = SeleniumCodeGenerator._normalize_test_method_name("User login flow", "python")
        assert result.startswith("test_")
        assert "user" in result

    def test_normalize_test_method_name_java(self):
        result = SeleniumCodeGenerator._normalize_test_method_name("User login flow", "java")
        assert "user" in result.lower()
        assert not result.startswith("test_")

    def test_normalize_test_method_name_csharp(self):
        result = SeleniumCodeGenerator._normalize_test_method_name("User login flow", "csharp")
        assert result[0].isupper()

    def test_extract_module_name(self):
        assert SeleniumCodeGenerator._extract_module_name({"scenario_name": "Login test"}) == "Login_test"
        assert SeleniumCodeGenerator._extract_module_name({"scenario_name": None}) == "unnamed"

    def test_build_file_path_python(self):
        result = SeleniumCodeGenerator._build_file_path("LoginTest", ".py")
        assert result == "tests/selenium/LoginTest/LoginTestTest.py"

    def test_fallback_render_python(self, generator: SeleniumCodeGenerator):
        context = {
            "module_name": "TestModule",
            "imports": ["from selenium import webdriver"],
            "page_objects": [],
            "test_class_name": "TestSuite",
            "driver_setup": {
                "options_lines": [],
                "driver_init": "self.driver = webdriver.Chrome()",
                "wait_init": "self.wait = WebDriverWait(self.driver, 10)",
            },
            "teardown": {"quit": "self.driver.quit()"},
            "test_methods": [
                {
                    "name": "test_example",
                    "url": "",
                    "pom_calls": [],
                    "assertions": [],
                    "waits": [],
                    "scenario": "example",
                }
            ],
        }
        result = generator._fallback_render_python(context)
        assert "class TestSuite" in result
        assert "driver.quit()" in result

    def test_fallback_render_java(self, java_generator: SeleniumCodeGenerator):
        context = {
            "module_name": "TestModule",
            "imports": [],
            "page_objects": [],
            "test_class_name": "TestSuite",
            "driver_setup": {
                "options_lines": [],
                "driver_init": "this.driver = new ChromeDriver()",
                "wait_init": "this.wait = new WebDriverWait(...)",
            },
            "teardown": {"quit": "this.driver.quit()"},
            "test_methods": [],
        }
        result = java_generator._fallback_render_java(context)
        assert "public class TestSuite" in result
        assert "driver.quit()" in result

    def test_fallback_render_csharp(self, csharp_generator: SeleniumCodeGenerator):
        context = {
            "module_name": "TestModule",
            "imports": [],
            "page_objects": [],
            "test_class_name": "TestSuite",
            "driver_setup": {
                "options_lines": [],
                "driver_init": "this.driver = new ChromeDriver()",
                "wait_init": "this.wait = new WebDriverWait(...)",
            },
            "teardown": {"quit": "this.driver.Quit()"},
            "test_methods": [],
        }
        result = csharp_generator._fallback_render_csharp(context)
        assert "public class TestSuite" in result
        assert "driver.Quit()" in result

    def test_parse_compile_error(self):
        msg = 'File "test.py", line 42'
        line, col = SeleniumCodeGenerator._parse_compile_error(msg)
        assert line == 42
        assert col is None
