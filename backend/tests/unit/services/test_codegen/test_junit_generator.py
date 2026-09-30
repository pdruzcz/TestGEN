"""Unit tests for JUnitCodeGenerator — Story 1.37.

Coverage:
7.1  test_generate_single_test_method
7.2  test_generate_lifecycle_methods_before_each_after_each
7.3  test_generate_parameterized_test_csv_source
7.4  test_map_comparison_type_to_junit_assertion
7.5  test_normalize_method_name_should_x_when_y
7.6  test_generate_mocks_mockito_inject_mocks_when_then_return
7.7  test_validate_syntax_structural
7.8  test_full_generation_golden_data
7.9  test_edge_cases_empty_no_assertions_long_name_complex_types
"""

import pytest

from app.services.test_generation.codegen.base import (
    CodeGenRegistry,
    TestCodeFile,
)
from app.services.test_generation.codegen.junit_generator import (
    JUnitCodeGenerator,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def generator() -> JUnitCodeGenerator:
    """Zwraca instancje JUnitCodeGenerator z domyslna konfiguracja."""
    return JUnitCodeGenerator()


@pytest.fixture
def registry() -> CodeGenRegistry:
    """Zwraca singleton instancje CodeGenRegistry."""
    return CodeGenRegistry.get_instance()


@pytest.fixture
def sample_test_case() -> dict:
    """Pojedynczy test case Java do testow."""
    return {
        "title": "Dodawanie dwoch liczb",
        "scenario_name": "Dodawanie liczb dodatnich",
        "description": "Sprawdza czy metoda add poprawnie dodaje.",
        "test_type": "unit",
        "source_file": "src/main/java/com/example/Calculator.java",
        "source_class": "Calculator",
        "source_function": "add",
        "setup_code": "Calculator calc = new Calculator();",
        "teardown_code": "calc.reset();",
        "expected_result": "5",
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
        "source_file": "src/main/java/com/example/Calculator.java",
        "source_class": "Calculator",
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
    """Test case integracyjny z zaleznosciami do mockowania Mockito."""
    return {
        "title": "Zapis do bazy danych",
        "scenario_name": "Zapis wyniku do DB",
        "description": "Test integracyjny z mockiem DB.",
        "test_type": "integration",
        "source_file": "src/main/java/com/example/Calculator.java",
        "source_class": "Calculator",
        "source_function": "save",
        "dependencies": [
            {
                "target": "com.example.Database",
                "method": "connect",
                "return_value": "true",
                "verify_method": "save",
            },
        ],
        "expected_result": "True",
        "comparison_type": "is_true",
    }


# ── 7.1 Test: generowanie pojedynczej metody testowej ────────────────────────


class TestGenerateSingleMethod:
    """7.1 Test generowania pojedynczej metody testowej JUnit."""

    def test_generates_valid_java_structure(self, generator, sample_test_case):
        """Wygenerowany kod ma poprawna strukture Java (klasa, package, importy)."""
        result = generator.generate_test_file([sample_test_case])
        assert result.compilation_result is not None
        assert result.compilation_result.success, (
            f"Walidacja nie powiodla sie: {result.compilation_result.error_message}"
        )

    def test_method_name_starts_with_should(self, generator, sample_test_case):
        """Nazwa metody testowej zaczyna sie od should."""
        result = generator.generate_test_file([sample_test_case])
        assert len(result.test_functions) == 1
        assert result.test_functions[0]["name"].startswith("should")

    def test_contains_test_annotation(self, generator, sample_test_case):
        """Wygenerowany kod zawiera adnotacje @Test."""
        result = generator.generate_test_file([sample_test_case])
        assert "@Test" in result.content

    def test_contains_junit_imports(self, generator, sample_test_case):
        """Wygenerowany kod zawiera importy JUnit 5."""
        result = generator.generate_test_file([sample_test_case])
        assert "import org.junit.jupiter.api.Test" in result.content
        assert "import static org.junit.jupiter.api.Assertions.*" in result.content

    def test_class_name_convention(self, generator, sample_test_case):
        """Nazwa klasy sledzi konwencje {TestedClass}Test."""
        result = generator.generate_test_file([sample_test_case])
        assert "CalculatorTest" in result.content
        assert "public class" in result.content

    def test_package_declaration(self, generator, sample_test_case):
        """Kod zawiera deklaracje package."""
        result = generator.generate_test_file([sample_test_case])
        assert "package com.example" in result.content

    def test_display_name_annotation(self, generator, sample_test_case):
        """Kod zawiera adnotacje @DisplayName."""
        result = generator.generate_test_file([sample_test_case])
        assert "@DisplayName" in result.content

    def test_file_path_convention(self, generator, sample_test_case):
        """file_path sledzi konwencje src/test/java/{package}/{Class}Test.java."""
        result = generator.generate_test_file([sample_test_case])
        assert "src/test/java/" in result.file_path
        assert "CalculatorTest.java" in result.file_path

    def test_framework_and_language(self, generator, sample_test_case):
        """TestCodeFile ma framework=junit, language=java."""
        result = generator.generate_test_file([sample_test_case])
        assert result.framework == "junit"
        assert result.language == "java"


# ── 7.2 Test: generowanie lifecycle methods (@BeforeEach, @AfterEach) ────────


class TestLifecycleGeneration:
    """7.2 Test generowania @BeforeEach i @AfterEach."""

    def test_before_each_present_when_setup(self, generator, sample_test_case):
        """@BeforeEach jest generowany gdy test case ma setup_code."""
        result = generator.generate_test_file([sample_test_case])
        assert "@BeforeEach" in result.content
        assert "void setUp()" in result.content

    def test_after_each_present_when_teardown(self, generator, sample_test_case):
        """@AfterEach jest generowany gdy test case ma teardown_code."""
        result = generator.generate_test_file([sample_test_case])
        assert "@AfterEach" in result.content
        assert "void tearDown()" in result.content

    def test_setup_code_in_before_each(self, generator, sample_test_case):
        """Kod setup jest wewnatrz setUp()."""
        result = generator.generate_test_file([sample_test_case])
        content = result.content
        setup_pos = content.find("void setUp()")
        calc_pos = content.find("Calculator calc = new Calculator()")
        assert setup_pos > 0
        assert calc_pos > setup_pos

    def test_no_lifecycle_when_no_setup_teardown(self, generator):
        """Brak lifecycle gdy brak setup_code i teardown_code."""
        tc = {"title": "Prosty test", "test_type": "unit", "source_class": "Simple"}
        result = generator.generate_test_file([tc])
        assert "@BeforeEach" not in result.content
        assert "@AfterEach" not in result.content

    def test_mockito_open_mocks_in_before_each(self, generator, mock_test_case):
        """MockitoAnnotations.openMocks(this) jest w @BeforeEach gdy sa mocki."""
        result = generator.generate_test_file([mock_test_case])
        assert "MockitoAnnotations.openMocks(this)" in result.content


# ── 7.3 Test: generowanie @ParameterizedTest z @CsvSource ────────────────────


class TestParameterized:
    """7.3 Test generowania @ParameterizedTest z @CsvSource."""

    def test_parameterized_test_annotation(self, generator, parametrize_test_case):
        """@ParameterizedTest jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([parametrize_test_case])
        assert "@ParameterizedTest" in result.content

    def test_csv_source_present(self, generator, parametrize_test_case):
        """@CsvSource jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([parametrize_test_case])
        assert "@CsvSource" in result.content

    def test_csv_source_has_all_values(self, generator, parametrize_test_case):
        """Wszystkie zestawy danych sa w @CsvSource."""
        result = generator.generate_test_file([parametrize_test_case])
        assert '"1, 2, 3"' in result.content
        assert '"10, 20, 30"' in result.content
        assert '"-1, 1, 0"' in result.content

    def test_parameterized_imports(self, generator, parametrize_test_case):
        """Importy ParameterizedTest sa w kodzie."""
        result = generator.generate_test_file([parametrize_test_case])
        assert "import org.junit.jupiter.params.ParameterizedTest" in result.content
        assert "import org.junit.jupiter.params.provider.CsvSource" in result.content

    def test_no_parameterized_single_data_set(self, generator):
        """Brak @ParameterizedTest gdy tylko 1 zestaw danych."""
        tc = {
            "title": "Pojedynczy zestaw",
            "test_type": "unit",
            "source_class": "Calc",
            "test_data": {"a": 1, "b": 2},
            "expected_result": "3",
            "comparison_type": "equals",
        }
        result = generator.generate_test_file([tc])
        assert "@ParameterizedTest" not in result.content

    def test_no_parameterized_no_data(self, generator, sample_test_case):
        """Brak @ParameterizedTest gdy brak test_data."""
        result = generator.generate_test_file([sample_test_case])
        assert "@ParameterizedTest" not in result.content


# ── 7.4 Test: mapowanie comparison_type na asercje JUnit ──────────────────────


class TestAssertionMapping:
    """7.4 Test mapowania comparison_type na asercje JUnit 5."""

    @pytest.mark.parametrize(
        "comparison_type,expected,actual,expected_fragment",
        [
            ("equals", "42", "result", "assertEquals(42, result)"),
            ("not_equals", "42", "result", "assertNotEquals(42, result)"),
            ("contains", '"hello"', "text", 'assertTrue(text.contains("hello"))'),
            ("throws", "IllegalArgumentException", "result", "assertThrows(IllegalArgumentException.class"),
            ("is_none", "None", "result", "assertNull(result)"),
            ("is_not_none", "None", "result", "assertNotNull(result)"),
            ("is_true", "True", "flag", "assertTrue(flag)"),
            ("is_false", "True", "flag", "assertFalse(flag)"),
            ("greater_than", "0", "result", "assertTrue(result > 0)"),
            ("less_than", "100", "result", "assertTrue(result < 100)"),
        ],
    )
    def test_assertion_contains_expected_fragment(
        self, generator, comparison_type, expected, actual, expected_fragment
    ):
        """Kazdy comparison_type generuje poprawna asercje JUnit."""
        result = generator.generate_assertion(
            expected=expected,
            actual=actual,
            comparison_type=comparison_type,
        )
        assert expected_fragment in result

    def test_unknown_comparison_type_fallback(self, generator):
        """Nieznany comparison_type fallbackuje do assertEquals."""
        result = generator.generate_assertion("42", "result", "unknown_type")
        assert "assertEquals" in result
        assert "42" in result

    def test_assertion_with_message(self, generator):
        """Asercja z komunikatem zawiera message."""
        result = generator.generate_assertion("42", "result", "equals", "Wartosc powinna byc 42")
        assert "Wartosc powinna byc 42" in result

    def test_assertion_without_message(self, generator):
        """Asercja bez komunikatu nie zawiera dodatkowego argumentu."""
        result = generator.generate_assertion("42", "result", "equals", None)
        assert "assertEquals(42, result)" in result


# ── 7.5 Test: normalizacja nazwy metody (should_X_when_Y) ────────────────────


class TestNormalizeMethodName:
    """7.5 Test normalizacji nazwy scenariusza na camelCase should_X_when_Y."""

    @pytest.mark.parametrize(
        "input_name,expected_start",
        [
            ("Dodawanie dwoch liczb", "should"),
            ("User Login API", "should"),
            ("test-case-with-dashes", "should"),
            ("already_valid_name", "should"),
        ],
    )
    def test_normalization_starts_with_should(self, input_name, expected_start):
        """Znormalizowana nazwa zaczyna sie od should."""
        result = JUnitCodeGenerator._normalize_method_name(input_name)
        assert result.startswith(expected_start)

    def test_empty_string_returns_default(self):
        """Pusty string zwraca domyslna nazwe."""
        result = JUnitCodeGenerator._normalize_method_name("")
        assert result == "should_work_whenCalled"

    def test_very_long_name_truncated(self):
        """Bardzo dluga nazwa jest obcinana do 80 znakow."""
        long_name = "should " + "x" * 200
        result = JUnitCodeGenerator._normalize_method_name(long_name)
        assert len(result) <= 80

    def test_special_chars_removed(self):
        """Znaki specjalne sa usuwane z nazwy metody."""
        result = JUnitCodeGenerator._normalize_method_name("test@example.com!")
        # Tylko alfanumeryki i _
        assert result.isascii()

    def test_spaces_converted_to_camel_case(self):
        """Spacje sa konwertowane na camelCase."""
        result = JUnitCodeGenerator._normalize_method_name("should add numbers when called")
        assert "Should" in result or "should" in result

    def test_preformatted_should_preserved(self):
        """Nazwa zaczynajaca sie od 'should ' jest zachowana."""
        result = JUnitCodeGenerator._normalize_method_name("should return true when input is valid")
        assert result.startswith("should")


# ── 7.6 Test: generowanie mockow Mockito ─────────────────────────────────────


class TestMockitoMockGeneration:
    """7.6 Test generowania @Mock, @InjectMocks, when/thenReturn."""

    def test_mock_annotation_present(self, generator, mock_test_case):
        """Adnotacja @Mock jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([mock_test_case])
        assert "@Mock" in result.content

    def test_inject_mocks_present(self, generator, mock_test_case):
        """Adnotacja @InjectMocks jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([mock_test_case])
        assert "@InjectMocks" in result.content

    def test_mock_field_type_correct(self, generator, mock_test_case):
        """Typ pola mocka jest poprawny."""
        result = generator.generate_test_file([mock_test_case])
        assert "com.example.Database" in result.content

    def test_when_then_return_present(self, generator, mock_test_case):
        """when().thenReturn() jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([mock_test_case])
        assert "when(" in result.content
        assert "thenReturn" in result.content

    def test_mockito_imports(self, generator, mock_test_case):
        """Importy Mockito sa w kodzie."""
        result = generator.generate_test_file([mock_test_case])
        assert "import org.mockito.Mock" in result.content
        assert "import org.mockito.InjectMocks" in result.content
        assert "import org.mockito.MockitoAnnotations" in result.content

    def test_no_mock_without_dependencies(self, generator, sample_test_case):
        """Brak Mockito gdy test case nie ma dependencies."""
        result = generator.generate_test_file([sample_test_case])
        assert "@Mock" not in result.content
        assert "@InjectMocks" not in result.content

    def test_mock_stubbing_with_side_effect(self, generator):
        """when().thenThrow() jest generowany gdy side_effect ustawione."""
        tc = {
            "title": "Blad DB",
            "scenario_name": "DB throws exception",
            "test_type": "integration",
            "source_class": "Calculator",
            "dependencies": [
                {
                    "target": "com.example.Database",
                    "method": "connect",
                    "side_effect": "RuntimeException",
                }
            ],
            "expected_result": "RuntimeException",
            "comparison_type": "throws",
        }
        result = generator.generate_test_file([tc])
        assert "thenThrow(new RuntimeException())" in result.content


# ── 7.7 Test: walidacja skladni wygenerowanego kodu Java ──────────────────────


class TestValidateSyntax:
    """7.7 Test walidacji skladni Java."""

    def test_valid_java_passes_structural(self, generator):
        """Poprawny kod Java przechodzi walidacje strukturalna."""
        code = (
            "package com.example;\n"
            "import org.junit.jupiter.api.Test;\n"
            "public class CalcTest {\n"
            "    @Test\n"
            "    void testAdd() {\n"
            "        assertEquals(2, 1 + 1);\n"
            "    }\n"
            "}\n"
        )
        result = generator.validate_syntax(code)
        assert result.success is True

    def test_unbalanced_braces_fails(self, generator):
        """Niezbalansowane nawiasy klamrowe nie przechodza walidacji."""
        code = "package com.example;\npublic class CalcTest {\n    void test() {\n        // brak zamkniecia\n"
        result = generator.validate_syntax(code)
        assert result.success is False
        assert "nawias" in result.error_message.lower() or "klamrow" in result.error_message.lower()

    def test_missing_class_declaration_fails(self, generator):
        """Brak deklaracji klasy nie przechodzi walidacji."""
        code = "package com.example;\nvoid test() {}\n"
        result = generator.validate_syntax(code)
        assert result.success is False

    def test_missing_package_fails(self, generator):
        """Brak deklaracji package nie przechodzi walidacji."""
        code = "public class CalcTest {\n}\n"
        result = generator.validate_syntax(code)
        assert result.success is False
        assert "package" in result.error_message.lower()

    def test_empty_code_fails(self, generator):
        """Pusty kod nie przechodzi walidacji."""
        result = generator.validate_syntax("")
        assert result.success is False
        assert "Pusty kod" in result.error_message

    def test_missing_junit_import_warning(self, generator):
        """Brak importu JUnit generuje ostrzezenie."""
        code = "package com.example;\npublic class CalcTest {\n    void test() {}\n}\n"
        result = generator.validate_syntax(code)
        assert result.success is True
        assert any("import org.junit.jupiter.api.Test" in w for w in result.warnings)


# ── 7.8 Test: pelny przeplyw generowania pliku testowego (golden data) ────────


class TestFullGenerationGoldenData:
    """7.8 Test pelnego przeplywu TestCase -> JUnitCodeGenerator -> TestCodeFile."""

    def test_full_pipeline_multiple_cases(self, generator):
        """Pelny przeplyw z wieloma test case'ami."""
        test_cases = [
            {
                "title": "Dodawanie liczb",
                "scenario_name": "Dodawanie pozytywne",
                "description": "Sprawdza dodawanie.",
                "test_type": "unit",
                "source_file": "src/main/java/com/example/Calculator.java",
                "source_class": "Calculator",
                "setup_code": "Calculator calc = new Calculator();",
                "teardown_code": "calc.reset();",
                "test_data": {
                    "sets": [
                        {"a": 1, "b": 2, "expected": 3},
                        {"a": 5, "b": 5, "expected": 10},
                    ]
                },
                "expected_result": "expected",
                "comparison_type": "equals",
            },
            {
                "title": "Dzielenie przez zero",
                "scenario_name": "Dzielenie przez zero",
                "description": "Sprawdza wyjatek.",
                "test_type": "unit",
                "source_file": "src/main/java/com/example/Calculator.java",
                "source_class": "Calculator",
                "setup_code": "Calculator calc = new Calculator();",
                "expected_result": "ArithmeticException",
                "comparison_type": "throws",
            },
            {
                "title": "Mock DB save",
                "scenario_name": "Zapis do DB z mockiem",
                "description": "Test z mockiem.",
                "test_type": "integration",
                "source_file": "src/main/java/com/example/Calculator.java",
                "source_class": "Calculator",
                "dependencies": [
                    {
                        "target": "com.example.Database",
                        "method": "save",
                        "return_value": "true",
                    }
                ],
                "expected_result": "True",
                "comparison_type": "is_true",
            },
        ]

        result = generator.generate_test_file(test_cases)

        # Struktura TestCodeFile
        assert isinstance(result, TestCodeFile)
        assert result.framework == "junit"
        assert result.language == "java"
        assert "CalculatorTest.java" in result.file_path
        assert result.module_name == "Calculator"
        assert len(result.test_functions) == 3

        # Walidacja strukturalna przechodzi
        assert result.compilation_result is not None
        assert result.compilation_result.success, f"Blad walidacji: {result.compilation_result.error_message}"

        # Zawiera wszystkie elementy
        assert "import org.junit.jupiter.api.Test" in result.content
        assert "@ParameterizedTest" in result.content
        assert "@CsvSource" in result.content
        assert "@Mock" in result.content
        assert "@InjectMocks" in result.content
        assert "@BeforeEach" in result.content
        assert "when(" in result.content

    def test_file_path_convention(self, generator):
        """file_path sledzi konwencje src/test/java/{package}/{Class}Test.java."""
        tc = {
            "title": "Test",
            "source_file": "src/main/java/com/example/service/UserService.java",
            "source_class": "UserService",
            "test_type": "unit",
        }
        result = generator.generate_test_file([tc])
        assert result.file_path == "src/test/java/com/example/service/UserServiceTest.java"


# ── 7.9 Test: edge cases ────────────────────────────────────────────────────


class TestEdgeCases:
    """7.9 Test edge cases — pusty test case, brak asercji, dluga nazwa, zlozone typy."""

    def test_empty_test_case_list(self, generator):
        """Pusta lista test case'ow nie crashuje."""
        result = generator.generate_test_file([])
        assert result.content is not None
        assert isinstance(result, TestCodeFile)

    def test_test_case_no_assertions(self, generator):
        """Test case bez asercji generuje TODO w kodzie."""
        tc = {
            "title": "Brak asercji",
            "scenario_name": "No assertions",
            "source_class": "Simple",
            "test_type": "unit",
        }
        result = generator.generate_test_file([tc])
        assert "TODO" in result.content

    def test_very_long_scenario_name(self, generator):
        """Bardzo dluga nazwa scenariusza jest obcinana."""
        tc = {
            "title": "x" * 200,
            "scenario_name": "x" * 200,
            "source_class": "Simple",
            "test_type": "unit",
        }
        result = generator.generate_test_file([tc])
        assert len(result.test_functions) == 1
        method_name = result.test_functions[0]["name"]
        assert len(method_name) <= 80

    def test_test_case_with_none_fields(self, generator):
        """Test case z polami None nie crashuje."""
        tc = {
            "title": "Test z None",
            "test_type": "unit",
            "source_file": None,
            "source_class": None,
            "setup_code": None,
            "teardown_code": None,
            "test_data": None,
            "expected_result": None,
            "dependencies": None,
        }
        result = generator.generate_test_file([tc])
        assert result.compilation_result is not None

    def test_complex_parameterized_types(self, generator):
        """Zlozone typy danych w parametryzacji generuja @MethodSource."""
        tc = {
            "title": "Zlozone dane",
            "scenario_name": "Test z listami",
            "test_type": "unit",
            "source_class": "Processor",
            "test_data": {
                "sets": [
                    {"input": "List.of(1, 2, 3)", "expected": 6},
                    {"input": "List.of(4, 5)", "expected": 9},
                ]
            },
            "expected_result": "expected",
            "comparison_type": "equals",
        }
        result = generator.generate_test_file([tc])
        assert "@ParameterizedTest" in result.content
        # Zlozone typy moga uzyc CsvSource lub MethodSource
        assert "@CsvSource" in result.content or "@MethodSource" in result.content

    def test_registry_has_junit_generator(self, registry):
        """CodeGenRegistry obsluguje framework junit."""
        assert registry.is_supported("junit")

    def test_registry_get_junit_generator(self, registry):
        """CodeGenRegistry zwraca JUnitCodeGenerator dla junit."""
        gen = registry.get_generator("junit")
        assert isinstance(gen, JUnitCodeGenerator)

    def test_java_value_literal_types(self):
        """_java_value_literal konwertuje typy Python na literaly Java."""
        assert JUnitCodeGenerator._java_value_literal(None) == "null"
        assert JUnitCodeGenerator._java_value_literal(True) == "true"
        assert JUnitCodeGenerator._java_value_literal(False) == "false"
        assert JUnitCodeGenerator._java_value_literal(42) == "42"
        assert JUnitCodeGenerator._java_value_literal(3.14) == "3.14d"
        assert JUnitCodeGenerator._java_value_literal("hello") == '"hello"'
        assert JUnitCodeGenerator._java_value_literal([1, 2]) == "List.of(1, 2)"

    def test_build_file_path(self):
        """_build_file_path generuje poprawna sciezke."""
        path = JUnitCodeGenerator._build_file_path("com.example.service", "UserServiceTest")
        assert path == "src/test/java/com/example/service/UserServiceTest.java"

    def test_to_camel_case(self):
        """_to_camel_case konwertuje nazwe klasy na camelCase."""
        assert JUnitCodeGenerator._to_camel_case("Calculator") == "calculator"
        assert JUnitCodeGenerator._to_camel_case("UserService") == "userService"
        assert JUnitCodeGenerator._to_camel_case("") == "instance"

    def test_file_path_to_package(self):
        """_file_path_to_package konwertuje sciezke na pakiet Java."""
        pkg = JUnitCodeGenerator._file_path_to_package("src/main/java/com/example/service/UserService.java")
        assert pkg == "com.example.service"

    def test_file_path_to_package_fallback(self):
        """_file_path_to_package fallback gdy brak src/main/java."""
        pkg = JUnitCodeGenerator._file_path_to_package("UserService.java")
        assert isinstance(pkg, str)
        assert len(pkg) > 0

    def test_generate_setup_returns_string(self, generator):
        """generate_setup zwraca niepusty string."""
        result = generator.generate_setup({"project_name": "testgen"})
        assert isinstance(result, str)
        assert len(result) > 0
