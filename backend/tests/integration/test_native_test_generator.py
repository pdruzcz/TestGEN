"""Tests for native test generator - Story 1.29"""

from app.services.generators.native_test_generator import (
    GeneratedTestCase,
    NativeTestGenerator,
    TestFramework,
    TestSuite,
    TestType,
    get_native_test_generator,
)


class TestTestFramework:
    """Test TestFramework enum."""

    def test_framework_values(self):
        """Test all framework values exist."""
        assert TestFramework.PYTEST == "pytest"
        assert TestFramework.JUNIT == "junit"
        assert TestFramework.NUNIT == "nunit"
        assert TestFramework.MOCHA == "mocha"
        assert TestFramework.JEST == "jest"
        assert TestFramework.SELENIUM == "selenium"
        assert TestFramework.PLAYWRIGHT == "playwright"
        assert TestFramework.PHPUNIT == "phpunit"  # Story 1.55 (FR24/FR12)
        assert TestFramework.PEST == "pest"  # Story 1.55 (FR24/FR12)
        assert TestFramework.APPIUM == "appium"  # Story 1.56 (AC3)


E2E_FUNC = {
    "name": "book_flight",
    "parameters": [],
    "return_type": "",
    "class_name": None,
}


class TestE2eFrameworkRendering:
    """Story 1.56 (AC3) — natywny generator renderuje kod E2E dla wyboru użytkownika."""

    def test_render_function_test_selenium(self):
        gen = NativeTestGenerator()
        code = gen._render_function_test(E2E_FUNC, "success", TestFramework.SELENIUM)
        assert "from selenium import webdriver" in code
        assert "def test_book_flight_success" in code
        assert "driver.quit()" in code

    def test_render_function_test_playwright(self):
        gen = NativeTestGenerator()
        code = gen._render_function_test(E2E_FUNC, "success", TestFramework.PLAYWRIGHT)
        assert "@playwright/test" in code
        assert "test(" in code

    def test_render_function_test_appium(self):
        gen = NativeTestGenerator()
        code = gen._render_function_test(E2E_FUNC, "success", TestFramework.APPIUM)
        assert "from appium import webdriver" in code
        assert "AppiumBy" in code

    def test_render_endpoint_test_selenium(self):
        gen = NativeTestGenerator()
        endpoint = {"path": "/api/flights", "http_method": "GET", "name": "list_flights"}
        code = gen._render_endpoint_test(endpoint, "success", TestFramework.SELENIUM)
        assert "from selenium import webdriver" in code
        assert "/api/flights" in code

    def test_render_endpoint_test_playwright(self):
        gen = NativeTestGenerator()
        endpoint = {"path": "/api/flights", "http_method": "GET", "name": "list_flights"}
        code = gen._render_endpoint_test(endpoint, "success", TestFramework.PLAYWRIGHT)
        assert "@playwright/test" in code
        assert "/api/flights" in code

    def test_render_endpoint_test_appium(self):
        gen = NativeTestGenerator()
        endpoint = {"path": "/api/flights", "http_method": "GET", "name": "list_flights"}
        code = gen._render_endpoint_test(endpoint, "success", TestFramework.APPIUM)
        assert "from appium import webdriver" in code
        assert "UiAutomator2" in code


PHP_ANALYSIS_RESULT = {
    "language": "php",
    "source_files": ["app/Calculator.php", "app/Services/UserService.php"],
    "logic_structures": {
        "functions": [
            {
                "name": "add",
                "class_name": "Calculator",
                "parameters": [
                    {"name": "a", "type": "int"},
                    {"name": "b", "type": "int"},
                ],
                "return_type": "int",
                "docstring": "Dodaje dwie liczby.",
                "file_path": "app/Calculator.php",
            },
            {
                "name": "divide",
                "class_name": "Calculator",
                "parameters": [
                    {"name": "a", "type": "int"},
                    {"name": "b", "type": "int"},
                ],
                "return_type": "float",
                "docstring": "Dzieli a przez b.",
                "file_path": "app/Calculator.php",
            },
        ]
    },
    "entry_points": {"endpoints": []},
}


class TestPhpFrameworkRendering:
    """Story 1.55 — natywny generator renderuje kod PHP (PHPUnit + Pest)."""

    def test_generate_tests_phpunit_produces_php_class(self):
        gen = NativeTestGenerator()
        suite = gen.generate_tests(PHP_ANALYSIS_RESULT, framework=TestFramework.PHPUNIT, test_type=TestType.POSITIVE)
        assert suite.framework == TestFramework.PHPUNIT
        assert len(suite.test_cases) > 0
        code = suite.test_cases[0].code
        assert "<?php" in code
        assert "use PHPUnit\\Framework\\TestCase;" in code
        assert "extends TestCase" in code
        assert "public function test" in code
        assert "$this->assert" in code

    def test_generate_tests_pest_produces_dsl(self):
        gen = NativeTestGenerator()
        suite = gen.generate_tests(PHP_ANALYSIS_RESULT, framework=TestFramework.PEST, test_type=TestType.POSITIVE)
        assert suite.framework == TestFramework.PEST
        code = suite.test_cases[0].code
        assert "<?php" in code
        assert "it(" in code
        assert "expect(" in code

    def test_render_function_test_phpunit_style(self):
        gen = NativeTestGenerator()
        func = {
            "name": "add",
            "class_name": "Calculator",
            "parameters": [
                {"name": "a", "type": "int"},
                {"name": "b", "type": "int"},
            ],
            "return_type": "int",
        }
        code = gen._render_function_test(func, "success", TestFramework.PHPUNIT)
        assert "<?php" in code
        assert "final class CalculatorTest extends TestCase" in code
        assert "$calculator = new Calculator();" in code
        assert "$result = $calculator->add(42, 42);" in code
        assert "$this->assertNotNull($result);" in code

    def test_render_function_test_pest_style(self):
        gen = NativeTestGenerator()
        func = {
            "name": "divide",
            "class_name": "Calculator",
            "parameters": [
                {"name": "a", "type": "int"},
                {"name": "b", "type": "int"},
            ],
            "return_type": "float",
        }
        code = gen._render_function_test(func, "success", TestFramework.PEST)
        assert "<?php" in code
        assert "it(" in code
        assert "$calculator = new Calculator();" in code
        assert "$result = $calculator->divide(42, 42);" in code
        assert "expect($result)->not->toBeNull();" in code

    def test_php_sample_values_are_php_literals(self):
        """Wartości próbek dla PHP: true/null/42 — nie Pythonowe True/None."""
        gen = NativeTestGenerator()
        func = {
            "name": "setFlag",
            "parameters": [
                {"name": "flag", "type": "bool"},
                {"name": "name", "type": "str"},
                {"name": "parent", "type": "none"},
            ],
            "return_type": "bool",
        }
        code = gen._render_function_test(func, "success", TestFramework.PHPUNIT)
        assert "setFlag(true, 'test_value', null)" in code


class TestTestType:
    """Test TestType enum."""

    def test_type_values(self):
        """Test all test type values exist."""
        assert TestType.POSITIVE == "positive"
        assert TestType.NEGATIVE == "negative"
        assert TestType.BOUNDARY == "boundary"
        assert TestType.UNIT == "unit"
        assert TestType.INTEGRATION == "integration"
        assert TestType.E2E == "e2e"


class TestGeneratedTestCase:
    """Test GeneratedTestCase dataclass."""

    def test_test_case_creation(self):
        """Test creating a generated test case."""
        test_case = GeneratedTestCase(
            name="test_create_user_success",
            description="Test user creation - success case",
            test_type=TestType.POSITIVE,
            framework=TestFramework.PYTEST,
            language="python",
            code="def test_create_user_success():\n    pass",
            source_file="app/services/user.py",
            source_function="create_user",
            test_data={"username": "test", "email": "test@example.com"},
        )

        assert test_case.name == "test_create_user_success"
        assert test_case.test_type == TestType.POSITIVE
        assert test_case.framework == TestFramework.PYTEST
        assert test_case.source_function == "create_user"
        assert test_case.test_data is not None


class TestTestSuite:
    """Test TestSuite dataclass."""

    def test_suite_creation(self):
        """Test creating a test suite."""
        suite = TestSuite(
            name="python_tests",
            framework=TestFramework.PYTEST,
            language="python",
            source_files=["app/services/user.py", "app/services/auth.py"],
        )

        assert suite.name == "python_tests"
        assert suite.framework == TestFramework.PYTEST
        assert len(suite.source_files) == 2
        assert len(suite.test_cases) == 0

    def test_suite_statistics(self):
        """Test test suite statistics calculation."""
        suite = TestSuite(
            name="python_tests",
            framework=TestFramework.PYTEST,
            language="python",
        )

        suite.test_cases = [
            GeneratedTestCase(
                name="test_1",
                description="Test 1",
                test_type=TestType.POSITIVE,
                framework=TestFramework.PYTEST,
                language="python",
                code="pass",
                source_file="test.py",
            ),
            GeneratedTestCase(
                name="test_2",
                description="Test 2",
                test_type=TestType.NEGATIVE,
                framework=TestFramework.PYTEST,
                language="python",
                code="pass",
                source_file="test.py",
            ),
            GeneratedTestCase(
                name="test_3",
                description="Test 3",
                test_type=TestType.POSITIVE,
                framework=TestFramework.PYTEST,
                language="python",
                code="pass",
                source_file="test.py",
            ),
        ]

        stats = suite.get_statistics()

        assert stats["total_tests"] == 3
        assert stats["test_types"][TestType.POSITIVE] == 2
        assert stats["test_types"][TestType.NEGATIVE] == 1
        assert stats["source_files_count"] == 0  # source_files is suite-level, not per-test-case

    def test_suite_to_dict(self):
        """Test test suite serialization to dict."""
        suite = TestSuite(
            name="python_tests",
            framework=TestFramework.PYTEST,
            language="python",
            source_files=["test.py"],
        )

        suite.test_cases = [
            GeneratedTestCase(
                name="test_example",
                description="Example test",
                test_type=TestType.POSITIVE,
                framework=TestFramework.PYTEST,
                language="python",
                code="def test(): pass",
                source_file="test.py",
                source_function="example",
            ),
        ]

        data = suite.to_dict()

        assert data["name"] == "python_tests"
        assert data["framework"] == TestFramework.PYTEST
        assert len(data["test_cases"]) == 1
        assert data["statistics"]["total_tests"] == 1


class TestNativeTestGenerator:
    """Test native test generator."""

    def test_generator_initialization(self):
        """Test generator can be initialized."""
        generator = NativeTestGenerator()
        assert generator.templates is not None
        assert len(generator.templates) > 0

    def test_template_loading(self):
        """Test templates are loaded correctly."""
        generator = NativeTestGenerator()

        assert TestFramework.PYTEST in generator.templates
        assert TestFramework.JUNIT in generator.templates
        assert TestFramework.MOCHA in generator.templates

    def test_generate_tests_from_analysis(self):
        """Test generating tests from analysis result."""
        generator = NativeTestGenerator()

        analysis_result = {
            "language": "python",
            "source_files": ["app/services/user.py"],
            "entry_points": {
                "endpoints": [
                    {
                        "path": "/api/users",
                        "http_method": "POST",
                        "name": "create_user",
                        "file_path": "app/api/users.py",
                    }
                ]
            },
            "logic_structures": {
                "functions": [
                    {
                        "name": "validate_email",
                        "file_path": "app/services/user.py",
                    }
                ]
            },
        }

        suite = generator.generate_tests(
            analysis_result,
            framework=TestFramework.PYTEST,
            test_type=TestType.POSITIVE,
        )

        assert suite.language == "python"
        assert suite.framework == TestFramework.PYTEST
        assert len(suite.source_files) == 1
        # Should have tests for endpoint and function
        assert len(suite.test_cases) >= 1

    def test_generate_endpoint_tests_positive(self):
        """Test generating positive endpoint tests."""
        generator = NativeTestGenerator()

        endpoint = {
            "path": "/api/users",
            "http_method": "POST",
            "name": "create_user",
            "file_path": "app/api/users.py",
        }

        test_cases = generator._generate_endpoint_tests(
            endpoint,
            framework=TestFramework.PYTEST,
            test_type=TestType.POSITIVE,
        )

        assert len(test_cases) == 1
        assert test_cases[0].test_type == TestType.POSITIVE
        assert "success" in test_cases[0].name
        assert test_cases[0].code is not None

    def test_generate_endpoint_tests_negative(self):
        """Test generating negative endpoint tests."""
        generator = NativeTestGenerator()

        endpoint = {
            "path": "/api/users",
            "http_method": "GET",
            "name": "get_user",
            "file_path": "app/api/users.py",
        }

        test_cases = generator._generate_endpoint_tests(
            endpoint,
            framework=TestFramework.PYTEST,
            test_type=TestType.NEGATIVE,
        )

        assert len(test_cases) == 1
        assert test_cases[0].test_type == TestType.NEGATIVE
        assert "not_found" in test_cases[0].name

    def test_generate_function_tests(self):
        """Test generating function tests."""
        generator = NativeTestGenerator()

        func = {
            "name": "calculate_tax",
            "file_path": "app/services/tax.py",
        }

        test_cases = generator._generate_function_tests(
            func,
            framework=TestFramework.PYTEST,
            test_type=TestType.POSITIVE,
            language="python",
        )

        assert len(test_cases) == 1
        assert test_cases[0].test_type == TestType.POSITIVE
        assert "success" in test_cases[0].name

    def test_render_endpoint_test_pytest_success(self):
        """Test rendering pytest success test for endpoint."""
        generator = NativeTestGenerator()

        endpoint = {
            "path": "/api/users",
            "http_method": "POST",
            "name": "create_user",
        }

        code = generator._render_endpoint_test(endpoint, "success", TestFramework.PYTEST)

        assert "def test_create_user_success" in code
        assert "201" in code
        assert "client" in code

    def test_render_endpoint_test_pytest_not_found(self):
        """Test rendering pytest not_found test for endpoint."""
        generator = NativeTestGenerator()

        endpoint = {
            "path": "/api/users/{id}",
            "http_method": "GET",
            "name": "get_user",
        }

        code = generator._render_endpoint_test(endpoint, "not_found", TestFramework.PYTEST)

        assert "def test_get_user_not_found" in code
        assert "404" in code

    def test_render_function_test(self):
        """Test rendering function test."""
        generator = NativeTestGenerator()

        func = {
            "name": "calculate_tax",
        }

        code = generator._render_function_test(func, "success", TestFramework.PYTEST)

        assert "calculate_tax" in code
        assert "success" in code

    def test_generate_tests_with_no_data(self):
        """Test generating tests with empty analysis result."""
        generator = NativeTestGenerator()

        analysis_result = {
            "language": "python",
            "source_files": [],
            "entry_points": {"endpoints": []},
            "logic_structures": {"functions": []},
        }

        suite = generator.generate_tests(
            analysis_result,
            framework=TestFramework.PYTEST,
            test_type=TestType.POSITIVE,
        )

        # Should still create suite, just no tests
        assert suite is not None
        assert suite.language == "python"
        assert len(suite.test_cases) == 0

    def test_generate_tests_framework_junit(self):
        """Test generating JUnit tests."""
        generator = NativeTestGenerator()

        endpoint = {
            "path": "/api/users",
            "http_method": "POST",
            "name": "createUser",
            "file_path": "app/api/UsersController.java",
        }

        test_cases = generator._generate_endpoint_tests(
            endpoint,
            framework=TestFramework.JUNIT,
            test_type=TestType.POSITIVE,
        )

        assert len(test_cases) == 1
        assert test_cases[0].framework == TestFramework.JUNIT

    def test_generate_tests_framework_mocha(self):
        """Test generating Mocha tests."""
        generator = NativeTestGenerator()

        endpoint = {
            "path": "/api/users",
            "http_method": "POST",
            "name": "createUser",
            "file_path": "app/api/users.ts",
        }

        test_cases = generator._generate_endpoint_tests(
            endpoint,
            framework=TestFramework.MOCHA,
            test_type=TestType.POSITIVE,
        )

        assert len(test_cases) == 1
        assert test_cases[0].framework == TestFramework.MOCHA


def test_get_native_test_generator():
    """Test getting native test generator instance."""
    generator = get_native_test_generator()
    assert isinstance(generator, NativeTestGenerator)
