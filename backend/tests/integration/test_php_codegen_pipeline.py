"""Integration tests for PHPUnit/Pest code generators — Story 1.55 (FR24/FR12).

Wzorzec Stories 1.36-1.42 (mirror ``test_pytest_codegen_pipeline.py``):
golden data PHP → generacja (phpunit + pest) → walidacja składni → metryka
>80% plików przechodzi walidację (native path).
"""

from __future__ import annotations

from pathlib import Path

from app.services.test_generation.codegen import CodeGenRegistry
from app.services.test_generation.codegen.phpunit_generator import (
    PestCodeGenerator,
    PhpUnitCodeGenerator,
)

GOLDEN_DATA_DIR = Path(__file__).resolve().parent.parent / "golden_data" / "code_samples" / "php"

# ── Golden data — PHP test case'y (mirror pytest golden suites) ──────────────

CALCULATOR_TEST_CASES = [
    {
        "title": "Dodawanie dwóch liczb dodatnich",
        "scenario_name": "Dodawanie liczb dodatnich",
        "description": "Sprawdza czy Calculator::add poprawnie dodaje liczby.",
        "test_type": "unit",
        "source_file": "app/Calculator.php",
        "source_class": "Calculator",
        "source_function": "add",
        "test_data": {"sets": [{"a": 1, "b": 2, "expected": 3}]},
        "expected_result": "3",
        "comparison_type": "equals",
    },
    {
        "title": "Dzielenie przez zero",
        "scenario_name": "Dzielenie przez zero rzuca wyjątek",
        "description": "Sprawdza czy Calculator::divide rzuca InvalidArgumentException.",
        "test_type": "unit",
        "source_file": "app/Calculator.php",
        "source_class": "Calculator",
        "source_function": "divide",
        "test_data": {"sets": [{"a": 1, "b": 0}]},
        "expected_result": "InvalidArgumentException",
        "comparison_type": "throws",
    },
    {
        "title": "Mnożenie liczb ujemnych",
        "scenario_name": "Mnożenie ujemnych",
        "description": "Sprawdza czy Calculator::multiply poprawnie mnoży.",
        "test_type": "unit",
        "source_file": "app/Calculator.php",
        "source_class": "Calculator",
        "source_function": "multiply",
        "test_data": {"sets": [{"a": -2, "b": -3, "expected": 6}]},
        "expected_result": "6",
        "comparison_type": "equals",
    },
]

USER_SERVICE_TEST_CASES = [
    {
        "title": "Tworzenie użytkownika",
        "scenario_name": "Utwórz poprawnego użytkownika",
        "description": "Sprawdza czy UserService::create_user tworzy użytkownika.",
        "test_type": "unit",
        "source_file": "app/Services/UserService.php",
        "source_class": "UserService",
        "source_function": "create_user",
        "test_data": {"sets": [{"username": "alice", "email": "alice@test.com"}]},
        "expected_result": "True",
        "comparison_type": "is_not_none",
    },
    {
        "title": "Tworzenie z krótką nazwą",
        "scenario_name": "Krótka nazwa użytkownika",
        "description": "Sprawdza czy create_user rzuca InvalidArgumentException.",
        "test_type": "unit",
        "source_file": "app/Services/UserService.php",
        "source_class": "UserService",
        "source_function": "create_user",
        "test_data": {"sets": [{"username": "ab"}]},
        "expected_result": "InvalidArgumentException",
        "comparison_type": "throws",
    },
    {
        "title": "Deaktywacja użytkownika",
        "scenario_name": "Deaktywuj istniejącego użytkownika",
        "description": "Sprawdza czy deactivate_user zwraca true.",
        "test_type": "unit",
        "source_file": "app/Services/UserService.php",
        "source_class": "UserService",
        "source_function": "deactivate_user",
        "test_data": {"sets": [{"username": "alice"}]},
        "expected_result": "true",
        "comparison_type": "is_true",
    },
]

ORDER_REPOSITORY_TEST_CASES = [
    {
        "title": "Filtrowanie zamówień opłaconych",
        "scenario_name": "Filtruj opłacone",
        "description": "Sprawdza czy OrderRepository::findPaid zwraca tylko opłacone.",
        "test_type": "unit",
        "source_file": "app/Repositories/OrderRepository.php",
        "source_class": "OrderRepository",
        "source_function": "findPaid",
        "test_data": {"sets": [{"limit": 10}]},
        "expected_result": "3",
        "comparison_type": "has_length",
    },
    {
        "title": "Suma z pustej listy",
        "scenario_name": "Suma pusta lista",
        "description": "Sprawdza czy OrderRepository::total zwraca 0 dla pustej listy.",
        "test_type": "unit",
        "source_file": "app/Repositories/OrderRepository.php",
        "source_class": "OrderRepository",
        "source_function": "total",
        "test_data": {"sets": [{}]},
        "expected_result": "0",
        "comparison_type": "equals",
    },
]

INVOICE_SERVICE_TEST_CASES = [
    {
        "title": "Kwota netto faktury",
        "scenario_name": "Kwota netto",
        "description": "Sprawdza czy InvoiceService::netAmount liczy kwotę netto.",
        "test_type": "unit",
        "source_file": "app/Services/InvoiceService.php",
        "source_class": "InvoiceService",
        "source_function": "netAmount",
        "test_data": {"sets": [{"gross": 123.0, "expected": 100.0}]},
        "expected_result": "100.0",
        "comparison_type": "equals",
    },
    {
        "title": "Termin płatności w przeszłości",
        "scenario_name": "Termin w przeszłości",
        "description": "Sprawdza czy netAmount rzuca DomainException dla przeszłej daty.",
        "test_type": "unit",
        "source_file": "app/Services/InvoiceService.php",
        "source_class": "InvoiceService",
        "source_function": "netAmount",
        "test_data": {"sets": [{"gross": -1}]},
        "expected_result": "DomainException",
        "comparison_type": "throws",
    },
]

AUTH_HANDLER_TEST_CASES = [
    {
        "title": "Hashowanie hasła",
        "scenario_name": "Hash poprawnego hasła",
        "description": "Sprawdza czy AuthHandler::hashPassword zwraca hash.",
        "test_type": "unit",
        "source_file": "app/Security/AuthHandler.php",
        "source_class": "AuthHandler",
        "source_function": "hashPassword",
        "test_data": {"sets": [{"password": "s3cret"}]},
        "expected_result": "True",
        "comparison_type": "is_not_none",
    },
    {
        "title": "Hasło za krótkie",
        "scenario_name": "Krótkie hasło rzuca wyjątek",
        "description": "Sprawdza czy hashPassword rzuca InvalidArgumentException.",
        "test_type": "unit",
        "source_file": "app/Security/AuthHandler.php",
        "source_class": "AuthHandler",
        "source_function": "hashPassword",
        "test_data": {"sets": [{"password": "x"}]},
        "expected_result": "InvalidArgumentException",
        "comparison_type": "throws",
    },
]

GOLDEN_DATA_SUITES = [
    ("calculator", CALCULATOR_TEST_CASES),
    ("user_service", USER_SERVICE_TEST_CASES),
    ("order_repository", ORDER_REPOSITORY_TEST_CASES),
    ("invoice_service", INVOICE_SERVICE_TEST_CASES),
    ("auth_handler", AUTH_HANDLER_TEST_CASES),
]

GENERATORS = [
    ("phpunit", PhpUnitCodeGenerator),
    ("pest", PestCodeGenerator),
]


class TestGoldenDataPipeline:
    """Golden data PHP → generacja → walidacja składni → porównanie."""

    def test_golden_suites_generate_valid_php(self):
        for framework, gen_cls in GENERATORS:
            gen = gen_cls()
            for suite_name, test_cases in GOLDEN_DATA_SUITES:
                result = gen.generate_test_file(test_cases)
                assert result.compilation_result is not None, f"{framework}/{suite_name}: brak walidacji"
                assert result.compilation_result.success, (
                    f"{framework}/{suite_name}: {result.compilation_result.error_message}"
                )
                assert result.content.lstrip().startswith("<?php")
                assert result.language == "php"

    def test_all_golden_data_files_exist(self):
        """Wszystkie pliki golden data PHP istnieją (mirror §8.1 wzorca 1.36)."""
        expected_files = [
            "Calculator.php",
            "UserService.php",
            "OrderRepository.php",
            "InvoiceService.php",
            "AuthHandler.php",
        ]
        for filename in expected_files:
            filepath = GOLDEN_DATA_DIR / filename
            assert filepath.exists(), f"Brak pliku golden data: {filepath}"

    def test_golden_source_files_are_valid_php(self):
        """Próbki źródłowe przechodzą walidację składni (php -l lub statyczną)."""
        gen = PhpUnitCodeGenerator()
        for filepath in sorted(GOLDEN_DATA_DIR.glob("*.php")):
            code = filepath.read_text(encoding="utf-8")
            result = gen.validate_syntax(code)
            assert result.success, f"{filepath.name}: {result.error_message}"

    def test_compilation_rate_above_threshold(self):
        """>80% wygenerowanych plików przechodzi walidację (native path)."""
        total = 0
        success = 0
        for _framework, gen_cls in GENERATORS:
            gen = gen_cls()
            for _suite_name, test_cases in GOLDEN_DATA_SUITES:
                result = gen.generate_test_file(test_cases)
                total += 1
                if result.compilation_result and result.compilation_result.success:
                    success += 1

        rate = success / total * 100 if total > 0 else 0
        assert rate >= 80, f"Compilation rate: {rate:.1f}% ({success}/{total}) — below 80% threshold"

    def test_all_test_functions_generated(self):
        gen = PhpUnitCodeGenerator()
        for _suite_name, test_cases in GOLDEN_DATA_SUITES:
            result = gen.generate_test_file(test_cases)
            assert len(result.test_functions) == len(test_cases)

    def test_registry_routes_php_frameworks_correctly(self):
        registry = CodeGenRegistry.get_instance()
        for framework, gen_cls in GENERATORS:
            gen = registry.get_generator(framework)
            assert isinstance(gen, gen_cls)
            result = gen.generate_test_file(CALCULATOR_TEST_CASES)
            assert result.framework == framework
            assert result.language == "php"
            assert result.compilation_result.success

    def test_setup_files_are_valid_php(self):
        for _framework, gen_cls in GENERATORS:
            setup = gen_cls().generate_setup({"project_name": "testgen"})
            assert setup.lstrip().startswith("<?php")
            assert gen_cls().validate_syntax(setup).success
