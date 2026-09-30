"""Unit tests for PytestCodeGenerator — Story 1.36.

Coverage:
7.1  test_generate_single_test_function
7.2  test_generate_fixture_setup_teardown
7.3  test_generate_parametrize_multiple_data_sets
7.4  test_map_comparison_type_to_assertion
7.5  test_normalize_function_name
7.6  test_generate_mock_fixture
7.7  test_validate_syntax_py_compile
7.8  test_generate_conftest_shared_fixtures
7.9  test_full_generation_golden_data
7.10 test_edge_cases_empty_no_assertions_long_name
"""

import py_compile
import tempfile

import pytest

from app.services.test_generation.codegen.base import (
    CodeGenRegistry,
    TestCodeFile,
)
from app.services.test_generation.codegen.pytest_generator import PytestCodeGenerator

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def generator() -> PytestCodeGenerator:
    """Zwraca instancje PytestCodeGenerator z domyslna konfiguracja."""
    return PytestCodeGenerator()


@pytest.fixture
def registry() -> CodeGenRegistry:
    """Zwraca singleton instancje CodeGenRegistry (pytest juz zarejestrowany)."""
    return CodeGenRegistry.get_instance()


@pytest.fixture
def sample_test_case() -> dict:
    """Pojedynczy test case do testow."""
    return {
        "title": "Dodawanie dwoch liczb",
        "scenario_name": "Dodawanie liczb dodatnich",
        "description": "Sprawdza czy funkcja add poprawnie dodaje.",
        "test_type": "unit",
        "source_file": "app/calculator.py",
        "source_class": "Calculator",
        "source_function": "add",
        "setup_code": "calc = Calculator()",
        "teardown_code": "calc.reset()",
        "expected_result": "expected",
        "comparison_type": "equals",
    }


@pytest.fixture
def parametrize_test_case() -> dict:
    """Test case z wieloma zestawami danych."""
    return {
        "title": "Parametryzowane dodawanie",
        "scenario_name": "Dodawanie roznych wartosci",
        "description": "Sprawdza dodawanie z roznymi danymi.",
        "test_type": "unit",
        "source_file": "app/math.py",
        "source_function": "add",
        "test_data": {
            "sets": [
                {"a": 1, "b": 2, "expected": 3},
                {"a": 10, "b": 20, "expected": 30},
                {"a": -1, "b": 1, "expected": 0},
            ]
        },
        "expected_result": "expected",
        "comparison_type": "equals",
    }


@pytest.fixture
def mock_test_case() -> dict:
    """Test case z zaleznosciami do mockowania."""
    return {
        "title": "Zapis do bazy danych",
        "scenario_name": "Zapis wyniku do DB",
        "description": "Test integracyjny z mockiem DB.",
        "test_type": "integration",
        "source_file": "app/calculator.py",
        "source_class": "Calculator",
        "source_function": "save",
        "dependencies": [
            {"target": "app.calculator.Database.connect", "name": "db"},
        ],
        "expected_result": "True",
        "comparison_type": "is_true",
    }


# ── 7.1 Test: generowanie pojedynczej funkcji testowej ────────────────────────


class TestGenerateSingleFunction:
    """7.1 Test generowania pojedynczej funkcji testowej."""

    def test_generates_valid_python(self, generator, sample_test_case):
        """Wygenerowany kod kompiluje sie przez py_compile."""
        result = generator.generate_test_file([sample_test_case])
        assert result.compilation_result is not None
        assert result.compilation_result.success, (
            f"Kompilacja nie powiodla sie: {result.compilation_result.error_message}"
        )

    def test_function_name_starts_with_test(self, generator, sample_test_case):
        """Nazwa funkcji testowej zaczyna sie od test_."""
        result = generator.generate_test_file([sample_test_case])
        assert len(result.test_functions) == 1
        assert result.test_functions[0]["name"].startswith("test_")

    def test_function_has_docstring(self, generator, sample_test_case):
        """Funkcja testowa zawiera docstring."""
        result = generator.generate_test_file([sample_test_case])
        assert "description" in result.test_functions[0]
        assert result.test_functions[0]["description"]

    def test_contains_import_pytest(self, generator, sample_test_case):
        """Wygenerowany kod zawiera import pytest."""
        result = generator.generate_test_file([sample_test_case])
        assert "import pytest" in result.content


# ── 7.2 Test: generowanie fixture z setup/teardown ────────────────────────────


class TestFixtureGeneration:
    """7.2 Test generowania @pytest.fixture z setup/teardown."""

    def test_fixture_present_when_setup_code(self, generator, sample_test_case):
        """Fixture jest generowany gdy test case ma setup_code."""
        result = generator.generate_test_file([sample_test_case])
        assert len(result.fixtures) >= 1
        assert result.fixtures[0]["name"] is not None

    def test_fixture_has_yield(self, generator, sample_test_case):
        """Fixture zawiera yield."""
        result = generator.generate_test_file([sample_test_case])
        assert "yield" in result.content

    def test_fixture_teardown_after_yield(self, generator, sample_test_case):
        """Teardown jest po yield w wygenerowanym kodzie."""
        result = generator.generate_test_file([sample_test_case])
        content = result.content
        yield_pos = content.find("yield")
        teardown_pos = content.find("calc.reset()")
        assert yield_pos > 0
        assert teardown_pos > yield_pos

    def test_no_fixture_when_no_setup(self, generator):
        """Brak fixture gdy test case nie ma setup_code ani teardown_code."""
        tc = {"title": "Prosty test", "test_type": "unit"}
        result = generator.generate_test_file([tc])
        # Brak setup_code/teardown_code → brak fixture z tego test case
        fixture_names = [f["name"] for f in result.fixtures]
        assert len(fixture_names) == 0


# ── 7.3 Test: generowanie @pytest.mark.parametrize ────────────────────────────


class TestParametrize:
    """7.3 Test generowania @pytest.mark.parametrize z wieloma zestawami."""

    def test_parametrize_decorator_present(self, generator, parametrize_test_case):
        """Dekorator parametrize jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([parametrize_test_case])
        assert "@pytest.mark.parametrize" in result.content

    def test_parametrize_has_all_values(self, generator, parametrize_test_case):
        """Wszystkie zestawy danych sa w parametrize."""
        result = generator.generate_test_file([parametrize_test_case])
        assert "(1, 2, 3)" in result.content
        assert "(10, 20, 30)" in result.content
        assert "(-1, 1, 0)" in result.content

    def test_no_parametrize_single_data_set(self, generator):
        """Brak parametrize gdy tylko 1 zestaw danych."""
        tc = {
            "title": "Pojedynczy zestaw",
            "test_type": "unit",
            "test_data": {"a": 1, "b": 2},
            "expected_result": "3",
            "comparison_type": "equals",
        }
        result = generator.generate_test_file([tc])
        assert "@pytest.mark.parametrize" not in result.content

    def test_no_parametrize_no_data(self, generator, sample_test_case):
        """Brak parametrize gdy brak test_data."""
        result = generator.generate_test_file([sample_test_case])
        assert "@pytest.mark.parametrize" not in result.content


# ── 7.4 Test: mapowanie comparison_type na asercje pytest ──────────────────────


class TestAssertionMapping:
    """7.4 Test mapowania comparison_type na asercje pytest."""

    @pytest.mark.parametrize(
        "comparison_type,expected,actual,expected_fragment",
        [
            ("equals", "42", "result", "assert result == 42"),
            ("not_equals", "42", "result", "assert result != 42"),
            ("contains", '"hello"', "text", '"hello" in text'),
            ("not_contains", '"hello"', "text", '"hello" not in text'),
            ("throws", "ValueError", "func()", "pytest.raises(ValueError)"),
            ("approx", "3.14", "result", "pytest.approx(3.14)"),
            ("is_none", "None", "result", "assert result is None"),
            ("is_not_none", "None", "result", "assert result is not None"),
            ("is_instance", "int", "result", "isinstance(result, int)"),
            ("is_true", "True", "flag", "assert flag is True"),
            ("is_false", "False", "flag", "assert flag is False"),
            ("greater_than", "0", "result", "assert result > 0"),
            ("less_than", "100", "result", "assert result < 100"),
            ("has_length", "5", "items", "len(items) == 5"),
        ],
    )
    def test_assertion_contains_expected_fragment(
        self, generator, comparison_type, expected, actual, expected_fragment
    ):
        """Kazdy comparison_type generuje poprawna asercje."""
        result = generator.generate_assertion(
            expected=expected,
            actual=actual,
            comparison_type=comparison_type,
        )
        assert expected_fragment in result

    def test_unknown_comparison_type_fallback(self, generator):
        """Nieznany comparison_type fallbackuje do assert equals."""
        result = generator.generate_assertion("42", "result", "unknown_type")
        assert "assert" in result
        assert "42" in result


# ── 7.5 Test: normalizacja nazwy funkcji ──────────────────────────────────────


class TestNormalizeFunctionName:
    """7.5 Test normalizacji nazwy scenariusza na snake_case."""

    @pytest.mark.parametrize(
        "input_name,expected",
        [
            ("Dodawanie dwoch liczb", "dodawanie_dwoch_liczb"),
            ("User Login API", "user_login_api"),
            ("test-case-with-dashes", "test_case_with_dashes"),
            ("  spaces  & special! chars #123  ", "spaces_special_chars_123"),
            ("already_snake_case", "already_snake_case"),
            ("CamelCaseName", "camelcasename"),
            ("test@example.com", "testexamplecom"),
            ("UPPERCASE NAME", "uppercase_name"),
        ],
    )
    def test_normalization(self, input_name, expected):
        """Konwersja na snake_case z normalizacja znakow."""
        result = PytestCodeGenerator._normalize_function_name(input_name)
        assert result == expected

    def test_empty_string_returns_unnamed(self):
        """Pusty string zwraca 'unnamed'."""
        assert PytestCodeGenerator._normalize_function_name("") == "unnamed"

    def test_very_long_name_truncated(self):
        """Bardzo dluga nazwa jest obcinana do 60 znakow."""
        long_name = "a" * 100
        result = PytestCodeGenerator._normalize_function_name(long_name)
        assert len(result) <= 60

    def test_only_special_chars_returns_unnamed(self):
        """Same znaki specjalne zwracaja 'unnamed'."""
        result = PytestCodeGenerator._normalize_function_name("!@#$%^&*()")
        assert result == "unnamed"


# ── 7.6 Test: generowanie mock fixture ────────────────────────────────────────


class TestMockFixture:
    """7.6 Test generowania mock fixture."""

    def test_mock_patch_present(self, generator, mock_test_case):
        """unittest.mock.patch jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([mock_test_case])
        assert "unittest.mock.patch" in result.content

    def test_mock_target_correct(self, generator, mock_test_case):
        """Cel mocka jest poprawny."""
        result = generator.generate_test_file([mock_test_case])
        assert "app.calculator.Database.connect" in result.content

    def test_mock_return_value(self, generator, mock_test_case):
        """Mock ma ustawione return_value."""
        result = generator.generate_test_file([mock_test_case])
        assert "return_value" in result.content

    def test_no_mock_without_dependencies(self, generator, sample_test_case):
        """Brak mockow gdy test case nie ma dependencies."""
        result = generator.generate_test_file([sample_test_case])
        assert "@unittest.mock.patch" not in result.content


# ── 7.7 Test: walidacja kompilacji wygenerowanego kodu (py_compile) ────────────


class TestValidateSyntax:
    """7.7 Test walidacji kompilacji przez py_compile."""

    def test_valid_code_passes(self, generator):
        """Poprawny kod Python przechodzi walidacje."""
        code = "import pytest\n\ndef test_example():\n    assert True\n"
        result = generator.validate_syntax(code)
        assert result.success is True
        assert result.error_message is None

    def test_invalid_code_fails(self, generator):
        """Niepoprawny kod Python nie przechodzi walidacji."""
        code = "def test_example(\n    assert True\n"  # brak zamkniecia nawiasu
        result = generator.validate_syntax(code)
        assert result.success is False
        assert result.error_message is not None

    def test_empty_code_fails(self, generator):
        """Pusty kod nie przechodzi walidacji."""
        result = generator.validate_syntax("")
        assert result.success is False
        assert "Pusty kod" in result.error_message

    def test_missing_pytest_import_warning(self, generator):
        """Brak 'import pytest' generuje ostrzezenie."""
        code = "def test_example():\n    assert True\n"
        result = generator.validate_syntax(code)
        assert result.success is True
        assert any("import pytest" in w for w in result.warnings)

    def test_error_line_parsed(self, generator):
        """Numer linii bledu jest ekstrahowany."""
        code = "import pytest\n\ndef test_ok():\n    assert True\n\nbad syntax here (\n"
        result = generator.validate_syntax(code)
        assert result.success is False
        # Niektore bledy maja numer linii
        if result.error_line:
            assert result.error_line > 0


# ── 7.8 Test: generowanie conftest.py z wspolnymi fixtures ────────────────────


class TestConftestGeneration:
    """7.8 Test generowania conftest.py."""

    def test_conftest_valid_python(self, generator):
        """conftest.py kompiluje sie poprawnie."""
        ctx = {"project_name": "testgen", "dependencies": ["database"]}
        content = generator.generate_setup(ctx)
        assert "import pytest" in content

        # Walidacja py_compile
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            py_compile.compile(f.name, doraise=True)

    def test_db_fixture_present(self, generator):
        """Fixture db_session jest generowany gdy projekt wymaga DB."""
        ctx = {"project_name": "testgen", "dependencies": ["database"]}
        content = generator.generate_setup(ctx)
        assert "db_session" in content
        assert "@pytest.fixture" in content

    def test_mock_fixture_present(self, generator):
        """Mock fixture jest generowany gdy projekt wymaga API."""
        ctx = {"project_name": "testgen", "dependencies": ["api"]}
        content = generator.generate_setup(ctx)
        assert "mock_api_client" in content
        assert "unittest.mock" in content

    def test_empty_conftest_without_deps(self, generator):
        """conftest bez zaleznosci nie ma fixture."""
        content = generator.generate_setup()
        assert "# Brak wspolnych fixtures" in content or "pass" in content


# ── 7.9 Test: pelny przeplyw generowania pliku testowego (golden data) ────────


class TestFullGenerationGoldenData:
    """7.9 Test pelnego przeplywu TestCase → PytestCodeGenerator → TestCodeFile."""

    def test_full_pipeline_multiple_cases(self, generator):
        """Pelny przeplyw z wieloma test case'ami."""
        test_cases = [
            {
                "title": "Dodawanie liczb",
                "scenario_name": "Dodawanie pozytywne",
                "description": "Sprawdza dodawanie.",
                "test_type": "unit",
                "source_file": "app/math.py",
                "source_class": "Calculator",
                "setup_code": "calc = Calculator()",
                "teardown_code": "calc.reset()",
                "test_data": {"sets": [{"a": 1, "b": 2, "expected": 3}, {"a": 5, "b": 5, "expected": 10}]},
                "expected_result": "expected",
                "comparison_type": "equals",
            },
            {
                "title": "Dzielenie przez zero",
                "scenario_name": "Dzielenie przez zero",
                "description": "Sprawdza wyjatek.",
                "test_type": "unit",
                "source_file": "app/math.py",
                "source_class": "Calculator",
                "setup_code": "calc = Calculator()",
                "expected_result": "ZeroDivisionError",
                "comparison_type": "throws",
            },
            {
                "title": "Mock DB save",
                "scenario_name": "Zapis do DB z mockiem",
                "description": "Test z mockiem.",
                "test_type": "integration",
                "source_file": "app/math.py",
                "source_class": "Calculator",
                "dependencies": [{"target": "app.math.Database", "name": "db"}],
                "expected_result": "True",
                "comparison_type": "is_true",
            },
        ]

        result = generator.generate_test_file(test_cases)

        # Struktura TestCodeFile
        assert isinstance(result, TestCodeFile)
        assert result.framework == "pytest"
        assert result.language == "python"
        assert result.file_path == "tests/test_math.py"
        assert result.module_name == "math"
        assert len(result.test_functions) == 3

        # Kod sie kompiluje
        assert result.compilation_result is not None
        assert result.compilation_result.success, f"Błąd kompilacji: {result.compilation_result.error_message}"

        # Zawiera wszystkie elementy
        assert "import pytest" in result.content
        assert "@pytest.mark.parametrize" in result.content
        assert "@unittest.mock.patch" in result.content
        assert "@pytest.mark.integration" in result.content
        assert "yield" in result.content

    def test_file_path_convention(self, generator):
        """file_path sledzi konwencje tests/test_{module_name}.py."""
        tc = {"title": "Test", "source_file": "app/services/user.py", "test_type": "unit"}
        result = generator.generate_test_file([tc])
        assert result.file_path == "tests/test_user.py"
        assert result.module_name == "user"


# ── 7.10 Test: edge cases ────────────────────────────────────────────────────


class TestEdgeCases:
    """7.10 Test edge cases — pusty test case, brak asercji, dluga nazwa."""

    def test_empty_test_case_list(self, generator):
        """Pusta lista test case'ow nie crashuje."""
        result = generator.generate_test_file([])
        assert result.content is not None
        assert isinstance(result, TestCodeFile)

    def test_test_case_no_assertions(self, generator):
        """Test case bez asercji generuje pass z TODO."""
        tc = {"title": "Brak asercji", "scenario_name": "No assertions", "test_type": "unit"}
        result = generator.generate_test_file([tc])
        assert "TODO" in result.content or "pass" in result.content

    def test_very_long_scenario_name(self, generator):
        """Bardzo dluga nazwa scenariusza jest obcinana."""
        tc = {
            "title": "x" * 200,
            "scenario_name": "x" * 200,
            "test_type": "unit",
        }
        result = generator.generate_test_file([tc])
        assert len(result.test_functions) == 1
        func_name = result.test_functions[0]["name"]
        assert len(func_name) <= 65  # test_ prefix + max 60
        assert func_name.startswith("test_")

    def test_test_case_with_none_fields(self, generator):
        """Test case z polami None nie crashuje."""
        tc = {
            "title": "Test z None",
            "test_type": "unit",
            "source_file": None,
            "setup_code": None,
            "teardown_code": None,
            "test_data": None,
            "expected_result": None,
            "dependencies": None,
        }
        result = generator.generate_test_file([tc])
        assert result.compilation_result.success

    def test_special_chars_in_source_file(self, generator):
        """Znaki specjalne w source_file nie crashuja."""
        tc = {
            "title": "Spec chars",
            "source_file": "app/module-name/test_file.py",
            "test_type": "unit",
            "expected_result": "42",
            "comparison_type": "equals",
        }
        result = generator.generate_test_file([tc])
        assert result.compilation_result.success

    def test_registry_get_generator(self, registry):
        """CodeGenRegistry zwraca PytestCodeGenerator dla pytest."""
        gen = registry.get_generator("pytest")
        assert isinstance(gen, PytestCodeGenerator)

    def test_registry_unsupported_framework(self, registry):
        """CodeGenRegistry rzuca KeyError dla nieobslugiwanego frameworka."""
        with pytest.raises(KeyError, match="Brak generatora"):
            registry.get_generator("nonexistent_framework")
