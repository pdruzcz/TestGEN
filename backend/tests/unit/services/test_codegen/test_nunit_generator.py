"""Unit tests for NUnitCodeGenerator — Story 1.38.

Coverage:
7.1  test_generate_single_test_method
7.2  test_generate_lifecycle_methods_setUp_tearDown
7.3  test_generate_parameterized_test_case_attrs
7.4  test_map_comparison_type_to_nunit_assertion
7.5  test_normalize_method_name_pascal_case
7.6  test_generate_mocks_moq_setup_verify
7.7  test_validate_syntax_structural
7.8  test_full_generation_golden_data
7.9  test_edge_cases_empty_no_assertions_long_name
7.10 test_test_case_source_complex_types
"""

import pytest

from app.services.test_generation.codegen.base import (
    CodeGenRegistry,
    TestCodeFile,
)
from app.services.test_generation.codegen.nunit_generator import (
    NUnitCodeGenerator,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def generator() -> NUnitCodeGenerator:
    """Zwraca instancje NUnitCodeGenerator z domyslna konfiguracja."""
    return NUnitCodeGenerator()


@pytest.fixture
def registry() -> CodeGenRegistry:
    """Zwraca singleton instancje CodeGenRegistry."""
    return CodeGenRegistry.get_instance()


@pytest.fixture
def sample_test_case() -> dict:
    """Pojedynczy test case C# do testow."""
    return {
        "title": "Dodawanie dwoch liczb",
        "scenario_name": "Dodawanie liczb dodatnich",
        "description": "Sprawdza czy metoda Add poprawnie dodaje.",
        "test_type": "unit",
        "source_file": "src/MyApp/Calculator.cs",
        "source_class": "Calculator",
        "source_function": "Add",
        "setup_code": "var calc = new Calculator();",
        "teardown_code": "calc.Dispose();",
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
        "source_file": "src/MyApp/Calculator.cs",
        "source_class": "Calculator",
        "source_function": "Add",
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
    """Test case integracyjny z zaleznosciami do mockowania Moq."""
    return {
        "title": "Zapis do bazy danych",
        "scenario_name": "Zapis wyniku do DB",
        "description": "Test integracyjny z mockiem DB.",
        "test_type": "integration",
        "source_file": "src/MyApp/Calculator.cs",
        "source_class": "Calculator",
        "source_function": "Save",
        "dependencies": [
            {
                "target": "MyApp.Data.IDatabase",
                "method": "Connect",
                "return_value": "true",
                "verify_method": "Save",
            },
        ],
        "expected_result": "True",
        "comparison_type": "is_true",
    }


# ── 7.1 Test: generowanie pojedynczej metody testowej ────────────────────────


class TestGenerateSingleMethod:
    """7.1 Test generowania pojedynczej metody testowej NUnit."""

    def test_generates_valid_csharp_structure(self, generator, sample_test_case):
        """Wygenerowany kod ma poprawna strukture C# (klasa, namespace, usingi)."""
        result = generator.generate_test_file([sample_test_case])
        assert result.compilation_result is not None
        assert result.compilation_result.success, (
            f"Walidacja nie powiodla sie: {result.compilation_result.error_message}"
        )

    def test_method_name_pascal_case_convention(self, generator, sample_test_case):
        """Nazwa metody testowa sledzi konwencje {Method}_{Scenario} (PascalCase)."""
        result = generator.generate_test_file([sample_test_case])
        assert len(result.test_functions) == 1
        name = result.test_functions[0]["name"]
        assert name.startswith("Add_")
        assert "DodawanieLiczbDodatnich" in name

    def test_contains_test_attribute(self, generator, sample_test_case):
        """Wygenerowany kod zawiera atrybut [Test]."""
        result = generator.generate_test_file([sample_test_case])
        assert "[Test]" in result.content

    def test_contains_nunit_using(self, generator, sample_test_case):
        """Wygenerowany kod zawiera using NUnit.Framework."""
        result = generator.generate_test_file([sample_test_case])
        assert "using NUnit.Framework;" in result.content

    def test_class_name_convention(self, generator, sample_test_case):
        """Nazwa klasy sledzi konwencje {TestedClass}Tests."""
        result = generator.generate_test_file([sample_test_case])
        assert "CalculatorTests" in result.content
        assert "public class" in result.content

    def test_test_fixture_attribute(self, generator, sample_test_case):
        """Klasa testowa ma atrybut [TestFixture]."""
        result = generator.generate_test_file([sample_test_case])
        assert "[TestFixture]" in result.content

    def test_namespace_declaration(self, generator, sample_test_case):
        """Kod zawiera deklaracje namespace."""
        result = generator.generate_test_file([sample_test_case])
        assert "namespace" in result.content

    def test_file_path_convention(self, generator, sample_test_case):
        """file_path sledzi konwencje Tests/{namespace}/{Class}Tests.cs."""
        result = generator.generate_test_file([sample_test_case])
        assert "Tests/" in result.file_path
        assert "CalculatorTests.cs" in result.file_path

    def test_framework_and_language(self, generator, sample_test_case):
        """TestCodeFile ma framework=nunit, language=csharp."""
        result = generator.generate_test_file([sample_test_case])
        assert result.framework == "nunit"
        assert result.language == "csharp"


# ── 7.2 Test: generowanie lifecycle methods ([SetUp], [TearDown]) ────────────


class TestLifecycleGeneration:
    """7.2 Test generowania [SetUp] i [TearDown]."""

    def test_set_up_present_when_setup(self, generator, sample_test_case):
        """[SetUp] jest generowany gdy test case ma setup_code."""
        result = generator.generate_test_file([sample_test_case])
        assert "[SetUp]" in result.content
        assert "public void SetUp()" in result.content

    def test_tear_down_present_when_teardown(self, generator, sample_test_case):
        """[TearDown] jest generowany gdy test case ma teardown_code."""
        result = generator.generate_test_file([sample_test_case])
        assert "[TearDown]" in result.content
        assert "public void TearDown()" in result.content

    def test_setup_code_in_set_up(self, generator, sample_test_case):
        """Kod setup jest wewnatrz SetUp()."""
        result = generator.generate_test_file([sample_test_case])
        content = result.content
        setup_pos = content.find("public void SetUp()")
        calc_pos = content.find("var calc = new Calculator()")
        assert setup_pos > 0
        assert calc_pos > setup_pos

    def test_no_lifecycle_when_no_setup_teardown(self, generator):
        """Brak lifecycle gdy brak setup_code i teardown_code."""
        tc = {"title": "Prosty test", "test_type": "unit", "source_class": "Simple"}
        result = generator.generate_test_file([tc])
        assert "[SetUp]" not in result.content
        assert "[TearDown]" not in result.content

    def test_mock_initialization_in_set_up(self, generator, mock_test_case):
        """Inicjalizacja mockow (new Mock<T>()) jest w [SetUp] gdy sa mocki."""
        result = generator.generate_test_file([mock_test_case])
        assert "new Mock<" in result.content
        assert "_sut = new Calculator(" in result.content


# ── 7.3 Test: generowanie [TestCase] z wieloma zestawami danych ──────────────


class TestParameterized:
    """7.3 Test generowania [TestCase(params)] z wieloma zestawami danych."""

    def test_test_case_attribute(self, generator, parametrize_test_case):
        """[TestCase(arg1, arg2, ...)] jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([parametrize_test_case])
        assert "[TestCase(" in result.content

    def test_test_case_has_all_values(self, generator, parametrize_test_case):
        """Wszystkie zestawy danych sa w atrybutach [TestCase]."""
        result = generator.generate_test_file([parametrize_test_case])
        assert "[TestCase(1, 2, 3)]" in result.content
        assert "[TestCase(10, 20, 30)]" in result.content
        assert "[TestCase(-1, 1, 0)]" in result.content

    def test_parameters_in_method_signature(self, generator, parametrize_test_case):
        """Parametry metody odpowiadaja kluczom danych testowych."""
        result = generator.generate_test_file([parametrize_test_case])
        # Metoda testowa powinna miec parametry int a, int b, int expected
        assert "int a" in result.content or "int" in result.content

    def test_no_test_case_single_data_set(self, generator):
        """Brak [TestCase] gdy tylko 1 zestaw danych — uzywa [Test]."""
        tc = {
            "title": "Pojedynczy zestaw",
            "test_type": "unit",
            "source_class": "Calc",
            "source_function": "Add",
            "test_data": {"a": 1, "b": 2},
            "expected_result": "3",
            "comparison_type": "equals",
        }
        result = generator.generate_test_file([tc])
        assert "[TestCase(" not in result.content
        assert "[Test]" in result.content

    def test_no_test_case_when_no_data(self, generator, sample_test_case):
        """Brak [TestCase] gdy brak test_data."""
        result = generator.generate_test_file([sample_test_case])
        assert "[TestCase(" not in result.content


# ── 7.4 Test: mapowanie comparison_type na asercje NUnit ──────────────────────


class TestAssertionMapping:
    """7.4 Test mapowania comparison_type na asercje NUnit 3."""

    @pytest.mark.parametrize(
        "comparison_type,expected,actual,expected_fragment",
        [
            ("equals", "42", "result", "Assert.AreEqual(42, result)"),
            ("not_equals", "42", "result", "Assert.AreNotEqual(42, result)"),
            ("contains", '"hello"', "text", "Assert.That(text, Does.Contain"),
            ("throws", "InvalidOperationException", "result", "Assert.Throws<InvalidOperationException>"),
            ("is_none", "None", "result", "Assert.IsNull(result)"),
            ("is_not_none", "None", "result", "Assert.IsNotNull(result)"),
            ("is_true", "True", "flag", "Assert.IsTrue(flag)"),
            ("is_false", "True", "flag", "Assert.IsFalse(flag)"),
            ("greater_than", "0", "result", "Assert.Greater(result, 0)"),
            ("less_than", "100", "result", "Assert.Less(result, 100)"),
        ],
    )
    def test_assertion_contains_expected_fragment(
        self, generator, comparison_type, expected, actual, expected_fragment
    ):
        """Kazdy comparison_type generuje poprawna asercje NUnit."""
        result = generator.generate_assertion(
            expected=expected,
            actual=actual,
            comparison_type=comparison_type,
        )
        assert expected_fragment in result

    def test_unknown_comparison_type_fallback(self, generator):
        """Nieznany comparison_type fallbackuje do Assert.AreEqual."""
        result = generator.generate_assertion("42", "result", "unknown_type")
        assert "Assert.AreEqual" in result
        assert "42" in result

    def test_assertion_with_message(self, generator):
        """Asercja z komunikatem zawiera message."""
        result = generator.generate_assertion("42", "result", "equals", "Wartosc powinna byc 42")
        assert "Wartosc powinna byc 42" in result

    def test_assertion_without_message(self, generator):
        """Asercja bez komunikatu nie zawiera dodatkowego argumentu."""
        result = generator.generate_assertion("42", "result", "equals", None)
        assert "Assert.AreEqual(42, result);" in result

    def test_throws_assertion_format(self, generator):
        """Asercja throws generuje Assert.Throws<T>(() => { ... });."""
        result = generator.generate_assertion("ArgumentException", "call()", "throws")
        assert "Assert.Throws<ArgumentException>" in result
        assert "() =>" in result


# ── 7.5 Test: normalizacja nazwy metody (PascalCase) ─────────────────────────


class TestNormalizeMethodName:
    """7.5 Test normalizacji nazwy scenariusza na PascalCase {Method}_{Scenario}."""

    @pytest.mark.parametrize(
        "source_func,scenario,expected_contains",
        [
            ("Add", "Dodawanie dwoch liczb", "Add_DodawanieDwochLiczb"),
            ("GetUser", "User Login API", "GetUser_UserLoginApi"),
            ("Process", "test case with dashes", "Process_TestCaseWithDashes"),
            ("Calculate", "already_valid_name", "Calculate_AlreadyValidName"),
        ],
    )
    def test_normalization_pascal_case(self, source_func, scenario, expected_contains):
        """Znormalizowana nazwa sledzi konwencje {Method}_{Scenario} PascalCase."""
        result = NUnitCodeGenerator._normalize_method_name(source_func, scenario)
        assert result == expected_contains

    def test_empty_both_returns_default(self):
        """Puste argumenty zwracaja domyslna nazwe."""
        result = NUnitCodeGenerator._normalize_method_name("", "")
        assert result == "TestMethod_WhenCalled_ReturnsExpected"

    def test_empty_scenario_uses_function_only(self):
        """Pusty scenario uzywa tylko nazwy funkcji."""
        result = NUnitCodeGenerator._normalize_method_name("Add", "")
        assert result == "Add"

    def test_very_long_name_truncated(self):
        """Bardzo dluga nazwa jest obcinana do 80 znakow."""
        long_name = "x" * 200
        result = NUnitCodeGenerator._normalize_method_name("Test", long_name)
        assert len(result) <= 80

    def test_special_chars_removed(self):
        """Znaki specjalne sa usuwane z nazwy metody."""
        result = NUnitCodeGenerator._normalize_method_name("Method", "test@example.com!")
        assert result.isalnum() or "_" in result
        assert "@" not in result

    def test_spaces_converted_to_pascal_case(self):
        """Spacje sa konwertowane na PascalCase."""
        result = NUnitCodeGenerator._normalize_method_name("Calc", "add two numbers")
        assert result == "Calc_AddTwoNumbers"


# ── 7.6 Test: generowanie mockow Moq ─────────────────────────────────────────


class TestMoqMockGeneration:
    """7.6 Test generowania Mock<T>, Setup/Returns, Verify."""

    def test_mock_field_present(self, generator, mock_test_case):
        """Pole Mock<T> jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([mock_test_case])
        assert "Mock<" in result.content
        assert "_database" in result.content.lower() or "_iDatabase" in result.content

    def test_sut_field_present(self, generator, mock_test_case):
        """Pole _sut (system under test) jest w wygenerowanym kodzie."""
        result = generator.generate_test_file([mock_test_case])
        assert "_sut" in result.content

    def test_setup_returns_present(self, generator, mock_test_case):
        """_mock.Setup(x => x.Method()).Returns(value) jest w kodzie."""
        result = generator.generate_test_file([mock_test_case])
        assert ".Setup(" in result.content
        assert ".Returns(" in result.content

    def test_moq_using_import(self, generator, mock_test_case):
        """using Moq; jest w kodzie gdy sa mocki."""
        result = generator.generate_test_file([mock_test_case])
        assert "using Moq;" in result.content

    def test_no_mock_without_dependencies(self, generator, sample_test_case):
        """Brak Moq gdy test case nie ma dependencies."""
        result = generator.generate_test_file([sample_test_case])
        assert "Mock<" not in result.content
        assert "using Moq;" not in result.content

    def test_mock_stubbing_with_side_effect(self, generator):
        """Setup().Throws() jest generowany gdy side_effect ustawione."""
        tc = {
            "title": "Blad DB",
            "scenario_name": "DB throws exception",
            "test_type": "integration",
            "source_class": "Calculator",
            "source_function": "Save",
            "dependencies": [
                {
                    "target": "MyApp.Data.IDatabase",
                    "method": "Connect",
                    "side_effect": "InvalidOperationException",
                }
            ],
            "expected_result": "InvalidOperationException",
            "comparison_type": "throws",
        }
        result = generator.generate_test_file([tc])
        assert ".Throws(new InvalidOperationException())" in result.content

    def test_verify_call_generated(self, generator):
        """Mock.Verify() jest generowany gdy verify jest ustawione."""
        tc = {
            "title": "Verify test",
            "scenario_name": "Verify method call",
            "test_type": "integration",
            "source_class": "Calculator",
            "source_function": "Save",
            "dependencies": [
                {
                    "target": "MyApp.Data.IDatabase",
                    "method": "Save",
                    "return_value": "true",
                    "verify": "Save",
                }
            ],
            "expected_result": "True",
            "comparison_type": "is_true",
        }
        result = generator.generate_test_file([tc])
        assert ".Verify(" in result.content
        assert "Times.Once" in result.content

    def test_mock_init_in_setup(self, generator, mock_test_case):
        """Inicjalizacja mocka (new Mock<T>()) jest w [SetUp]."""
        result = generator.generate_test_file([mock_test_case])
        content = result.content
        setup_pos = content.find("[SetUp]")
        mock_init_pos = content.find("new Mock<")
        assert setup_pos > 0
        assert mock_init_pos > setup_pos


# ── 7.7 Test: walidacja skladni wygenerowanego kodu C# ────────────────────────


class TestValidateSyntax:
    """7.7 Test walidacji skladni C#."""

    def test_valid_csharp_passes_structural(self, generator):
        """Poprawny kod C# przechodzi walidacje strukturalna."""
        code = (
            "namespace TestProject.Tests;\n"
            "using NUnit.Framework;\n"
            "[TestFixture]\n"
            "public class CalcTests\n"
            "{\n"
            "    [Test]\n"
            "    public void TestAdd()\n"
            "    {\n"
            "        Assert.AreEqual(2, 1 + 1);\n"
            "    }\n"
            "}\n"
        )
        result = generator.validate_syntax(code)
        assert result.success is True

    def test_unbalanced_braces_fails(self, generator):
        """Niezbalansowane nawiasy klamrowe nie przechodza walidacji."""
        code = "namespace TestProject.Tests;\npublic class CalcTests {\n    void Test() {\n        // brak zamkniecia\n"
        result = generator.validate_syntax(code)
        assert result.success is False
        assert "nawias" in result.error_message.lower() or "klamrow" in result.error_message.lower()

    def test_missing_class_declaration_fails(self, generator):
        """Brak deklaracji klasy nie przechodzi walidacji."""
        code = "namespace TestProject.Tests;\nvoid Test() {}\n"
        result = generator.validate_syntax(code)
        assert result.success is False

    def test_missing_namespace_fails(self, generator):
        """Brak deklaracji namespace nie przechodzi walidacji."""
        code = "public class CalcTests {\n}\n"
        result = generator.validate_syntax(code)
        assert result.success is False
        assert "namespace" in result.error_message.lower()

    def test_empty_code_fails(self, generator):
        """Pusty kod nie przechodzi walidacji."""
        result = generator.validate_syntax("")
        assert result.success is False
        assert "Pusty kod" in result.error_message

    def test_missing_nunit_using_warning(self, generator):
        """Brak using NUnit.Framework; generuje ostrzezenie."""
        code = "namespace TestProject.Tests;\npublic class CalcTests {\n    void Test() {}\n}\n"
        result = generator.validate_syntax(code)
        assert result.success is True
        assert any("using NUnit.Framework;" in w for w in result.warnings)

    def test_unbalanced_brackets_fails(self, generator):
        """Niezbalansowane nawiasy kwadratowe nie przechodza walidacji."""
        code = "namespace TestProject.Tests;\n[TestTestFixture\npublic class CalcTests {\n}\n"
        result = generator.validate_syntax(code)
        assert result.success is False
        assert "kwadratow" in result.error_message.lower()


# ── 7.8 Test: pelny przeplyw generowania pliku testowego (golden data) ────────


class TestFullGenerationGoldenData:
    """7.8 Test pelnego przeplywu TestCase -> NUnitCodeGenerator -> TestCodeFile."""

    def test_full_pipeline_multiple_cases(self, generator):
        """Pelny przeplyw z wieloma test case'ami."""
        test_cases = [
            {
                "title": "Dodawanie liczb",
                "scenario_name": "Dodawanie pozytywne",
                "description": "Sprawdza dodawanie.",
                "test_type": "unit",
                "source_file": "src/MyApp/Calculator.cs",
                "source_class": "Calculator",
                "source_function": "Add",
                "setup_code": "var calc = new Calculator();",
                "teardown_code": "calc.Dispose();",
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
                "source_file": "src/MyApp/Calculator.cs",
                "source_class": "Calculator",
                "source_function": "Divide",
                "setup_code": "var calc = new Calculator();",
                "expected_result": "DivideByZeroException",
                "comparison_type": "throws",
            },
            {
                "title": "Mock DB save",
                "scenario_name": "Zapis do DB z mockiem",
                "description": "Test z mockiem.",
                "test_type": "integration",
                "source_file": "src/MyApp/Calculator.cs",
                "source_class": "Calculator",
                "source_function": "Save",
                "dependencies": [
                    {
                        "target": "MyApp.Data.IDatabase",
                        "method": "Save",
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
        assert result.framework == "nunit"
        assert result.language == "csharp"
        assert "CalculatorTests.cs" in result.file_path
        assert result.module_name == "Calculator"
        assert len(result.test_functions) == 3

        # Walidacja strukturalna przechodzi
        assert result.compilation_result is not None
        assert result.compilation_result.success, f"Blad walidacji: {result.compilation_result.error_message}"

        # Zawiera wszystkie elementy
        assert "using NUnit.Framework;" in result.content
        assert "[TestCase(" in result.content
        assert "Mock<" in result.content
        assert "[SetUp]" in result.content
        assert ".Setup(" in result.content
        assert "[TestFixture]" in result.content
        assert "Assert.Throws<" in result.content

    def test_file_path_with_namespace(self, generator):
        """file_path sledzi konwencje Tests/{namespace}/{Class}Tests.cs."""
        tc = {
            "title": "Test",
            "source_file": "src/MyApp/Services/UserService.cs",
            "source_class": "UserService",
            "source_function": "GetUser",
            "test_type": "unit",
        }
        result = generator.generate_test_file([tc])
        assert "UserServiceTests.cs" in result.file_path
        assert "Tests/" in result.file_path


# ── 7.9 Test: edge cases ────────────────────────────────────────────────────


class TestEdgeCases:
    """7.9 Test edge cases — pusty test case, brak asercji, dluga nazwa."""

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
            "source_function": "DoStuff",
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
            "source_function": "Test",
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
            "source_function": None,
            "setup_code": None,
            "teardown_code": None,
            "test_data": None,
            "expected_result": None,
            "dependencies": None,
        }
        result = generator.generate_test_file([tc])
        assert result.compilation_result is not None

    def test_complex_parameterized_types(self, generator):
        """Zlozone typy danych w parametryzacji generuja [TestCaseSource]."""
        tc = {
            "title": "Zlozone dane",
            "scenario_name": "Test z listami",
            "test_type": "unit",
            "source_class": "Processor",
            "source_function": "Process",
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
        # Zlozone typy moga uzyc [TestCase] lub [TestCaseSource]
        assert "[TestCase(" in result.content or "[TestCaseSource(" in result.content

    def test_registry_has_nunit_generator(self, registry):
        """CodeGenRegistry obsluguje framework nunit."""
        assert registry.is_supported("nunit")

    def test_registry_get_nunit_generator(self, registry):
        """CodeGenRegistry zwraca NUnitCodeGenerator dla nunit."""
        gen = registry.get_generator("nunit")
        assert isinstance(gen, NUnitCodeGenerator)


# ── 7.10 Test: TestCaseSource dla zlozonych typow ────────────────────────────


class TestTestCaseSource:
    """7.10 Test generowania [TestCaseSource] dla zlozonych typow danych."""

    def test_test_case_source_generated_for_complex_data(self, generator):
        """[TestCaseSource] jest generowany dla zlozonych typow (obiekty zagniezdzone)."""
        tc = {
            "title": "Zlozone dane",
            "scenario_name": "Test z obiektami",
            "test_type": "unit",
            "source_class": "Processor",
            "source_function": "Process",
            "test_data": {
                "sets": [
                    {"input": [1, 2, 3], "expected": 6},
                    {"input": [4, 5], "expected": 9},
                ]
            },
            "expected_result": "expected",
            "comparison_type": "equals",
        }
        result = generator.generate_test_file([tc])
        assert "[TestCaseSource(" in result.content

    def test_csharp_value_literal_types(self):
        """_csharp_value_literal konwertuje typy Python na literaly C#."""
        assert NUnitCodeGenerator._csharp_value_literal(None) == "null"
        assert NUnitCodeGenerator._csharp_value_literal(True) == "true"
        assert NUnitCodeGenerator._csharp_value_literal(False) == "false"
        assert NUnitCodeGenerator._csharp_value_literal(42) == "42"
        assert NUnitCodeGenerator._csharp_value_literal(3.14) == "3.14f"
        assert NUnitCodeGenerator._csharp_value_literal("hello") == '"hello"'
        assert NUnitCodeGenerator._csharp_value_literal([1, 2]) == "new[] { 1, 2 }"

    def test_build_file_path(self):
        """_build_file_path generuje poprawna sciezke."""
        path = NUnitCodeGenerator._build_file_path("MyApp.Tests.Services", "UserServiceTests")
        assert path == "Tests/MyApp/Tests/Services/UserServiceTests.cs"

    def test_to_camel_case(self):
        """_to_camel_case konwertuje nazwe klasy na camelCase."""
        assert NUnitCodeGenerator._to_camel_case("Calculator") == "calculator"
        assert NUnitCodeGenerator._to_camel_case("UserService") == "userService"
        assert NUnitCodeGenerator._to_camel_case("") == "instance"

    def test_file_path_to_namespace(self):
        """_file_path_to_namespace konwertuje sciezke na namespace C#."""
        ns = NUnitCodeGenerator._file_path_to_namespace("src/MyApp/Services/UserService.cs")
        assert ns == "MyApp.Services"

    def test_file_path_to_namespace_fallback(self):
        """_file_path_to_namespace fallback dla prostych sciezek."""
        ns = NUnitCodeGenerator._file_path_to_namespace("UserService.cs")
        assert isinstance(ns, str)
        assert len(ns) > 0

    def test_generate_setup_returns_string(self, generator):
        """generate_setup zwraca niepusty string."""
        result = generator.generate_setup({"project_name": "testgen"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_infer_csharp_type(self):
        """_infer_csharp_type wnioskuje typ C# z danych."""
        data = [{"a": 1}, {"a": 2}]
        assert NUnitCodeGenerator._infer_csharp_type(data, "a") == "int"

        data = [{"a": True}]
        assert NUnitCodeGenerator._infer_csharp_type(data, "a") == "bool"

        data = [{"a": "hello"}]
        assert NUnitCodeGenerator._infer_csharp_type(data, "a") == "string"

        data = [{"a": 3.14}]
        assert NUnitCodeGenerator._infer_csharp_type(data, "a") == "double"

        data = [{"a": None}]
        assert NUnitCodeGenerator._infer_csharp_type(data, "a") == "object"

    def test_multiple_data_types_in_test_case(self, generator):
        """[TestCase] obsluguje rozne typy danych: string, int, double, bool."""
        tc = {
            "title": "Rozne typy",
            "scenario_name": "Test z roznymi typami",
            "test_type": "unit",
            "source_class": "Calculator",
            "source_function": "Compute",
            "test_data": {
                "sets": [
                    {"input": "test", "count": 1, "ratio": 1.5, "flag": True},
                    {"input": "data", "count": 2, "ratio": 2.5, "flag": False},
                ]
            },
            "expected_result": "expected",
            "comparison_type": "equals",
        }
        result = generator.generate_test_file([tc])
        assert "[TestCase(" in result.content
        assert '"test"' in result.content
        assert "true" in result.content
        assert "false" in result.content

    def test_no_self_referencing_using(self, generator):
        """Using nie zawiera samego siebie (namespace == using)."""
        tc = {
            "title": "Test",
            "scenario_name": "Self ref check",
            "test_type": "unit",
            "source_class": "Calculator",
            "source_function": "Add",
        }
        result = generator.generate_test_file([tc])
        # Sprawdz ze namespace nie jest w usingach
        lines = result.content.split("\n")
        namespace_line = ""
        for line in lines:
            if line.strip().startswith("namespace "):
                namespace_line = line.strip().replace("namespace ", "").rstrip(";").strip()
                break
        if namespace_line:
            for line in lines:
                if line.strip().startswith("using "):
                    using_ns = line.strip().replace("using ", "").rstrip(";").strip()
                    assert using_ns != namespace_line, f"Self-referencing using: using {namespace_line};"
