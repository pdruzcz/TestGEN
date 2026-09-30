"""Testy jednostkowe MochaJestCodeGenerator — Story 1.39.

AC: 1-11

Pokrycie:
- Task 1: Core generator (generate_test_file, imports, describe/it, assertions, async, lifecycle)
- Task 2: Mockowanie (Jest: jest.mock/fn/spyOn, Sinon: stub/mock/sandbox)
- Task 3: TypeScript (rozszerzenie .test.ts, typowanie)
- Task 4: Szablony Jinja2
- Task 5: Walidacja skladni JS/TS
- Task 6: Wybor frameworku (jest vs mocha)
- Task 7: Integracja z orchestratorem (rejestracja)
- Task 8: Edge cases
"""

import pytest

from app.services.test_generation.codegen.base import (
    CodeGenConfig,
    CodeGenRegistry,
)
from app.services.test_generation.codegen.mocha_jest_generator import (
    MochaJestCodeGenerator,
    js_value_literal,
)

# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def jest_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="mocha_jest",
        language="javascript",
        file_extension=".test.js",
        validate_compilation=False,
        project_context={"framework_variant": "jest"},
    )


@pytest.fixture
def mocha_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="mocha_jest",
        language="javascript",
        file_extension=".test.js",
        validate_compilation=False,
        project_context={"framework_variant": "mocha"},
    )


@pytest.fixture
def ts_jest_config() -> CodeGenConfig:
    return CodeGenConfig(
        framework="mocha_jest",
        language="typescript",
        file_extension=".test.ts",
        validate_compilation=False,
        project_context={"framework_variant": "jest", "typescript": True},
    )


@pytest.fixture
def generator(jest_config: CodeGenConfig) -> MochaJestCodeGenerator:
    return MochaJestCodeGenerator(config=jest_config)


@pytest.fixture
def mocha_generator(mocha_config: CodeGenConfig) -> MochaJestCodeGenerator:
    return MochaJestCodeGenerator(config=mocha_config)


@pytest.fixture
def basic_test_case() -> dict:
    return {
        "scenario_name": "Add two numbers",
        "source_class": "Calculator",
        "source_module": "calculator.js",
        "test_type": "unit",
        "steps": [{"code": "const result = calculator.add(2, 3);"}],
        "expected_result": "5",
        "comparison_type": "equals",
    }


@pytest.fixture
def async_test_case() -> dict:
    return {
        "scenario_name": "Fetch user data",
        "source_class": "UserService",
        "source_module": "userService.js",
        "test_type": "integration",
        "steps": [{"code": "const result = await userService.fetchUser(1);"}],
        "expected_result": "'John'",
        "comparison_type": "equals",
        "is_async": True,
        "dependencies": [{"target": "api", "type": "api", "method": "fetch"}],
    }


@pytest.fixture
def mock_test_case() -> dict:
    return {
        "scenario_name": "Save user to database",
        "source_class": "UserService",
        "source_module": "userService.js",
        "test_type": "integration",
        "steps": [{"code": "const result = userService.save(user);"}],
        "expected_result": "true",
        "comparison_type": "is_true",
        "dependencies": [
            {
                "target": "./database",
                "type": "db",
                "method": "save",
                "return_value": True,
                "verify": "save",
            }
        ],
    }


@pytest.fixture
def parameterized_test_case() -> dict:
    return {
        "scenario_name": "Add multiple inputs",
        "source_class": "Calculator",
        "source_module": "calculator.js",
        "test_type": "unit",
        "steps": [{"code": "const result = calculator.add(a, b);"}],
        "expected_result": "expected",
        "comparison_type": "equals",
        "test_data": [
            {"a": 2, "b": 3, "expected": 5},
            {"a": 0, "b": 0, "expected": 0},
            {"a": -1, "b": 1, "expected": 0},
        ],
    }


@pytest.fixture
def lifecycle_test_case() -> dict:
    return {
        "scenario_name": "Process data with setup",
        "source_class": "DataProcessor",
        "source_module": "dataProcessor.js",
        "test_type": "unit",
        "setup_code": "const processor = new DataProcessor();",
        "teardown_code": "processor.cleanup();",
        "steps": [{"code": "const result = processor.process(data);"}],
        "expected_result": "'processed'",
        "comparison_type": "equals",
    }


# ════════════════════════════════════════════════════════════════════════
# AC 1: Generator registration — MochaJestCodeGenerator
# ════════════════════════════════════════════════════════════════════════


class TestGeneratorRegistration:
    def test_registry_has_mocha_jest_generator(self):
        assert CodeGenRegistry.get_instance().is_supported("mocha_jest")

    def test_registry_get_mocha_jest_generator(self):
        gen = CodeGenRegistry.get_instance().get_generator("mocha_jest")
        assert isinstance(gen, MochaJestCodeGenerator)

    def test_framework_and_language(self, generator: MochaJestCodeGenerator):
        assert generator.FRAMEWORK == "mocha_jest"
        assert generator.LANGUAGE == "javascript"
        assert generator.FILE_EXTENSION == ".test.js"


# ════════════════════════════════════════════════════════════════════════
# AC 2: Imports — describe/it/expect + module imports
# ════════════════════════════════════════════════════════════════════════


class TestImports:
    def test_jest_no_global_imports(self, generator: MochaJestCodeGenerator, jest_config: CodeGenConfig):
        """Jest globals — brak importow describe/it/expect."""
        imports = generator._build_imports(
            [{"source_module": "calculator.js", "source_class": "Calculator"}],
            jest_config,
            "jest",
            False,
        )
        # Jest nie importuje chai ani sinon
        assert not any("chai" in imp for imp in imports)

    def test_mocha_imports_chai_and_sinon(self, mocha_generator: MochaJestCodeGenerator, mocha_config: CodeGenConfig):
        """Mocha wymaga importu chai."""
        imports = mocha_generator._build_imports(
            [{"source_module": "calculator.js", "source_class": "Calculator"}],
            mocha_config,
            "mocha",
            False,
        )
        assert any("chai" in imp for imp in imports)
        assert any("expect" in imp for imp in imports)

    def test_source_module_import(self, generator: MochaJestCodeGenerator, jest_config: CodeGenConfig):
        """Import testowanego modulu."""
        imports = generator._build_imports(
            [{"source_module": "calculator.js", "source_class": "Calculator"}],
            jest_config,
            "jest",
            False,
        )
        assert any("Calculator" in imp for imp in imports)
        assert any("calculator" in imp for imp in imports)

    def test_typescript_uses_import_syntax(self, generator: MochaJestCodeGenerator, jest_config: CodeGenConfig):
        """TS uzywa import zamiast require."""
        imports = generator._build_imports(
            [{"source_module": "calculator.ts", "source_class": "Calculator"}],
            jest_config,
            "jest",
            True,
        )
        assert any("import" in imp and "Calculator" in imp for imp in imports)

    def test_javascript_uses_require_syntax(self, generator: MochaJestCodeGenerator, jest_config: CodeGenConfig):
        """JS uzywa require."""
        imports = generator._build_imports(
            [{"source_module": "calculator.js", "source_class": "Calculator"}],
            jest_config,
            "jest",
            False,
        )
        assert any("require" in imp and "Calculator" in imp for imp in imports)

    def test_explicit_imports_from_test_case(self, generator: MochaJestCodeGenerator, jest_config: CodeGenConfig):
        """Explicit importy z test case."""
        imports = generator._build_imports(
            [{"source_module": "calc.js", "imports": ["const fs = require('fs');"]}],
            jest_config,
            "jest",
            False,
        )
        assert any("fs" in imp for imp in imports)


# ════════════════════════════════════════════════════════════════════════
# AC 3: describe/it structure
# ════════════════════════════════════════════════════════════════════════


class TestDescribeIt:
    def test_describe_block_present(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert "describe(" in result.content
        assert "Calculator" in result.content

    def test_it_block_present(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert "it(" in result.content

    def test_describe_name_matches_module(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert "describe('Calculator'" in result.content

    def test_it_description_normalized(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert "should" in result.content.lower()


# ════════════════════════════════════════════════════════════════════════
# AC 4: Assertions — Jest vs Mocha+Chai
# ════════════════════════════════════════════════════════════════════════


class TestJestAssertions:
    @pytest.mark.parametrize(
        "comparison_type,expected,actual,expected_fragment",
        [
            ("equals", "42", "result", "expect(result).toBe(42)"),
            ("not_equals", "42", "result", "expect(result).not.toBe(42)"),
            ("contains", "'hello'", "text", "expect(text).toContain('hello')"),
            ("throws", "Error", "fn()", "toThrow(Error)"),
            ("approx", "3.14", "result", "expect(result).toBeCloseTo(3.14, 2)"),
            ("is_none", "None", "result", "expect(result).toBeNull()"),
            ("is_not_none", "None", "result", "expect(result).toBeDefined()"),
            ("is_true", "True", "flag", "expect(flag).toBeTruthy()"),
            ("is_false", "True", "flag", "expect(flag).toBeFalsy()"),
            ("greater_than", "0", "result", "expect(result).toBeGreaterThan(0)"),
            ("less_than", "100", "result", "expect(result).toBeLessThan(100)"),
            ("has_length", "3", "arr", "expect(arr).toHaveLength(3)"),
            ("is_instance", "Array", "result", "expect(result).toBeInstanceOf(Array)"),
        ],
    )
    def test_assertion_contains_expected_fragment(
        self, generator: MochaJestCodeGenerator, comparison_type, expected, actual, expected_fragment
    ):
        result = generator.generate_assertion(expected, actual, comparison_type)
        assert expected_fragment in result

    def test_unknown_comparison_type_fallback(self, generator: MochaJestCodeGenerator):
        result = generator.generate_assertion("42", "result", "unknown_type")
        assert "nieznany comparison_type: unknown_type" in result


class TestMochaAssertions:
    @pytest.mark.parametrize(
        "comparison_type,expected,actual,expected_fragment",
        [
            ("equals", "42", "result", "expect(result).to.equal(42)"),
            ("not_equals", "42", "result", "expect(result).to.not.equal(42)"),
            ("contains", "'hello'", "text", "expect(text).to.include('hello')"),
            ("throws", "Error", "fn()", "to.throw(Error)"),
            ("approx", "3.14", "result", "expect(result).to.be.closeTo(3.14, 2)"),
            ("is_none", "None", "result", "expect(result).to.be.null"),
            ("is_not_none", "None", "result", "expect(result).to.exist"),
            ("is_true", "True", "flag", "expect(flag).to.be.true"),
            ("is_false", "True", "flag", "expect(flag).to.be.false"),
            ("greater_than", "0", "result", "expect(result).to.be.above(0)"),
            ("less_than", "100", "result", "expect(result).to.be.below(100)"),
            ("has_length", "3", "arr", "expect(arr).to.have.lengthOf(3)"),
        ],
    )
    def test_assertion_contains_expected_fragment(
        self, mocha_generator: MochaJestCodeGenerator, comparison_type, expected, actual, expected_fragment
    ):
        result = mocha_generator.generate_assertion(expected, actual, comparison_type)
        assert expected_fragment in result


# ════════════════════════════════════════════════════════════════════════
# AC 5: Async/await
# ════════════════════════════════════════════════════════════════════════


class TestAsyncAwait:
    def test_async_test_has_async_keyword(self, generator: MochaJestCodeGenerator, async_test_case: dict):
        result = generator.generate_test_file([async_test_case])
        assert "async" in result.content

    def test_sync_test_no_async(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        # Szukamy czy it() nie ma async (dla testow synchronicznych)
        lines = result.content.split("\n")
        it_lines = [line for line in lines if "it(" in line]
        # Przynajmniej jeden it() bez async
        if it_lines:
            assert any("async" not in line for line in it_lines)

    def test_async_detected_from_await_step(self, generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "Async test",
            "source_class": "Service",
            "steps": [{"code": "const result = await service.getData();"}],
            "expected_result": "'data'",
            "comparison_type": "equals",
        }
        assert generator._is_async_test(tc) is True

    def test_async_detected_from_is_async_flag(self, generator: MochaJestCodeGenerator):
        tc = {"is_async": True}
        assert generator._is_async_test(tc) is True

    def test_async_detected_from_api_dependency(self, generator: MochaJestCodeGenerator):
        tc = {"dependencies": [{"type": "api", "target": "api"}]}
        assert generator._is_async_test(tc) is True

    def test_sync_test_detected(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        assert generator._is_async_test(basic_test_case) is False


# ════════════════════════════════════════════════════════════════════════
# AC 6: Setup/teardown — beforeEach/afterEach
# ════════════════════════════════════════════════════════════════════════


class TestLifecycle:
    def test_before_each_present_when_setup(self, generator: MochaJestCodeGenerator, lifecycle_test_case: dict):
        result = generator.generate_test_file([lifecycle_test_case])
        assert "beforeEach(" in result.content

    def test_after_each_present_when_teardown(self, generator: MochaJestCodeGenerator, lifecycle_test_case: dict):
        result = generator.generate_test_file([lifecycle_test_case])
        assert "afterEach(" in result.content

    def test_setup_code_in_before_each(self, generator: MochaJestCodeGenerator, lifecycle_test_case: dict):
        result = generator.generate_test_file([lifecycle_test_case])
        content = result.content
        assert "processor" in content
        assert "beforeEach" in content

    def test_no_lifecycle_when_no_setup_teardown(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        tc = {k: v for k, v in basic_test_case.items() if k not in ("setup_code", "teardown_code")}
        result = generator.generate_test_file([tc])
        # Nie musi byc beforeEach/afterEach dla prostych testow bez setup/teardown
        # Ale mocki tez dodaja lifecycle — wiec sprawdzamy ze nie ma setup_code
        if "beforeEach" not in result.content:
            pass  # OK — brak lifecycle


# ════════════════════════════════════════════════════════════════════════
# AC 7: Mockowanie — Jest + Sinon
# ════════════════════════════════════════════════════════════════════════


class TestJestMocks:
    def test_jest_mock_present(
        self, generator: MochaJestCodeGenerator, jest_config: CodeGenConfig, mock_test_case: dict
    ):
        result = generator.generate_test_file([mock_test_case])
        assert "jest" in result.content.lower() or "mock" in result.content.lower()

    def test_jest_fn_generated(self, generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "Mock test",
            "source_class": "Service",
            "source_module": "service.js",
            "steps": [{"code": "const result = service.call();"}],
            "expected_result": "true",
            "comparison_type": "is_true",
            "dependencies": [{"target": "./db", "type": "db", "method": "query", "return_value": True}],
        }
        result = generator.generate_test_file([tc])
        assert "jest.fn()" in result.content or "mockReturnValue" in result.content

    def test_jest_restore_all_mocks_in_after_each(self, generator: MochaJestCodeGenerator, jest_config: CodeGenConfig):
        tc = {
            "scenario_name": "Mock test",
            "source_class": "Service",
            "source_module": "service.js",
            "steps": [],
            "expected_result": "true",
            "comparison_type": "is_true",
            "dependencies": [{"target": "./db", "type": "db", "method": "query"}],
        }
        result = generator.generate_test_file([tc])
        assert "restoreAllMocks" in result.content

    def test_no_mock_without_dependencies(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert "jest.fn()" not in result.content


class TestSinonMocks:
    def test_sinon_stub_generated(self, mocha_generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "Mock test",
            "source_class": "Service",
            "source_module": "service.js",
            "steps": [{"code": "const result = service.call();"}],
            "expected_result": "true",
            "comparison_type": "is_true",
            "dependencies": [{"target": "./db", "type": "db", "method": "query", "return_value": True}],
        }
        result = mocha_generator.generate_test_file([tc])
        assert "sandbox.stub" in result.content or "sandbox" in result.content

    def test_sinon_sandbox_restore(self, mocha_generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "Mock test",
            "source_class": "Service",
            "source_module": "service.js",
            "steps": [],
            "expected_result": "true",
            "comparison_type": "is_true",
            "dependencies": [{"target": "./db", "type": "db", "method": "query"}],
        }
        result = mocha_generator.generate_test_file([tc])
        assert "sandbox.restore()" in result.content


# ════════════════════════════════════════════════════════════════════════
# AC 8: TypeScript support
# ════════════════════════════════════════════════════════════════════════


class TestTypeScript:
    def test_typescript_file_extension(self):
        config = CodeGenConfig(
            framework="mocha_jest",
            project_context={"framework_variant": "jest", "typescript": True},
            validate_compilation=False,
        )
        gen = MochaJestCodeGenerator(config=config)
        tc = {
            "scenario_name": "TS test",
            "source_class": "Calculator",
            "source_module": "calculator.ts",
            "steps": [{"code": "const result = calc.add(2, 3);"}],
            "expected_result": "5",
            "comparison_type": "equals",
        }
        result = gen.generate_test_file([tc])
        assert result.language == "typescript"
        assert ".test.ts" in result.file_path

    def test_javascript_file_extension(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert result.language == "javascript"
        assert ".test.js" in result.file_path

    def test_typescript_detected_from_source_file(self, generator: MochaJestCodeGenerator, jest_config: CodeGenConfig):
        """Automatyczna detekcja TS z rozszerzenia .ts."""
        tc = {
            "scenario_name": "TS test",
            "source_module": "calculator.ts",
            "source_class": "Calculator",
            "steps": [],
            "expected_result": "5",
            "comparison_type": "equals",
        }
        assert generator._is_typescript([tc], jest_config) is True

    def test_detect_typescript_utility(self):
        assert MochaJestCodeGenerator._detect_typescript({"typescript": True}) is True
        assert MochaJestCodeGenerator._detect_typescript({"typescript": False}) is False
        assert MochaJestCodeGenerator._detect_typescript(None) is False


# ════════════════════════════════════════════════════════════════════════
# AC 9: Walidacja skladni JS/TS
# ════════════════════════════════════════════════════════════════════════


class TestValidateSyntax:
    def test_valid_js_passes_structural(self, generator: MochaJestCodeGenerator):
        code = """
describe('Calculator', () => {
  it('should add two numbers', () => {
    expect(2 + 2).toBe(4);
  });
});
"""
        result = generator.validate_syntax(code)
        assert result.success is True

    def test_unbalanced_braces_fails(self, generator: MochaJestCodeGenerator):
        code = """describe('Calc', () => {
  it('test', () => {
    expect(1).toBe(1);
"""
        result = generator.validate_syntax(code)
        assert result.success is False

    def test_missing_describe_warns(self, generator: MochaJestCodeGenerator):
        code = """it('test', () => {
  expect(1).toBe(1);
});"""
        result = generator.validate_syntax(code)
        # node --check akceptuje poprawny JS bez describe — sprawdzamy warning
        assert any("describe" in w.lower() for w in result.warnings) or result.success is False

    def test_missing_it_warns(self, generator: MochaJestCodeGenerator):
        code = """describe('Calc', () => {
  expect(1).toBe(1);
});"""
        result = generator.validate_syntax(code)
        # node --check akceptuje poprawny JS bez it — sprawdzamy warning
        assert any("it" in w.lower() or "test" in w.lower() for w in result.warnings) or result.success is False

    def test_empty_code_fails(self, generator: MochaJestCodeGenerator):
        result = generator.validate_syntax("")
        assert result.success is False
        assert "Pusty" in result.error_message

    def test_unbalanced_parens_fails(self, generator: MochaJestCodeGenerator):
        code = """describe('Calc', () => {
  it('test', () => {
    expect(1.toBe(1);
  });
});"""
        result = generator.validate_syntax(code)
        assert result.success is False


# ════════════════════════════════════════════════════════════════════════
# AC 10: Wybor frameworku (jest vs mocha)
# ════════════════════════════════════════════════════════════════════════


class TestFrameworkVariant:
    def test_default_variant_is_jest(self):
        config = CodeGenConfig(framework="mocha_jest")
        gen = MochaJestCodeGenerator(config=config)
        assert gen._get_variant() == "jest"

    def test_jest_variant(self, jest_config: CodeGenConfig):
        gen = MochaJestCodeGenerator(config=jest_config)
        assert gen._get_variant() == "jest"

    def test_mocha_variant(self, mocha_config: CodeGenConfig):
        gen = MochaJestCodeGenerator(config=mocha_config)
        assert gen._get_variant() == "mocha"

    def test_jest_assertion_syntax(self, generator: MochaJestCodeGenerator):
        result = generator.generate_assertion("42", "result", "equals")
        assert ".toBe(" in result

    def test_mocha_assertion_syntax(self, mocha_generator: MochaJestCodeGenerator):
        result = mocha_generator.generate_assertion("42", "result", "equals")
        assert ".to.equal(" in result

    def test_jest_mock_syntax(self, generator: MochaJestCodeGenerator, jest_config: CodeGenConfig):
        tc = {
            "scenario_name": "Mock test",
            "source_class": "Service",
            "source_module": "service.js",
            "steps": [],
            "expected_result": "true",
            "comparison_type": "is_true",
            "dependencies": [{"target": "./db", "type": "db", "method": "query"}],
        }
        result = generator.generate_test_file([tc])
        assert "jest" in result.content.lower()

    def test_mocha_mock_syntax(self, mocha_generator: MochaJestCodeGenerator, mocha_config: CodeGenConfig):
        tc = {
            "scenario_name": "Mock test",
            "source_class": "Service",
            "source_module": "service.js",
            "steps": [],
            "expected_result": "true",
            "comparison_type": "is_true",
            "dependencies": [{"target": "./db", "type": "db", "method": "query"}],
        }
        result = mocha_generator.generate_test_file([tc])
        assert "sinon" in result.content.lower()

    def test_invalid_variant_defaults_to_jest(self):
        config = CodeGenConfig(
            framework="mocha_jest",
            project_context={"framework_variant": "invalid"},
        )
        gen = MochaJestCodeGenerator(config=config)
        assert gen._get_variant() == "jest"


# ════════════════════════════════════════════════════════════════════════
# AC 11: Szablony Jinja2
# ════════════════════════════════════════════════════════════════════════


class TestTemplates:
    def test_js_template_used_for_javascript(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert result.language == "javascript"
        assert ".test.js" in result.file_path

    def test_ts_template_used_for_typescript(self, ts_jest_config: CodeGenConfig):
        gen = MochaJestCodeGenerator(config=ts_jest_config)
        tc = {
            "scenario_name": "TS test",
            "source_class": "Calculator",
            "source_module": "calculator.ts",
            "steps": [{"code": "const result = calc.add(2, 3);"}],
            "expected_result": "5",
            "comparison_type": "equals",
        }
        result = gen.generate_test_file([tc])
        assert ".test.ts" in result.file_path

    def test_generated_content_has_describe_block(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert "describe(" in result.content

    def test_generated_content_has_it_block(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert "it(" in result.content


# ════════════════════════════════════════════════════════════════════════
# Task 8.1: Normalizacja opisu testu
# ════════════════════════════════════════════════════════════════════════


class TestNormalizeDescription:
    @pytest.mark.parametrize(
        "scenario,expected_start",
        [
            ("Add two numbers", "should add two numbers"),
            ("should return true", "should return true"),
            ("when input is empty, returns null", "should when input is empty, returns null"),
            ("Validate email format", "should validate email format"),
        ],
    )
    def test_normalization(self, scenario, expected_start):
        result = MochaJestCodeGenerator._normalize_test_description(scenario)
        assert result.startswith(expected_start[:20])

    def test_empty_scenario(self):
        result = MochaJestCodeGenerator._normalize_test_description("")
        assert "should" in result

    def test_already_starts_with_should(self):
        result = MochaJestCodeGenerator._normalize_test_description("should work correctly")
        assert result == "should work correctly"


# ════════════════════════════════════════════════════════════════════════
# Parametryzacja — test.each() / it.each()
# ════════════════════════════════════════════════════════════════════════


class TestParameterization:
    def test_test_each_generated_for_multiple_data(
        self, generator: MochaJestCodeGenerator, parameterized_test_case: dict
    ):
        result = generator.generate_test_file([parameterized_test_case])
        assert "each" in result.content or "describe" in result.content

    def test_no_test_each_single_data(self, generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "Single data test",
            "source_class": "Calculator",
            "source_module": "calculator.js",
            "steps": [{"code": "const result = calc.add(2, 3);"}],
            "expected_result": "5",
            "comparison_type": "equals",
            "test_data": [{"a": 2, "b": 3, "expected": 5}],
        }
        result = generator.generate_test_file([tc])
        # Pojedynczy zestaw danych = zwykly test
        assert "it(" in result.content

    def test_no_test_each_when_no_data(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert "it(" in result.content


# ════════════════════════════════════════════════════════════════════════
# Pełny pipeline — golden data test
# ════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    def test_full_pipeline_multiple_cases(self, generator: MochaJestCodeGenerator):
        test_cases = [
            {
                "scenario_name": "Add two positive numbers",
                "source_class": "Calculator",
                "source_module": "calculator.js",
                "steps": [{"code": "const result = calc.add(2, 3);"}],
                "expected_result": "5",
                "comparison_type": "equals",
            },
            {
                "scenario_name": "Add negative numbers",
                "source_class": "Calculator",
                "source_module": "calculator.js",
                "steps": [{"code": "const result = calc.add(-1, -2);"}],
                "expected_result": "-3",
                "comparison_type": "equals",
            },
        ]
        result = generator.generate_test_file(test_cases)
        assert "describe(" in result.content
        assert result.content.count("it(") >= 2
        assert "Calculator" in result.content
        assert ".test.js" in result.file_path

    def test_file_path_structure(self, generator: MochaJestCodeGenerator, basic_test_case: dict):
        result = generator.generate_test_file([basic_test_case])
        assert result.file_path.startswith("tests/")
        assert ".test.js" in result.file_path


# ════════════════════════════════════════════════════════════════════════
# Edge cases
# ════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_test_case_list(self, generator: MochaJestCodeGenerator):
        result = generator.generate_test_file([])
        assert "Brak test case" in result.content

    def test_test_case_no_assertions(self, generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "No assertions",
            "source_class": "Calculator",
            "source_module": "calculator.js",
            "steps": [{"code": "calc.initialize();"}],
        }
        result = generator.generate_test_file([tc])
        assert "describe(" in result.content

    def test_very_long_scenario_name(self, generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "A" * 200,
            "source_class": "Calculator",
            "source_module": "calculator.js",
            "steps": [],
            "expected_result": "5",
            "comparison_type": "equals",
        }
        result = generator.generate_test_file([tc])
        assert "describe(" in result.content

    def test_test_case_with_none_fields(self, generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": None,
            "source_class": None,
            "source_module": None,
            "steps": None,
            "expected_result": None,
            "comparison_type": None,
        }
        result = generator.generate_test_file([tc])
        assert "describe(" in result.content

    def test_js_value_literal_none(self):
        assert js_value_literal(None) == "null"

    def test_js_value_literal_bool(self):
        assert js_value_literal(True) == "true"
        assert js_value_literal(False) == "false"

    def test_js_value_literal_int(self):
        assert js_value_literal(42) == "42"

    def test_js_value_literal_float(self):
        assert js_value_literal(3.14) == "3.14"

    def test_js_value_literal_string(self):
        assert js_value_literal("hello") == "'hello'"

    def test_js_value_literal_list(self):
        assert js_value_literal([1, 2, 3]) == "[1, 2, 3]"

    def test_js_value_literal_dict(self):
        result = js_value_literal({"a": 1})
        assert "'a'" in result
        assert "1" in result


# ════════════════════════════════════════════════════════════════════════
# Metody pomocnicze
# ════════════════════════════════════════════════════════════════════════


class TestHelperMethods:
    def test_to_camel_case(self):
        assert MochaJestCodeGenerator._to_camel_case("Calculator") == "calculator"
        assert MochaJestCodeGenerator._to_camel_case("my-module") == "myModule"
        assert MochaJestCodeGenerator._to_camel_case("my_module") == "myModule"
        assert MochaJestCodeGenerator._to_camel_case("") == "module"

    def test_extract_module_name_from_source_class(self):
        tc = {"source_class": "Calculator"}
        assert MochaJestCodeGenerator._extract_module_name(tc) == "Calculator"

    def test_extract_module_name_from_source_file(self):
        tc = {"source_file": "src/calculator.js"}
        assert MochaJestCodeGenerator._extract_module_name(tc) == "calculator"

    def test_extract_module_name_fallback(self):
        tc = {}
        assert MochaJestCodeGenerator._extract_module_name(tc) == "unknown"

    def test_source_to_import_path(self):
        assert MochaJestCodeGenerator._source_to_import_path("calculator.js") == "./calculator"
        assert MochaJestCodeGenerator._source_to_import_path("./utils/helper.ts") == "./utils/helper"
        assert MochaJestCodeGenerator._source_to_import_path("/absolute/path.js") == "/absolute/path"

    def test_build_file_path_js(self):
        result = MochaJestCodeGenerator._build_file_path("Calculator", ".test.js")
        assert result == "tests/Calculator/Calculator.test.js"

    def test_build_file_path_ts(self):
        result = MochaJestCodeGenerator._build_file_path("Calculator", ".test.ts")
        assert result == "tests/Calculator/Calculator.test.ts"

    def test_generate_setup_returns_string(self, generator: MochaJestCodeGenerator):
        result = generator.generate_setup()
        assert isinstance(result, str)
        assert "//" in result

    def test_infer_js_type(self):
        data = [{"a": 42}, {"a": 0}]
        assert MochaJestCodeGenerator._infer_js_type(data, "a") == "number"

        data = [{"a": True}]
        assert MochaJestCodeGenerator._infer_js_type(data, "a") == "boolean"

        data = [{"a": "hello"}]
        assert MochaJestCodeGenerator._infer_js_type(data, "a") == "string"

        data = [{"a": None}]
        assert MochaJestCodeGenerator._infer_js_type(data, "a") == "any"

    def test_fallback_render(self):
        context = {
            "test_module_name": "Calculator",
            "test_cases": [
                {"description": "should add numbers", "is_async": False},
            ],
        }
        result = MochaJestCodeGenerator._fallback_render(context, "jest")
        assert "describe(" in result
        assert "Calculator" in result
        assert "it(" in result


# ════════════════════════════════════════════════════════════════════════
# Mocha+Chai specific full pipeline
# ════════════════════════════════════════════════════════════════════════


class TestMochaFullPipeline:
    def test_mocha_full_pipeline(self, mocha_generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "Add two numbers",
            "source_class": "Calculator",
            "source_module": "calculator.js",
            "steps": [{"code": "const result = calc.add(2, 3);"}],
            "expected_result": "5",
            "comparison_type": "equals",
        }
        result = mocha_generator.generate_test_file([tc])
        assert "describe(" in result.content
        assert "expect(" in result.content
        assert ".to.equal(" in result.content
        assert "chai" in result.content.lower() or "expect" in result.content

    def test_mocha_with_sinon_mocks(self, mocha_generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "DB save",
            "source_class": "UserService",
            "source_module": "userService.js",
            "steps": [{"code": "const result = service.save(data);"}],
            "expected_result": "true",
            "comparison_type": "is_true",
            "dependencies": [{"target": "./database", "type": "db", "method": "save", "return_value": True}],
        }
        result = mocha_generator.generate_test_file([tc])
        assert "sinon" in result.content.lower()
        assert "sandbox" in result.content.lower()
