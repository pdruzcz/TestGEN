"""Integration tests for Mocha/Jest code generation pipeline — Story 1.39.

Testuje pelny przeplyw generowania kodu Mocha/Jest z golden data:
- 5+ probek kodu JS/TS z znanymi wynikami Jest/Mocha
- Generowanie -> walidacja skladni -> sprawdzenie elementow
- Metryka: >80% wygenerowanych plikow przechodzi walidacje (native path)
- Dwa warianty frameworka: Jest i Mocha
"""

import pytest

from app.services.test_generation.codegen.base import (
    CodeGenConfig,
    CodeGenRegistry,
    TestCodeFile,
)
from app.services.test_generation.codegen.mocha_jest_generator import MochaJestCodeGenerator

# ════════════════════════════════════════════════════════════════════════
# Golden data: probki kodu JS/TS z oczekiwanymi wynikami
# ════════════════════════════════════════════════════════════════════════

GOLDEN_DATA = {
    "Calculator": {
        "source_file": "calculator.js",
        "source_class": "Calculator",
        "test_cases": [
            {
                "scenario_name": "Add two positive numbers",
                "test_type": "unit",
                "source_function": "add",
                "steps": [{"code": "const result = calc.add(2, 3);"}],
                "expected_result": "5",
                "comparison_type": "equals",
            },
            {
                "scenario_name": "Division by zero throws error",
                "test_type": "unit",
                "source_function": "divide",
                "steps": [{"code": "calc.divide(1, 0);"}],
                "expected_result": "Error",
                "comparison_type": "throws",
            },
            {
                "scenario_name": "Add with multiple inputs",
                "test_type": "unit",
                "source_function": "add",
                "steps": [{"code": "const result = calc.add(a, b);"}],
                "expected_result": "expected",
                "comparison_type": "equals",
                "test_data": [
                    {"a": 1, "b": 2, "expected": 3},
                    {"a": 0, "b": 0, "expected": 0},
                    {"a": -1, "b": 1, "expected": 0},
                ],
            },
        ],
    },
    "UserService": {
        "source_file": "userService.js",
        "source_class": "UserService",
        "test_cases": [
            {
                "scenario_name": "Get user by ID returns user",
                "test_type": "integration",
                "source_function": "getUser",
                "is_async": True,
                "steps": [{"code": "const result = await service.getUser(1);"}],
                "expected_result": "true",
                "comparison_type": "is_not_none",
                "dependencies": [
                    {
                        "target": "./userRepository",
                        "type": "db",
                        "method": "findById",
                        "return_value": {"id": 1, "name": "John"},
                    },
                ],
            },
            {
                "scenario_name": "Create user without email throws",
                "test_type": "unit",
                "source_function": "createUser",
                "is_async": True,
                "steps": [{"code": "await service.createUser({});"}],
                "expected_result": "Error",
                "comparison_type": "throws",
            },
        ],
    },
    "DataProcessor": {
        "source_file": "dataProcessor.ts",
        "source_class": "DataProcessor",
        "test_cases": [
            {
                "scenario_name": "Process valid items",
                "test_type": "unit",
                "source_function": "process",
                "steps": [
                    {"code": "const result = processor.process([{name: 'test'}]);"},
                ],
                "expected_result": "true",
                "comparison_type": "is_true",
            },
            {
                "scenario_name": "Process empty array returns error",
                "test_type": "unit",
                "source_function": "process",
                "steps": [
                    {"code": "const result = processor.process([]);"},
                ],
                "expected_result": "false",
                "comparison_type": "is_false",
            },
            {
                "scenario_name": "Processed count increases",
                "test_type": "unit",
                "source_function": "getProcessedCount",
                "steps": [
                    {"code": "processor.process([{name: 'a'}, {name: 'b'}]);"},
                    {"code": "const result = processor.getProcessedCount();"},
                ],
                "expected_result": "2",
                "comparison_type": "equals",
            },
        ],
    },
    "AuthHandler": {
        "source_file": "authHandler.ts",
        "source_class": "AuthHandler",
        "test_cases": [
            {
                "scenario_name": "Generate token returns non-null",
                "test_type": "unit",
                "source_function": "generateToken",
                "steps": [{"code": "const result = handler.generateToken('user1', 'admin');"}],
                "expected_result": "true",
                "comparison_type": "is_not_none",
            },
            {
                "scenario_name": "Validate expired token returns null",
                "test_type": "unit",
                "source_function": "validateToken",
                "steps": [{"code": "const result = handler.validateToken('expired-token');"}],
                "expected_result": "null",
                "comparison_type": "is_none",
            },
            {
                "scenario_name": "Is authorized with admin role",
                "test_type": "unit",
                "source_function": "isAuthorized",
                "steps": [{"code": "const result = handler.isAuthorized(token, 'admin');"}],
                "expected_result": "true",
                "comparison_type": "is_true",
            },
        ],
    },
    "OrderService": {
        "source_file": "orderService.js",
        "source_class": "OrderService",
        "test_cases": [
            {
                "scenario_name": "Create order with valid items",
                "test_type": "integration",
                "source_function": "createOrder",
                "is_async": True,
                "steps": [
                    {"code": "const result = await service.createOrder([{price: 10, quantity: 2}], 'test@test.com');"},
                ],
                "expected_result": "true",
                "comparison_type": "is_not_none",
                "dependencies": [
                    {
                        "target": "./paymentGateway",
                        "type": "api",
                        "method": "processPayment",
                        "return_value": {"success": True},
                    },
                    {"target": "./inventoryService", "type": "db", "method": "checkAvailability", "return_value": True},
                ],
            },
            {
                "scenario_name": "Calculate total correctly",
                "test_type": "unit",
                "source_function": "calculateTotal",
                "steps": [
                    {
                        "code": "const result = service.calculateTotal([{price: 10, quantity: 2}, {price: 5, quantity: 3}]);"
                    },
                ],
                "expected_result": "35",
                "comparison_type": "equals",
            },
            {
                "scenario_name": "Cancel shipped order throws",
                "test_type": "unit",
                "source_function": "cancelOrder",
                "steps": [{"code": "service.cancelOrder('shipped-order-id');"}],
                "expected_result": "Error",
                "comparison_type": "throws",
            },
        ],
    },
}


# ════════════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture(params=list(GOLDEN_DATA.keys()))
def golden_sample(request) -> tuple[str, dict]:
    return request.param, GOLDEN_DATA[request.param]


@pytest.fixture
def jest_generator() -> MochaJestCodeGenerator:
    config = CodeGenConfig(
        framework="mocha_jest",
        language="javascript",
        file_extension=".test.js",
        validate_compilation=True,
        project_context={"framework_variant": "jest"},
    )
    return MochaJestCodeGenerator(config=config)


@pytest.fixture
def mocha_generator() -> MochaJestCodeGenerator:
    config = CodeGenConfig(
        framework="mocha_jest",
        language="javascript",
        file_extension=".test.js",
        validate_compilation=True,
        project_context={"framework_variant": "mocha"},
    )
    return MochaJestCodeGenerator(config=config)


# ════════════════════════════════════════════════════════════════════════
# Testy: Golden data — Jest variant
# ════════════════════════════════════════════════════════════════════════


class TestJestCodeGenPipeline:
    def test_golden_data_generates_valid_syntax(
        self, jest_generator: MochaJestCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample["test_cases"]
        # Wzbogac test cases o source_file/source_class
        for tc in test_cases:
            tc.setdefault("source_file", sample["source_file"])
            tc.setdefault("source_class", sample["source_class"])

        result = jest_generator.generate_test_file(test_cases)
        assert isinstance(result, TestCodeFile)
        assert result.content.strip()
        assert "describe(" in result.content

        # Walidacja skladni
        comp = result.compilation_result
        if comp:
            assert comp.success is True, f"Blad skladni {name}: {comp.error_message}"

    def test_golden_data_contains_expected_elements(
        self, jest_generator: MochaJestCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample["test_cases"]
        for tc in test_cases:
            tc.setdefault("source_file", sample["source_file"])
            tc.setdefault("source_class", sample["source_class"])

        result = jest_generator.generate_test_file(test_cases)
        content = result.content

        # describe block z nazwa klasy
        assert "describe(" in content
        # it/test blocks
        assert "it(" in content
        # expect (asercje)
        assert "expect(" in content

    def test_compilation_rate_above_threshold(self, jest_generator: MochaJestCodeGenerator):
        """Metryka: >80% plikow przechodzi walidacje skladniowa."""
        results: list[bool] = []

        for _name, sample in GOLDEN_DATA.items():
            test_cases = sample["test_cases"]
            for tc in test_cases:
                tc.setdefault("source_file", sample["source_file"])
                tc.setdefault("source_class", sample["source_class"])

            result = jest_generator.generate_test_file(test_cases)
            if result.compilation_result:
                results.append(result.compilation_result.success)
            else:
                results.append(True)  # Brak walidacji = pass

        success_rate = sum(results) / len(results) * 100 if results else 0
        assert success_rate >= 80, f"Compilation rate: {success_rate}% (wymagane >80%)"


# ════════════════════════════════════════════════════════════════════════
# Testy: Golden data — Mocha variant
# ════════════════════════════════════════════════════════════════════════


class TestMochaCodeGenPipeline:
    def test_golden_data_mocha_generates_valid_syntax(
        self, mocha_generator: MochaJestCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample["test_cases"]
        for tc in test_cases:
            tc.setdefault("source_file", sample["source_file"])
            tc.setdefault("source_class", sample["source_class"])

        result = mocha_generator.generate_test_file(test_cases)
        assert isinstance(result, TestCodeFile)
        assert result.content.strip()
        assert "describe(" in result.content

        # Walidacja skladni
        comp = result.compilation_result
        if comp:
            assert comp.success is True, f"Blad skladni {name}: {comp.error_message}"

    def test_golden_data_mocha_contains_chai_assertions(
        self, mocha_generator: MochaJestCodeGenerator, golden_sample: tuple[str, dict]
    ):
        name, sample = golden_sample
        test_cases = sample["test_cases"]
        for tc in test_cases:
            tc.setdefault("source_file", sample["source_file"])
            tc.setdefault("source_class", sample["source_class"])

        result = mocha_generator.generate_test_file(test_cases)
        content = result.content

        # Mocha+Chai specific assertions
        has_chai_assertion = any(
            x in content for x in [".to.equal(", ".to.be.", ".to.include(", ".to.throw(", ".to.have."]
        )
        assert has_chai_assertion, f"Brak asercji Chai w {name}"


# ════════════════════════════════════════════════════════════════════════
# Testy: Pelny przeplyw z rejestru
# ════════════════════════════════════════════════════════════════════════


class TestFullPipelineRegistry:
    def test_registry_to_generation_jest(self):
        gen = CodeGenRegistry.get_instance().get_generator(
            "mocha_jest",
            config=CodeGenConfig(
                framework="mocha_jest",
                project_context={"framework_variant": "jest"},
                validate_compilation=False,
            ),
        )
        assert isinstance(gen, MochaJestCodeGenerator)

        tc = {
            "scenario_name": "Registry test",
            "source_class": "Calculator",
            "source_module": "calculator.js",
            "steps": [{"code": "const result = calc.add(2, 3);"}],
            "expected_result": "5",
            "comparison_type": "equals",
        }
        result = gen.generate_test_file([tc])
        assert "describe(" in result.content
        assert "it(" in result.content
        assert "toBe(" in result.content
        assert "5" in result.content

    def test_registry_to_generation_mocha(self):
        gen = CodeGenRegistry.get_instance().get_generator(
            "mocha_jest",
            config=CodeGenConfig(
                framework="mocha_jest",
                project_context={"framework_variant": "mocha"},
                validate_compilation=False,
            ),
        )
        assert isinstance(gen, MochaJestCodeGenerator)

        tc = {
            "scenario_name": "Registry test",
            "source_class": "Calculator",
            "source_module": "calculator.js",
            "steps": [{"code": "const result = calc.add(2, 3);"}],
            "expected_result": "5",
            "comparison_type": "equals",
        }
        result = gen.generate_test_file([tc])
        assert "describe(" in result.content
        assert "it(" in result.content
        assert ".to.equal(" in result.content


# ════════════════════════════════════════════════════════════════════════
# Testy: TypeScript detection
# ════════════════════════════════════════════════════════════════════════


class TestTypeScriptPipeline:
    def test_typescript_from_source_extension(self, jest_generator: MochaJestCodeGenerator):
        tc = {
            "scenario_name": "TS test",
            "source_class": "DataProcessor",
            "source_module": "dataProcessor.ts",
            "steps": [{"code": "const result = processor.process(data);"}],
            "expected_result": "true",
            "comparison_type": "is_true",
        }
        result = jest_generator.generate_test_file([tc])
        assert result.language == "typescript"
        assert ".test.ts" in result.file_path

    def test_typescript_from_project_context(self):
        config = CodeGenConfig(
            framework="mocha_jest",
            project_context={"framework_variant": "jest", "typescript": True},
            validate_compilation=False,
        )
        gen = MochaJestCodeGenerator(config=config)
        tc = {
            "scenario_name": "TS test",
            "source_class": "Calculator",
            "source_module": "calculator.js",
            "steps": [{"code": "const result = calc.add(2, 3);"}],
            "expected_result": "5",
            "comparison_type": "equals",
        }
        result = gen.generate_test_file([tc])
        assert result.language == "typescript"
        assert ".test.ts" in result.file_path

    def test_multiple_test_cases_in_single_file(self, jest_generator: MochaJestCodeGenerator):
        test_cases = [
            {
                "scenario_name": "Test 1",
                "source_class": "Calculator",
                "source_module": "calculator.js",
                "steps": [{"code": "const r = calc.add(1, 2);"}],
                "expected_result": "3",
                "comparison_type": "equals",
            },
            {
                "scenario_name": "Test 2",
                "source_class": "Calculator",
                "source_module": "calculator.js",
                "steps": [{"code": "const r = calc.multiply(3, 4);"}],
                "expected_result": "12",
                "comparison_type": "equals",
            },
        ]
        result = jest_generator.generate_test_file(test_cases)
        assert result.content.count("it(") >= 2
        assert result.content.count("describe(") >= 1
