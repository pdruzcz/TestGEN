"""Integration tests for JUnit code generation pipeline — Story 1.37.

Testy integracyjne uzywajace golden data — 5 probek kodu Java
z generowaniem JUnit i walidacja skladni.

8.1  Golden data: 5+ probek kodu Java
8.2  Integration test: generowanie JUnit z golden data -> walidacja skladni
8.3  Metryka: >80% wygenerowanych plikow przechodzi walidacje (native path)
"""

from pathlib import Path

import pytest

from app.services.test_generation.codegen.base import (
    CodeGenConfig,
    CodeGenRegistry,
    TestCodeFile,
)
from app.services.test_generation.codegen.junit_generator import JUnitCodeGenerator

GOLDEN_DATA_DIR = Path(__file__).resolve().parent.parent / "golden_data" / "code_samples" / "java"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def generator() -> JUnitCodeGenerator:
    """JUnitCodeGenerator z wlaczona walidacja."""
    config = CodeGenConfig(
        framework="junit",
        language="java",
        validate_compilation=True,
    )
    return JUnitCodeGenerator(config=config)


@pytest.fixture
def registry() -> CodeGenRegistry:
    """CodeGenRegistry singleton."""
    return CodeGenRegistry.get_instance()


# ── Golden data test cases — mapowanie plik Java -> test case ────────────────

GOLDEN_TEST_CASES = {
    "Calculator": [
        {
            "title": "Dodawanie dwoch liczb",
            "scenario_name": "should return correct sum when adding two positive numbers",
            "description": "Sprawdza czy add(2,3) zwroci 5.",
            "test_type": "unit",
            "source_file": "src/main/java/com/example/Calculator.java",
            "source_class": "Calculator",
            "source_function": "add",
            "setup_code": "Calculator calc = new Calculator();",
            "teardown_code": "calc.reset();",
            "expected_result": "5",
            "comparison_type": "equals",
        },
        {
            "title": "Dzielenie przez zero",
            "scenario_name": "should throw ArithmeticException when dividing by zero",
            "description": "Sprawdza wyjatek dzielenia przez zero.",
            "test_type": "unit",
            "source_file": "src/main/java/com/example/Calculator.java",
            "source_class": "Calculator",
            "source_function": "divide",
            "setup_code": "Calculator calc = new Calculator();",
            "expected_result": "ArithmeticException",
            "comparison_type": "throws",
        },
        {
            "title": "Parametryzowane mnozenie",
            "scenario_name": "should multiply correctly for various inputs",
            "description": "Sprawdza mnozenie z roznymi danymi.",
            "test_type": "unit",
            "source_file": "src/main/java/com/example/Calculator.java",
            "source_class": "Calculator",
            "test_data": {
                "sets": [
                    {"a": 2, "b": 3, "expected": 6},
                    {"a": 0, "b": 5, "expected": 0},
                    {"a": -1, "b": 4, "expected": -4},
                ]
            },
            "expected_result": "expected",
            "comparison_type": "equals",
        },
    ],
    "UserService": [
        {
            "title": "Pobranie uzytkownika po ID",
            "scenario_name": "should return user when valid id provided",
            "description": "Test pobierania uzytkownika.",
            "test_type": "integration",
            "source_file": "src/main/java/com/example/service/UserService.java",
            "source_class": "UserService",
            "source_function": "getUserById",
            "dependencies": [
                {
                    "target": "com.example.repository.UserRepository",
                    "method": "findById",
                    "return_value": 'new User("Jan", "jan@test.pl")',
                },
            ],
            "expected_result": "jan",
            "comparison_type": "is_not_none",
        },
        {
            "title": "Nieprawidlowe ID",
            "scenario_name": "should throw IllegalArgumentException when id is null",
            "description": "Walidacja argumentu.",
            "test_type": "unit",
            "source_file": "src/main/java/com/example/service/UserService.java",
            "source_class": "UserService",
            "expected_result": "IllegalArgumentException",
            "comparison_type": "throws",
        },
    ],
    "DataProcessor": [
        {
            "title": "Suma liczb",
            "scenario_name": "should return correct sum for list of integers",
            "description": "Test sumowania.",
            "test_type": "unit",
            "source_file": "src/main/java/com/example/processor/DataProcessor.java",
            "source_class": "DataProcessor",
            "test_data": {
                "sets": [
                    {"input": "List.of(1, 2, 3)", "expected": 6},
                    {"input": "List.of(10)", "expected": 10},
                ]
            },
            "expected_result": "expected",
            "comparison_type": "equals",
        },
        {
            "title": "Null lista",
            "scenario_name": "should throw when null list provided",
            "description": "Walidacja null.",
            "test_type": "unit",
            "source_file": "src/main/java/com/example/processor/DataProcessor.java",
            "source_class": "DataProcessor",
            "expected_result": "IllegalArgumentException",
            "comparison_type": "throws",
        },
    ],
    "AuthHandler": [
        {
            "title": "Autoryzacja poprawna",
            "scenario_name": "should return token when valid credentials",
            "description": "Test logowania.",
            "test_type": "integration",
            "source_file": "src/main/java/com/example/auth/AuthHandler.java",
            "source_class": "AuthHandler",
            "dependencies": [
                {
                    "target": "com.example.service.TokenService",
                    "method": "validateCredentials",
                    "return_value": "true",
                },
                {
                    "target": "com.example.repository.SessionRepository",
                    "method": "saveSession",
                    "return_value": "null",
                },
            ],
            "expected_result": "token",
            "comparison_type": "is_not_none",
        },
        {
            "title": "Null credentials",
            "scenario_name": "should throw when null credentials",
            "description": "Walidacja credentials.",
            "test_type": "unit",
            "source_file": "src/main/java/com/example/auth/AuthHandler.java",
            "source_class": "AuthHandler",
            "expected_result": "IllegalArgumentException",
            "comparison_type": "throws",
        },
    ],
    "OrderService": [
        {
            "title": "Tworzenie zamowienia",
            "scenario_name": "should create order and process payment",
            "description": "Test pelnego przeplywu.",
            "test_type": "integration",
            "source_file": "src/main/java/com/example/order/OrderService.java",
            "source_class": "OrderService",
            "dependencies": [
                {
                    "target": "com.example.repository.OrderRepository",
                    "method": "save",
                    "return_value": "order",
                },
                {
                    "target": "com.example.service.PaymentService",
                    "method": "processPayment",
                    "return_value": "true",
                },
                {
                    "target": "com.example.service.NotificationService",
                    "method": "sendConfirmation",
                    "return_value": "null",
                },
            ],
            "expected_result": "order",
            "comparison_type": "is_not_none",
        },
        {
            "title": "Puste zamowienie",
            "scenario_name": "should throw when empty items list",
            "description": "Walidacja items.",
            "test_type": "unit",
            "source_file": "src/main/java/com/example/order/OrderService.java",
            "source_class": "OrderService",
            "expected_result": "IllegalArgumentException",
            "comparison_type": "throws",
        },
    ],
}


# ── 8.2 Integration test: generowanie JUnit z golden data ────────────────────


class TestGoldenDataGeneration:
    """8.2 Integration test: golden data -> JUnit generowanie -> walidacja."""

    @pytest.mark.parametrize(
        "class_name",
        list(GOLDEN_TEST_CASES.keys()),
    )
    def test_generates_valid_junit_for_golden_data(self, generator, class_name):
        """Kazda probka golden data generuje poprawny JUnit kod."""
        test_cases = GOLDEN_TEST_CASES[class_name]
        result = generator.generate_test_file(test_cases)

        assert isinstance(result, TestCodeFile)
        assert result.framework == "junit"
        assert result.language == "java"
        assert len(result.test_functions) == len(test_cases)
        assert result.compilation_result is not None
        assert result.compilation_result.success, (
            f"[{class_name}] Walidacja nie powiodla sie: {result.compilation_result.error_message}"
        )

        # Sprawdz strukture JUnit
        assert "package " in result.content
        assert "import org.junit.jupiter.api.Test" in result.content
        assert "public class" in result.content
        assert "@Test" in result.content

    def test_calculator_golden_data_has_parameterized(self, generator):
        """Calculator golden data generuje @ParameterizedTest."""
        test_cases = GOLDEN_TEST_CASES["Calculator"]
        result = generator.generate_test_file(test_cases)
        assert "@ParameterizedTest" in result.content
        assert "@CsvSource" in result.content

    def test_calculator_golden_data_has_lifecycle(self, generator):
        """Calculator golden data generuje @BeforeEach / @AfterEach."""
        test_cases = GOLDEN_TEST_CASES["Calculator"]
        result = generator.generate_test_file(test_cases)
        assert "@BeforeEach" in result.content
        assert "@AfterEach" in result.content

    def test_userservice_golden_data_has_mocks(self, generator):
        """UserService golden data generuje @Mock / @InjectMocks."""
        test_cases = GOLDEN_TEST_CASES["UserService"]
        result = generator.generate_test_file(test_cases)
        assert "@Mock" in result.content
        assert "@InjectMocks" in result.content
        assert "when(" in result.content

    def test_authhandler_golden_data_has_multiple_mocks(self, generator):
        """AuthHandler golden data generuje wiele mockow."""
        test_cases = GOLDEN_TEST_CASES["AuthHandler"]
        result = generator.generate_test_file(test_cases)
        content = result.content
        assert content.count("@Mock") >= 2  # TokenService + SessionRepository

    def test_orderservice_golden_data_has_three_mocks(self, generator):
        """OrderService golden data generuje 3 mocki."""
        test_cases = GOLDEN_TEST_CASES["OrderService"]
        result = generator.generate_test_file(test_cases)
        content = result.content
        assert content.count("@Mock") >= 3

    def test_dataprocessor_golden_data_has_method_source(self, generator):
        """DataProcessor golden data generuje @MethodSource dla zlozonych typow."""
        test_cases = GOLDEN_TEST_CASES["DataProcessor"]
        result = generator.generate_test_file(test_cases)
        assert "@ParameterizedTest" in result.content


# ── 8.3 Metryka: >80% plikow kompiluje sie (native path) ────────────────────


class TestCompilationMetric:
    """8.3 Metryka: >80% wygenerowanych plikow przechodzi walidacje."""

    def test_compilation_success_rate_above_80_percent(self, generator):
        """Wszystkie golden data probki osiagaja >80% walidacji."""
        total = 0
        passed = 0

        for _class_name, test_cases in GOLDEN_TEST_CASES.items():
            result = generator.generate_test_file(test_cases)
            total += 1
            if result.compilation_result and result.compilation_result.success:
                passed += 1

        success_rate = passed / total * 100
        assert success_rate >= 80, f"Compilation rate: {success_rate:.0f}% ({passed}/{total}) — target >80%"

    def test_all_golden_data_files_exist(self):
        """Kazdy plik golden data istnieje na dysku."""
        for class_name in GOLDEN_TEST_CASES:
            file_path = GOLDEN_DATA_DIR / f"{class_name}.java"
            assert file_path.exists(), f"Brak pliku golden data: {file_path}"


# ── Registry integration ─────────────────────────────────────────────────────


class TestRegistryIntegration:
    """Test integracji z CodeGenRegistry."""

    def test_registry_supports_junit(self, registry):
        """Registry obsluguje junit."""
        assert registry.is_supported("junit")

    def test_registry_returns_junit_generator(self, registry):
        """Registry zwraca JUnitCodeGenerator dla junit."""
        config = CodeGenConfig(framework="junit", language="java")
        gen = registry.get_generator("junit", config=config)
        assert isinstance(gen, JUnitCodeGenerator)
        assert gen.FRAMEWORK == "junit"
        assert gen.LANGUAGE == "java"

    def test_pipeline_full_flow(self, generator):
        """Symulacja pelnego przeplywu: test cases -> JUnit -> file -> walidacja."""
        test_cases = GOLDEN_TEST_CASES["Calculator"]

        # Generuj
        result = generator.generate_test_file(test_cases)
        assert isinstance(result, TestCodeFile)

        # Sprawdz zawartosc
        assert result.content is not None
        assert len(result.content) > 100
        assert "CalculatorTest" in result.content

        # Waliduj strukturalnie
        assert result.compilation_result is not None
        assert result.compilation_result.success

        # Sprawdz to_dict
        d = result.to_dict()
        assert d["framework"] == "junit"
        assert d["language"] == "java"
        assert d["num_test_functions"] == len(test_cases)
