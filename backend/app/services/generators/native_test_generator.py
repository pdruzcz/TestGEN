"""
Native (template-based) test case generator - Story 1.29

Generates test cases using Jinja2 templates from analysis results:
- Template-based test generation for multiple languages/frameworks
- Positive scenario generation from happy paths
- CRUD test generation from API endpoints
- Unit test generation from function signatures
- Test data generation from type information

Fast, deterministic test generation using code analysis.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from jinja2 import Template

logger = logging.getLogger(__name__)


class TestFramework(StrEnum):
    """Supported test frameworks."""

    PYTEST = "pytest"  # Python
    JUNIT = "junit"  # Java
    NUNIT = "nunit"  # C#
    MOCHA = "mocha"  # JavaScript/TypeScript
    JEST = "jest"  # TypeScript
    SELENIUM = "selenium"  # E2E
    PLAYWRIGHT = "playwright"  # E2E
    APPIUM = "appium"  # E2E mobilne — Story 1.56 (AC3)
    PHPUNIT = "phpunit"  # PHP — Story 1.55 (FR24/FR12)
    PEST = "pest"  # PHP (DSL nad PHPUnit) — Story 1.55 (FR24/FR12)
    UNITTEST = "unittest"  # Python (natywny) — Story 1.57
    TESTNG = "testng"  # Java — Story 1.57
    MSTEST = "mstest"  # C# — Story 1.57


class TestType(StrEnum):
    """Types of tests to generate."""

    POSITIVE = "positive"  # Happy path tests
    NEGATIVE = "negative"  # Error case tests
    BOUNDARY = "boundary"  # Edge case tests
    UNIT = "unit"  # Unit tests
    INTEGRATION = "integration"  # Integration tests
    E2E = "e2e"  # End-to-end tests


@dataclass
class GeneratedTestCase:
    """A generated test case."""

    name: str
    description: str
    test_type: TestType
    framework: TestFramework
    language: str
    code: str  # Generated test code
    source_file: str  # File this test is for
    source_function: str | None = None  # Function being tested
    test_data: dict[str, Any] | None = None  # Test input data


@dataclass
class TestSuite:
    """A collection of generated test cases."""

    name: str
    framework: TestFramework
    language: str
    source_files: list[str] = field(default_factory=list)
    test_cases: list[GeneratedTestCase] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def get_statistics(self) -> dict[str, Any]:
        """Get test suite statistics."""
        test_types = {}
        for tc in self.test_cases:
            test_types[tc.test_type] = test_types.get(tc.test_type, 0) + 1

        return {
            "total_tests": len(self.test_cases),
            "test_types": test_types,
            "source_files_count": len(self.source_files),
        }

    def to_dict(self) -> dict:
        """Convert test suite to dictionary."""
        return {
            "name": self.name,
            "framework": self.framework,
            "language": self.language,
            "source_files": self.source_files,
            "test_cases": [
                {
                    "name": tc.name,
                    "description": tc.description,
                    "test_type": tc.test_type,
                    "code": tc.code,
                    "source_file": tc.source_file,
                    "source_function": tc.source_function,
                }
                for tc in self.test_cases
            ],
            "generated_at": self.generated_at.isoformat(),
            "statistics": self.get_statistics(),
        }


class NativeTestGenerator:
    """Generates test cases using templates from analysis results."""

    def __init__(self, templates_dir: Path | None = None):
        self.templates_dir = templates_dir or Path("app/services/generators/templates")
        self.templates = {}
        self._load_templates()

    def _load_templates(self):
        """Load Jinja2 templates for test generation."""
        self.templates = {
            TestFramework.PYTEST: Template(
                """def test_{{ name }}():
    \"\"\"{{ description }}\"\"\"
    {% for line in setup %}
    {{ line }}
    {% endfor %}

    # Test execution
    result = {{ test_call }}
    assert result {{ assertion }}

def test_{{ name }}_{{ variant }}():
    \"\"\"{{ description }} ({{ variant }} case)\"\"\"
    # {{ test_data }}
    with pytest.raises({{ error_type }}):
        {{ test_call }}
"""
            ),
            TestFramework.JUNIT: Template(
                """@Test
public void {{ name }}() {
    // {{ description }}
    {{ setup }}

    // Test execution
    {{ test_call }}
    assertEquals({{ expected }}, result);
}"""
            ),
            TestFramework.MOCHA: Template(
                """describe('{{ name }}', () => {
    it('{{ description }}', () => {
        // {{ setup }}

        // Test execution
        const result = {{ test_call }};
        assert(result {{ assertion }});
    });
});"""
            ),
            TestFramework.PHPUNIT: Template(
                """<?php
// {{ description }}
use PHPUnit\\Framework\\TestCase;

final class {{ class_name }}Test extends TestCase
{
    public function test{{ name }}(): void
    {
        {{ setup }}

        // Test execution
        {{ test_call }}
        $this->{{ assertion }};
    }
}"""
            ),
            TestFramework.PEST: Template(
                """<?php
// {{ description }}
it('{{ description }}', function () {
    {{ setup }}

    // Test execution
    {{ test_call }}
    expect({{ assertion_var }})->not->toBeNull();
});"""
            ),
        }

    def generate_tests(
        self,
        analysis_result: dict,
        framework: TestFramework = TestFramework.PYTEST,
        test_type: TestType = TestType.POSITIVE,
    ) -> TestSuite:
        """
        Generate test cases from analysis results.

        Args:
            analysis_result: Analysis result from native/LLM analysis
            framework: Test framework to generate for
            test_type: Type of tests to generate

        Returns:
            Generated test suite
        """
        language = analysis_result.get("language", "python")
        source_files = analysis_result.get("source_files", [])

        suite = TestSuite(
            name=f"{language}_tests",
            framework=framework,
            language=language,
            source_files=source_files,
        )

        # Generate tests from entry points
        entry_points = (analysis_result.get("entry_points") or {}).get("endpoints", [])
        for endpoint in entry_points:
            test_cases = self._generate_endpoint_tests(endpoint, framework, test_type)
            suite.test_cases.extend(test_cases)

        # Generate tests from functions
        functions = (analysis_result.get("logic_structures") or {}).get("functions", [])
        for func in functions[:10]:  # Limit to prevent too many tests
            test_cases = self._generate_function_tests(func, framework, test_type, language)
            suite.test_cases.extend(test_cases)

        return suite

    def _generate_endpoint_tests(
        self,
        endpoint: dict,
        framework: TestFramework,
        test_type: TestType,
    ) -> list[GeneratedTestCase]:
        """Generate test cases for an API endpoint."""
        test_cases = []

        path = endpoint.get("path") or "/"
        method = endpoint.get("http_method") or "GET"
        name = endpoint.get("name", "test_endpoint")

        if test_type == TestType.POSITIVE:
            test_case = GeneratedTestCase(
                name=f"test_{name}_success",
                description=f"Test {method} {path} - success case",
                test_type=TestType.POSITIVE,
                framework=framework,
                language="php" if framework in (TestFramework.PHPUNIT, TestFramework.PEST) else "python",
                code=self._render_endpoint_test(endpoint, "success", framework),
                source_file=endpoint.get("file_path", ""),
                source_function=name,
            )
            test_cases.append(test_case)

        elif test_type == TestType.NEGATIVE:
            test_case = GeneratedTestCase(
                name=f"test_{name}_not_found",
                description=f"Test {method} {path} - not found",
                test_type=TestType.NEGATIVE,
                framework=framework,
                language="php" if framework in (TestFramework.PHPUNIT, TestFramework.PEST) else "python",
                code=self._render_endpoint_test(endpoint, "not_found", framework),
                source_file=endpoint.get("file_path", ""),
                source_function=name,
            )
            test_cases.append(test_case)

        return test_cases

    def _generate_function_tests(
        self,
        func: dict,
        framework: TestFramework,
        test_type: TestType,
        language: str,
    ) -> list[GeneratedTestCase]:
        """Generate test cases for a function."""
        test_cases = []

        name = func.get("name", "test_func")

        if test_type == TestType.POSITIVE:
            test_case = GeneratedTestCase(
                name=f"test_{name}_success",
                description=f"Test {name} - success case",
                test_type=TestType.POSITIVE,
                framework=framework,
                language=language,
                code=self._render_function_test(func, "success", framework),
                source_file=func.get("file_path", ""),
                source_function=name,
            )
            test_cases.append(test_case)

        return test_cases

    def _render_endpoint_test(self, endpoint: dict, scenario: str, framework: TestFramework) -> str:
        """Render test code for an endpoint scenario."""
        path = endpoint.get("path") or "/"
        method = (endpoint.get("http_method") or "GET").lower()
        name = endpoint.get("name", "test_endpoint")
        params = endpoint.get("parameters", [])

        if framework == TestFramework.PYTEST:
            if scenario == "success":
                # Build body for POST/PUT/PATCH
                body_setup = ""
                body_arg = ""
                if method in ("post", "put", "patch"):
                    body_vars = {}
                    for p in params:
                        p_loc = p.get("location", "body")
                        if p_loc in ("body", "query"):
                            ptype = p.get("type", "str")
                            pname = p.get("name", "data")
                            body_vars[pname] = self._payload_value_for_type(ptype)
                    if body_vars:
                        body_setup = f"\n    payload = {body_vars}\n"
                        body_arg = ", json=payload"
                expected_status = 201 if method == "post" else 200
                return (
                    f"import pytest\n"
                    f"from httpx import AsyncClient\n\n\n"
                    f"def test_{name}_success():\n"
                    f'    """Test {method.upper()} {path} - success case."""\n'
                    f"{body_setup}"
                    f'    response = client.{method}("{path}"{body_arg})\n'
                    f"    assert response.status_code == {expected_status}\n"
                    f"    assert response.json() is not None\n"
                )
            elif scenario == "not_found":
                return (
                    f"import pytest\n"
                    f"from httpx import AsyncClient\n\n\n"
                    f"def test_{name}_not_found():\n"
                    f'    """Test {method.upper()} {path} - not found."""\n'
                    f'    response = client.{method}("{path}")\n'
                    f"    assert response.status_code == 404\n"
                )

        elif framework == TestFramework.JUNIT:
            if scenario == "success":
                return (
                    f"import org.junit.Test;\n"
                    f"import static org.junit.Assert.*;\n\n"
                    f"@Test\n"
                    f"public void {name}Success() {{\n"
                    f"    // Test {method.upper()} {path} - success case\n"
                    f"    ResponseEntity<String> response = restTemplate.exchange(\n"
                    f'        "{path}", HttpMethod.{method.upper()}, null, String.class);\n'
                    f"    assertEquals(200, response.getStatusCode().value());\n"
                    f"    assertNotNull(response.getBody());\n"
                    f"}}\n"
                )
            elif scenario == "not_found":
                return (
                    f"import org.junit.Test;\n"
                    f"import static org.junit.Assert.*;\n\n"
                    f"@Test\n"
                    f"public void {name}NotFound() {{\n"
                    f"    // Test {method.upper()} {path} - not found\n"
                    f"    ResponseEntity<String> response = restTemplate.exchange(\n"
                    f'        "{path}", HttpMethod.{method.upper()}, null, String.class);\n'
                    f"    assertEquals(404, response.getStatusCode().value());\n"
                    f"}}\n"
                )

        elif framework in (TestFramework.MOCHA, TestFramework.JEST):
            if scenario == "success":
                return (
                    f"import request from 'supertest';\n"
                    f"import {{ app }} from './app';\n\n"
                    f"describe('{method.upper()} {path}', () => {{\n"
                    f"  it('should return 200 on success', async () => {{\n"
                    f"    const response = await request(app).{method}('{path}');\n"
                    f"    expect(response.status).toBe(200);\n"
                    f"    expect(response.body).toBeDefined();\n"
                    f"  }});\n"
                    f"}});\n"
                )
            elif scenario == "not_found":
                return (
                    f"import request from 'supertest';\n"
                    f"import {{ app }} from './app';\n\n"
                    f"describe('{method.upper()} {path}', () => {{\n"
                    f"  it('should return 404 when not found', async () => {{\n"
                    f"    const response = await request(app).{method}('{path}');\n"
                    f"    expect(response.status).toBe(404);\n"
                    f"  }});\n"
                    f"}});\n"
                )

        elif framework in (TestFramework.PHPUNIT, TestFramework.PEST):
            expected_status = 201 if (scenario == "success" and method == "post") else 200
            not_found = scenario == "not_found"
            if not_found:
                expected_status = 404
            if framework == TestFramework.PHPUNIT:
                return (
                    f"<?php\n\n"
                    f"use PHPUnit\\Framework\\TestCase;\n\n"
                    f"final class {name.capitalize()}EndpointTest extends TestCase\n"
                    f"{{\n"
                    f"    public function test{name.capitalize()}{scenario.capitalize()}(): void\n"
                    f"    {{\n"
                    f"        // Test {method.upper()} {path} - {scenario}\n"
                    f"        $client = new \\GuzzleHttp\\Client();\n"
                    f"        $response = $client->request('{method.upper()}', '{path}');\n"
                    f"        $this->assertSame({expected_status}, $response->getStatusCode());\n"
                    f"    }}\n"
                    f"}}\n"
                )
            return (
                f"<?php\n\n"
                f"it('{method.upper()} {path} - {scenario}', function () {{\n"
                f"    $response = test()->{method}('{path}');\n"
                f"    expect($response->status())->toBe({expected_status});\n"
                f"}});\n"
            )

        elif framework == TestFramework.SELENIUM:
            return (
                f"import pytest\n"
                f"from selenium import webdriver\n\n\n"
                f"def test_{name}_{scenario}():\n"
                f'    """Selenium E2E: {method.upper()} {path} — {scenario}."""\n'
                f"    driver = webdriver.Chrome()\n"
                f"    try:\n"
                f'        driver.get("http://localhost{path}")\n'
                f"        assert driver.current_url\n"
                f"    finally:\n"
                f"        driver.quit()\n"
            )

        elif framework == TestFramework.PLAYWRIGHT:
            return (
                f"import {{ test, expect }} from '@playwright/test';\n\n\n"
                f"test('{method.upper()} {path} — {scenario}', async ({{ page }}) => {{\n"
                f"  await page.goto('http://localhost{path}');\n"
                f"  await expect(page.locator('body')).toBeVisible();\n"
                f"}});\n"
            )

        elif framework == TestFramework.APPIUM:
            return (
                f"import pytest\n"
                f"from appium import webdriver\n"
                f"from appium.webdriver.common.appiumby import AppiumBy\n\n\n"
                f"def test_{name}_{scenario}():\n"
                f'    """Appium E2E: {method.upper()} {path} — {scenario}."""\n'
                f'    desired_caps = {{"platformName": "Android", "automationName": "UiAutomator2"}}\n'
                f'    driver = webdriver.Remote("http://localhost:4723/wd/hub", desired_caps)\n'
                f"    try:\n"
                f"        assert driver is not None\n"
                f"    finally:\n"
                f"        driver.quit()\n"
            )

        elif framework == TestFramework.UNITTEST:
            return (
                f"import unittest\n\n\n"
                f"class {name.capitalize()}{scenario.capitalize()}Test(unittest.TestCase):\n"
                f"    def test_{name}_{scenario}(self):\n"
                f'        """unittest: {method.upper()} {path} — {scenario}."""\n'
                f"        # TODO: wywołanie API + asercje\n"
                f"        self.assertTrue(True)\n"
            )

        elif framework == TestFramework.TESTNG:
            return (
                f"import org.testng.annotations.Test;\n"
                f"import static org.testng.Assert.*;\n\n\n"
                f"public class {name.capitalize()}{scenario.capitalize()}Test {{\n"
                f"    @Test\n"
                f"    public void test{name.capitalize()}{scenario.capitalize()}() {{\n"
                f"        // TestNG: {method.upper()} {path} — {scenario}\n"
                f"        // TODO: wywołanie API + asercje\n"
                f"    }}\n"
                f"}}\n"
            )

        elif framework == TestFramework.MSTEST:
            return (
                f"using Microsoft.VisualStudio.TestTools.UnitTesting;\n\n\n"
                f"[TestClass]\n"
                f"public class {name.capitalize()}{scenario.capitalize()}Test\n{{\n"
                f"    [TestMethod]\n"
                f"    public void Test{name.capitalize()}{scenario.capitalize()}()\n"
                f"    {{\n"
                f"        // MSTest: {method.upper()} {path} — {scenario}\n"
                f"        // TODO: wywołanie API + asercje\n"
                f"    }}\n"
                f"}}\n"
            )

        return f"# Test for {method.upper()} {path} - {scenario}"

    def _render_function_test(self, func: dict, scenario: str, framework: TestFramework) -> str:
        """Render test code for a function scenario."""
        name = func.get("name", "test_func")
        params = func.get("parameters", [])
        return_type = func.get("return_type", "")
        class_name = func.get("class_name")
        docstring = func.get("docstring", "")

        # Build sample arguments
        args_parts = []
        for p in params:
            pname = p.get("name", "arg")
            ptype = p.get("type", "any")
            args_parts.append(f"{pname}={self._sample_value_for_type(ptype)}")
        args_str = ", ".join(args_parts)

        if framework == TestFramework.PYTEST:
            assertions = self._build_assertions(return_type, "result")
            if class_name:
                setup = f"    instance = {class_name}()\n"
                call = f"    result = instance.{name}({args_str})\n"
            else:
                setup = ""
                call = f"    result = {name}({args_str})\n"

            return (
                f"import pytest\n\n\n"
                f"def test_{name}_{scenario}():\n"
                f'    """Test {name} - {scenario} case.'
                f"{' ' + docstring if docstring else ''}"
                f'"""\n'
                f"{setup}"
                f"{call}"
                f"{assertions}"
            )

        elif framework == TestFramework.JUNIT:
            if class_name:
                call = f"    Object result = new {class_name}().{name}({self._java_args(params)});\n"
            else:
                call = f"    Object result = {name}({self._java_args(params)});\n"
            return (
                f"import org.junit.Test;\n"
                f"import static org.junit.Assert.*;\n\n"
                f"@Test\n"
                f"public void {name}{scenario.capitalize()}() {{\n"
                f"    // Test {name} - {scenario} case\n"
                f"{call}"
                f"    assertNotNull(result);\n"
                f"}}\n"
            )

        elif framework in (TestFramework.MOCHA, TestFramework.JEST):
            if class_name:
                call = f"    const instance = new {class_name}();\n    const result = instance.{name}({args_str});\n"
            else:
                call = f"    const result = {name}({args_str});\n"
            return (
                f"import {{ describe, it, expect }} from '{framework.value}';\n\n"
                f"describe('{name}', () => {{\n"
                f"  it('should handle {scenario} case', () => {{\n"
                f"{call}"
                f"    expect(result).toBeDefined();\n"
                f"  }});\n"
                f"}});\n"
            )

        elif framework == TestFramework.PHPUNIT:
            php_args = self._php_args(params)
            if class_name:
                var = _php_var(class_name)
                setup = f"    ${var} = new {class_name}();\n"
                call = f"    $result = ${var}->{name}({php_args});\n"
            else:
                setup = ""
                call = f"    $result = {name}({php_args});\n"
            return (
                f"<?php\n\n"
                f"use PHPUnit\\Framework\\TestCase;\n\n"
                f"final class {(class_name or 'App').capitalize()}Test extends TestCase\n"
                f"{{\n"
                f"    public function test{name.capitalize()}{scenario.capitalize()}(): void\n"
                f"    {{\n"
                f"        // Test {name} - {scenario} case\n"
                f"{setup}"
                f"{call}"
                f"        $this->assertNotNull($result);\n"
                f"    }}\n"
                f"}}\n"
            )

        elif framework == TestFramework.PEST:
            php_args = self._php_args(params)
            if class_name:
                var = _php_var(class_name)
                setup = f"    ${var} = new {class_name}();\n"
                call = f"    $result = ${var}->{name}({php_args});\n"
            else:
                setup = ""
                call = f"    $result = {name}({php_args});\n"
            return (
                f"<?php\n\n"
                f"it('{name} - {scenario} case', function () {{\n"
                f"{setup}"
                f"{call}"
                f"    expect($result)->not->toBeNull();\n"
                f"}});\n"
            )

        elif framework == TestFramework.SELENIUM:
            return (
                f"import pytest\n"
                f"from selenium import webdriver\n\n\n"
                f"def test_{name}_{scenario}():\n"
                f'    """Selenium E2E dla {name} — {scenario}."""\n'
                f"    driver = webdriver.Chrome()\n"
                f"    try:\n"
                f"        # TODO: kroki E2E dla {name}({args_str})\n"
                f"        assert driver.current_url\n"
                f"    finally:\n"
                f"        driver.quit()\n"
            )

        elif framework == TestFramework.PLAYWRIGHT:
            return (
                f"import {{ test, expect }} from '@playwright/test';\n\n\n"
                f"test('{name} — {scenario}', async ({{ page }}) => {{\n"
                f"  // TODO: kroki E2E dla {name}({args_str})\n"
                f"  await expect(page.locator('body')).toBeVisible();\n"
                f"}});\n"
            )

        elif framework == TestFramework.APPIUM:
            return (
                f"import pytest\n"
                f"from appium import webdriver\n"
                f"from appium.webdriver.common.appiumby import AppiumBy\n\n\n"
                f"def test_{name}_{scenario}():\n"
                f'    """Appium E2E dla {name} — {scenario}."""\n'
                f'    desired_caps = {{"platformName": "Android", "automationName": "UiAutomator2"}}\n'
                f'    driver = webdriver.Remote("http://localhost:4723/wd/hub", desired_caps)\n'
                f"    try:\n"
                f"        # TODO: kroki mobilne dla {name}({args_str})\n"
                f"        assert driver is not None\n"
                f"    finally:\n"
                f"        driver.quit()\n"
            )

        elif framework == TestFramework.UNITTEST:
            return (
                f"import unittest\n\n\n"
                f"class {name.capitalize()}{scenario.capitalize()}Test(unittest.TestCase):\n"
                f"    def test_{name}_{scenario}(self):\n"
                f'        """unittest: {name} — {scenario}."""\n'
                f"        # TODO: kroki dla {name}({args_str})\n"
                f"        self.assertTrue(True)\n"
            )

        elif framework == TestFramework.TESTNG:
            return (
                f"import org.testng.annotations.Test;\n"
                f"import static org.testng.Assert.*;\n\n\n"
                f"public class {name.capitalize()}{scenario.capitalize()}Test {{\n"
                f"    @Test\n"
                f"    public void test{name.capitalize()}{scenario.capitalize()}() {{\n"
                f"        // TestNG: {name} — {scenario}\n"
                f"        // TODO: kroki dla {name}({args_str})\n"
                f"        Assert.assertTrue(true);\n"
                f"    }}\n"
                f"}}\n"
            )

        elif framework == TestFramework.MSTEST:
            return (
                f"using Microsoft.VisualStudio.TestTools.UnitTesting;\n\n\n"
                f"[TestClass]\n"
                f"public class {name.capitalize()}{scenario.capitalize()}Test\n{{\n"
                f"    [TestMethod]\n"
                f"    public void Test{name.capitalize()}{scenario.capitalize()}()\n"
                f"    {{\n"
                f"        // MSTest: {name} — {scenario}\n"
                f"        // TODO: kroki dla {name}({args_str})\n"
                f"        Assert.IsTrue(true);\n"
                f"    }}\n"
                f"}}\n"
            )

        return f"# Test for {name} - {scenario}"

    def _sample_value_for_type(self, param_type: str) -> str:
        """Return a sample value literal for a given type (as code string)."""
        type_map = {
            "str": '"test_value"',
            "string": '"test_value"',
            "int": "42",
            "integer": "42",
            "float": "3.14",
            "bool": "True",
            "boolean": "True",
            "list": "[1, 2, 3]",
            "array": "[1, 2, 3]",
            "dict": '{"key": "value"}',
            "dict[str, any]": '{"key": "value"}',
            "none": "None",
            "none_type": "None",
            "uuid": '"550e8400-e29b-41d4-a716-446655440000"',
            "any": '"test"',
        }
        return type_map.get(param_type.lower(), '"test"')

    def _payload_value_for_type(self, param_type: str) -> Any:
        """Return an actual Python value for use in request payloads."""
        type_map = {
            "str": "test_value",
            "string": "test_value",
            "int": 42,
            "integer": 42,
            "float": 3.14,
            "bool": True,
            "boolean": True,
            "list": [1, 2, 3],
            "array": [1, 2, 3],
            "dict": {"key": "value"},
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "any": "test",
        }
        return type_map.get(param_type.lower(), "test")

    def _java_args(self, params: list[dict]) -> str:
        """Build Java-style argument list for JUnit tests."""
        parts = []
        for p in params:
            ptype = p.get("type", "String")
            if ptype.lower() in ("int", "integer"):
                parts.append("42")
            elif ptype.lower() in ("float", "double"):
                parts.append("3.14")
            elif ptype.lower() in ("bool", "boolean"):
                parts.append("true")
            else:
                parts.append('"test_value"')
        return ", ".join(parts)

    def _php_args(self, params: list[dict]) -> str:
        """Build PHP-style argument list for PHPUnit/Pest tests (Story 1.55)."""
        return ", ".join(_php_sample_value_for_type(p.get("type", "any")) for p in params)

    def _build_assertions(self, return_type: str, var_name: str) -> str:
        """Build assertion lines based on return type for pytest."""
        rt = return_type.lower() if return_type else ""
        if rt in ("none", "none_type", ""):
            return f"    assert {var_name} is not None\n"
        if rt in ("bool", "boolean"):
            return f"    assert {var_name} is not None\n    assert isinstance({var_name}, bool)\n"
        if rt in ("int", "integer"):
            return f"    assert {var_name} is not None\n    assert isinstance({var_name}, int)\n"
        if rt in ("float",):
            return f"    assert {var_name} is not None\n    assert isinstance({var_name}, (int, float))\n"
        if rt in ("str", "string"):
            return f"    assert {var_name} is not None\n    assert isinstance({var_name}, str)\n"
        if rt in ("list", "array", "dict", "dict[str, any]"):
            return f"    assert {var_name} is not None\n"
        return f"    assert {var_name} is not None\n"


def get_native_test_generator() -> NativeTestGenerator:
    """Get or create native test generator instance."""
    return NativeTestGenerator()


def _php_var(class_name: str) -> str:
    """CamelCase variable name for a PHP class (Calculator → calculator)."""
    return class_name[:1].lower() + class_name[1:] if class_name else "instance"


def _php_sample_value_for_type(param_type: str) -> str:
    """PHP literal for a sample value of a given type (Story 1.55)."""
    type_map = {
        "str": "'test_value'",
        "string": "'test_value'",
        "int": "42",
        "integer": "42",
        "float": "3.14",
        "bool": "true",
        "boolean": "true",
        "list": "[1, 2, 3]",
        "array": "[1, 2, 3]",
        "dict": "['key' => 'value']",
        "none": "null",
        "none_type": "null",
        "uuid": "'550e8400-e29b-41d4-a716-446655440000'",
        "any": "'test'",
    }
    return type_map.get(param_type.lower(), "'test'")
