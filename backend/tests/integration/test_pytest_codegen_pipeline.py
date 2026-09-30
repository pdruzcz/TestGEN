"""Integration tests for PytestCodeGenerator — Story 1.36, Task 8.

8.1 Golden data: 5+ probek kodu Python z znanymi wynikami pytest
8.2 Integration: generowanie pytest kodu z golden data -> kompilacja -> porownanie
8.3 Metryka: >80% wygenerowanych plikow kompiluje sie pomyslnie (native path)
"""

import py_compile
from pathlib import Path

import pytest

from app.services.test_generation.codegen.base import CodeGenRegistry
from app.services.test_generation.codegen.pytest_generator import PytestCodeGenerator

GOLDEN_DATA_DIR = Path(__file__).resolve().parent.parent / "golden_data" / "code_samples" / "python"


# ── Golden data — definicje test case'ow dla kazdego modulu ──────────────────


CALCULATOR_TEST_CASES = [
    {
        "title": "Dodawanie dwoch liczb dodatnich",
        "scenario_name": "Dodawanie liczb dodatnich",
        "description": "Sprawdza czy Calculator.add poprawnie dodaje liczby.",
        "test_type": "unit",
        "source_file": "app/calculator.py",
        "source_class": "Calculator",
        "source_function": "add",
        "setup_code": "calc = Calculator()",
        "teardown_code": "calc.reset()",
        "test_data": {
            "sets": [
                {"a": 1, "b": 2, "expected": 3},
                {"a": 10, "b": 20, "expected": 30},
                {"a": -1, "b": 1, "expected": 0},
            ]
        },
        "expected_result": "expected",
        "comparison_type": "equals",
    },
    {
        "title": "Dzielenie przez zero",
        "scenario_name": "Dzielenie przez zero rzuca wyjatek",
        "description": "Sprawdza czy Calculator.divide rzuca ZeroDivisionError.",
        "test_type": "unit",
        "source_file": "app/calculator.py",
        "source_class": "Calculator",
        "source_function": "divide",
        "setup_code": "calc = Calculator()",
        "expected_result": "ZeroDivisionError",
        "comparison_type": "throws",
    },
    {
        "title": "Mnozenie liczb ujemnych",
        "scenario_name": "Mnozenie ujemnych",
        "description": "Sprawdza czy Calculator.multiply poprawnie mnozy.",
        "test_type": "unit",
        "source_file": "app/calculator.py",
        "source_class": "Calculator",
        "source_function": "multiply",
        "setup_code": "calc = Calculator()",
        "test_data": {
            "sets": [
                {"a": -2, "b": -3, "expected": 6},
                {"a": -1, "b": 5, "expected": -5},
            ]
        },
        "expected_result": "expected",
        "comparison_type": "equals",
    },
]

USER_SERVICE_TEST_CASES = [
    {
        "title": "Tworzenie uzytkownika",
        "scenario_name": "Utworz poprawnego uzytkownika",
        "description": "Sprawdza czy UserService.create_user tworzy usera.",
        "test_type": "unit",
        "source_file": "app/user_service.py",
        "source_class": "UserService",
        "source_function": "create_user",
        "setup_code": "svc = UserService()",
        "test_data": {
            "sets": [
                {"username": "alice", "email": "alice@test.com"},
                {"username": "bob", "email": "bob@test.com"},
            ]
        },
        "expected_result": "True",
        "comparison_type": "is_not_none",
    },
    {
        "title": "Tworzenie z krotka nazwa",
        "scenario_name": "Krótka nazwa uzytkownika",
        "description": "Sprawdza czy create_user rzuca ValueError dla krotkiej nazwy.",
        "test_type": "unit",
        "source_file": "app/user_service.py",
        "source_class": "UserService",
        "source_function": "create_user",
        "setup_code": "svc = UserService()",
        "expected_result": "ValueError",
        "comparison_type": "throws",
    },
    {
        "title": "Deaktywacja uzytkownika",
        "scenario_name": "Deaktywuj istniejacego usera",
        "description": "Sprawdza czy deactivate_user zwraca True.",
        "test_type": "unit",
        "source_file": "app/user_service.py",
        "source_class": "UserService",
        "source_function": "deactivate_user",
        "setup_code": "svc = UserService()\nsvc.create_user('test', 'test@test.com')",
        "expected_result": "True",
        "comparison_type": "is_true",
    },
]

DATA_PROCESSOR_TEST_CASES = [
    {
        "title": "Filtrowanie liczb dodatnich",
        "scenario_name": "Filtruj dodatnie",
        "description": "Sprawdza czy filter_positive zwraca tylko liczby > 0.",
        "test_type": "unit",
        "source_file": "app/data_processor.py",
        "source_class": "DataProcessor",
        "source_function": "filter_positive",
        "setup_code": "proc = DataProcessor()",
        "test_data": {
            "sets": [
                {"input": [1, -2, 3, -4, 5], "expected": [1, 3, 5]},
                {"input": [-1, -2, -3], "expected": []},
                {"input": [0, 1, 2], "expected": [1, 2]},
            ]
        },
        "expected_result": "expected",
        "comparison_type": "equals",
    },
    {
        "title": "Srednia z pustej listy",
        "scenario_name": "Srednia pusta lista",
        "description": "Sprawdza czy calculate_average rzuca ValueError.",
        "test_type": "unit",
        "source_file": "app/data_processor.py",
        "source_class": "DataProcessor",
        "source_function": "calculate_average",
        "setup_code": "proc = DataProcessor()",
        "expected_result": "ValueError",
        "comparison_type": "throws",
    },
]

AUTH_HANDLER_TEST_CASES = [
    {
        "title": "Hashowanie hasla",
        "scenario_name": "Hash poprawnego hasla",
        "description": "Sprawdza czy hash_password zwraca hash z sola.",
        "test_type": "unit",
        "source_file": "app/auth_handler.py",
        "source_class": "AuthHandler",
        "source_function": "hash_password",
        "setup_code": "handler = AuthHandler()",
        "expected_result": "True",
        "comparison_type": "is_not_none",
    },
    {
        "title": "Haslo za krotkie",
        "scenario_name": "Krotkie haslo rzuca wyjatek",
        "description": "Sprawdza czy hash_password rzuca ValueError.",
        "test_type": "unit",
        "source_file": "app/auth_handler.py",
        "source_class": "AuthHandler",
        "source_function": "hash_password",
        "setup_code": "handler = AuthHandler()",
        "expected_result": "ValueError",
        "comparison_type": "throws",
    },
    {
        "title": "Sesja uzytkownika",
        "scenario_name": "Utworz i zweryfikuj sesje",
        "description": "Sprawdza czy create_session i validate_session dzialaja.",
        "test_type": "unit",
        "source_file": "app/auth_handler.py",
        "source_class": "AuthHandler",
        "source_function": "create_session",
        "setup_code": "handler = AuthHandler()",
        "expected_result": "testuser",
        "comparison_type": "equals",
    },
]

FILE_MANAGER_TEST_CASES = [
    {
        "title": "Zapis i odczyt pliku",
        "scenario_name": "Zapisz i odczytaj",
        "description": "Sprawdza czy write_file i read_file dzialaja.",
        "test_type": "unit",
        "source_file": "app/file_manager.py",
        "source_class": "FileManager",
        "source_function": "write_file",
        "setup_code": "fm = FileManager(base_dir='/tmp/testgen_test')",
        "teardown_code": "import shutil; shutil.rmtree('/tmp/testgen_test', ignore_errors=True)",
        "expected_result": "'hello world'",
        "comparison_type": "equals",
    },
    {
        "title": "Odczyt nieistniejacego pliku",
        "scenario_name": "Nieistniejacy plik rzuca wyjatek",
        "description": "Sprawdza czy read_file rzuca FileNotFoundError.",
        "test_type": "unit",
        "source_file": "app/file_manager.py",
        "source_class": "FileManager",
        "source_function": "read_file",
        "setup_code": "fm = FileManager(base_dir='/tmp/testgen_test')",
        "expected_result": "FileNotFoundError",
        "comparison_type": "throws",
    },
]

# ── Wszystkie golden data zestawy ──

GOLDEN_DATA_SUITES = [
    ("calculator", CALCULATOR_TEST_CASES),
    ("user_service", USER_SERVICE_TEST_CASES),
    ("data_processor", DATA_PROCESSOR_TEST_CASES),
    ("auth_handler", AUTH_HANDLER_TEST_CASES),
    ("file_manager", FILE_MANAGER_TEST_CASES),
]


# ── Testy integracyjne ────────────────────────────────────────────────────────


class TestGoldenDataPipeline:
    """8.2 Integration: golden data → generowanie → kompilacja → porownanie."""

    @pytest.mark.parametrize(
        "suite_name,test_cases",
        GOLDEN_DATA_SUITES,
        ids=[s[0] for s in GOLDEN_DATA_SUITES],
    )
    def test_golden_suite_compiles(self, suite_name, test_cases):
        """Kazdy golden data suite generuje kod ktory sie kompiluje."""
        gen = PytestCodeGenerator()
        result = gen.generate_test_file(test_cases)

        assert result.compilation_result is not None, f"{suite_name}: brak wyniku kompilacji"
        assert result.compilation_result.success, (
            f"{suite_name}: kompilacja nie powiodla sie: {result.compilation_result.error_message}"
        )
        assert "import pytest" in result.content
        assert len(result.test_functions) == len(test_cases)

    def test_all_golden_data_files_exist(self):
        """8.1 — Wszystkie pliki golden data istnieja."""
        expected_files = [
            "calculator.py",
            "user_service.py",
            "data_processor.py",
            "auth_handler.py",
            "file_manager.py",
        ]
        for filename in expected_files:
            filepath = GOLDEN_DATA_DIR / filename
            assert filepath.exists(), f"Brak pliku golden data: {filepath}"

    def test_compilation_rate_above_threshold(self):
        """8.3 — Metryka: >80% wygenerowanych plikow kompiluje sie (native path)."""
        gen = PytestCodeGenerator()
        total = 0
        success = 0

        for _suite_name, test_cases in GOLDEN_DATA_SUITES:
            result = gen.generate_test_file(test_cases)
            total += 1
            if result.compilation_result and result.compilation_result.success:
                success += 1

        rate = success / total * 100 if total > 0 else 0
        assert rate >= 80, f"Compilation rate: {rate:.1f}% ({success}/{total}) — below 80% threshold"

    def test_conftest_compiles_with_project_context(self):
        """conftest.py z pelnym kontekstem projektu sie kompiluje."""
        gen = PytestCodeGenerator()
        ctx = {
            "project_name": "testgen",
            "dependencies": ["database", "api", "http"],
        }
        content = gen.generate_setup(ctx)
        assert "import pytest" in content

        # Walidacja py_compile
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            py_compile.compile(f.name, doraise=True)

    def test_registry_routes_pytest_correctly(self):
        """CodeGenRegistry poprawnie route'uje do PytestCodeGenerator."""
        registry = CodeGenRegistry.get_instance()
        gen = registry.get_generator("pytest")
        assert isinstance(gen, PytestCodeGenerator)

        result = gen.generate_test_file(CALCULATOR_TEST_CASES)
        assert result.framework == "pytest"
        assert result.language == "python"
        assert result.compilation_result.success

    def test_total_test_functions_generated(self):
        """Sumarycznie generuje sie odpowiednia liczba funkcji testowych."""
        gen = PytestCodeGenerator()
        total_functions = 0
        for _suite_name, test_cases in GOLDEN_DATA_SUITES:
            result = gen.generate_test_file(test_cases)
            total_functions += len(result.test_functions)

        # 5 suites, lacznie wszystkie test cases
        total_cases = sum(len(tc) for _, tc in GOLDEN_DATA_SUITES)
        assert total_functions == total_cases, f" Wygenerowano {total_functions} funkcji, oczekiwano {total_cases}"
