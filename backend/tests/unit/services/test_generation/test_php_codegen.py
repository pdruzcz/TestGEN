"""Unit tests for PHPUnit/Pest code generators — Story 1.55 (FR24/FR12).

Pokrywa §Testy 1 (enumy), 2 (test case → kod PHPUnit), 3 (Pest DSL:
``it()`` + ``expect()->toBe()``), 4 (składnia PHP — ``php -l`` jeśli dostępny,
inaczej walidacja statyczna) oraz setup/teardown i namespace'y.
"""

from __future__ import annotations

import shutil

import pytest

from app.models.test_case import TestFramework as ModelTestFramework
from app.services.generators.llm_test_generator import LLMTestFramework
from app.services.generators.native_test_generator import (
    TestFramework as GenTestFramework,
)
from app.services.test_generation.codegen import CodeGenConfig, CodeGenRegistry
from app.services.test_generation.codegen.phpunit_generator import (
    PestCodeGenerator,
    PhpUnitCodeGenerator,
)

CALCULATOR_ADD = {
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
}

CALCULATOR_DIVIDE_ZERO = {
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
}

USER_CREATE = {
    "title": "Tworzenie użytkownika",
    "scenario_name": "Utwórz poprawnego użytkownika",
    "description": "Sprawdza czy UserService::create_user zwraca użytkownika.",
    "test_type": "unit",
    "source_file": "app/Services/UserService.php",
    "source_class": "UserService",
    "source_function": "create_user",
    "test_data": {"sets": [{"username": "alice", "email": "alice@test.com"}]},
    "expected_result": "True",
    "comparison_type": "is_not_none",
}


# ── §Test 1 — enumy na 4 warstwach ──────────────────────────────────────────


class TestPhpEnums:
    def test_model_test_framework_has_php_entries(self):
        assert ModelTestFramework.PHPUNIT == "phpunit"
        assert ModelTestFramework.PEST == "pest"

    def test_native_generator_framework_has_php_entries(self):
        assert GenTestFramework.PHPUNIT == "phpunit"
        assert GenTestFramework.PEST == "pest"

    def test_llm_test_framework_has_php_entries(self):
        assert LLMTestFramework.PHPUNIT == "phpunit"
        assert LLMTestFramework.PEST == "pest"

    def test_registry_supports_php_frameworks(self):
        registry = CodeGenRegistry.get_instance()
        assert registry.is_supported("phpunit")
        assert registry.is_supported("pest")


# ── §Test 2 — generator natywny: test case → kod PHPUnit ────────────────────


class TestPhpUnitGenerator:
    def test_generates_class_extending_testcase(self):
        result = PhpUnitCodeGenerator().generate_test_file([CALCULATOR_ADD])
        assert result.content.lstrip().startswith("<?php")
        assert "use PHPUnit\\Framework\\TestCase;" in result.content
        assert "final class CalculatorTest extends TestCase" in result.content
        assert "public function test" in result.content

    def test_generates_assert_same_with_data_set(self):
        result = PhpUnitCodeGenerator().generate_test_file([CALCULATOR_ADD])
        assert "$calculator = new Calculator();" in result.content
        assert "$result = $calculator->add(1, 2);" in result.content
        assert "$this->assertSame(3, $result);" in result.content

    def test_throws_generates_expect_exception(self):
        result = PhpUnitCodeGenerator().generate_test_file([CALCULATOR_DIVIDE_ZERO])
        assert "$this->expectException(InvalidArgumentException::class);" in result.content

    def test_metadata_framework_language(self):
        result = PhpUnitCodeGenerator().generate_test_file([CALCULATOR_ADD])
        assert result.framework == "phpunit"
        assert result.language == "php"
        assert result.file_path.endswith("CalculatorTest.php")
        assert result.file_path.startswith("tests/")

    def test_default_namespace_tests_feature(self):
        result = PhpUnitCodeGenerator().generate_test_file([CALCULATOR_ADD])
        assert "namespace Tests\\Feature;" in result.content

    def test_namespace_override_via_project_context(self):
        config = CodeGenConfig(project_context={"php_namespace": "App\\Tests"})
        result = PhpUnitCodeGenerator().generate_test_file([CALCULATOR_ADD], config)
        assert "namespace App\\Tests;" in result.content

    def test_namespace_symfony_convention(self):
        config = CodeGenConfig(project_context={"php_app": "symfony"})
        result = PhpUnitCodeGenerator().generate_test_file([CALCULATOR_ADD], config)
        assert "namespace App\\Tests;" in result.content

    def test_multiple_cases_generate_multiple_methods(self):
        result = PhpUnitCodeGenerator().generate_test_file([CALCULATOR_ADD, CALCULATOR_DIVIDE_ZERO, USER_CREATE])
        assert len(result.test_functions) == 3

    def test_setup_contains_set_up_and_tear_down(self):
        setup = PhpUnitCodeGenerator().generate_setup({})
        assert "protected function setUp(): void" in setup
        assert "tearDown" in setup

    def test_generate_assertion_phpunit_style(self):
        assertion = PhpUnitCodeGenerator().generate_assertion("3", "$result", "equals")
        assert assertion == "$this->assertSame(3, $result);"

    def test_empty_input_returns_placeholder(self):
        result = PhpUnitCodeGenerator().generate_test_file([])
        assert "<?php" in result.content
        assert result.framework == "phpunit"
        assert result.language == "php"


# ── §Test 3 — Pest DSL ───────────────────────────────────────────────────────


class TestPestGenerator:
    def test_generates_it_closure(self):
        result = PestCodeGenerator().generate_test_file([CALCULATOR_ADD])
        assert result.content.lstrip().startswith("<?php")
        assert "it(" in result.content
        assert "function ()" in result.content

    def test_generates_expect_to_be(self):
        result = PestCodeGenerator().generate_test_file([CALCULATOR_ADD])
        assert "$calculator = new Calculator();" in result.content
        assert "$result = $calculator->add(1, 2);" in result.content
        assert "expect($result)->toBe(3);" in result.content

    def test_throws_generates_to_throw(self):
        result = PestCodeGenerator().generate_test_file([CALCULATOR_DIVIDE_ZERO])
        assert "->toThrow(InvalidArgumentException::class);" in result.content

    def test_metadata_framework_language(self):
        result = PestCodeGenerator().generate_test_file([CALCULATOR_ADD])
        assert result.framework == "pest"
        assert result.language == "php"
        assert result.file_path.endswith(".php")

    def test_setup_contains_before_each(self):
        setup = PestCodeGenerator().generate_setup({})
        assert "beforeEach(" in setup

    def test_generate_assertion_pest_style(self):
        assertion = PestCodeGenerator().generate_assertion("3", "$result", "equals")
        assert assertion == "expect($result)->toBe(3);"

    def test_registry_routes_php_generators(self):
        registry = CodeGenRegistry.get_instance()
        assert isinstance(registry.get_generator("phpunit"), PhpUnitCodeGenerator)
        assert isinstance(registry.get_generator("pest"), PestCodeGenerator)


# ── §Test 4 — składnia PHP ───────────────────────────────────────────────────


class TestPhpSyntaxValidation:
    def test_valid_phpunit_code_passes_validation(self):
        result = PhpUnitCodeGenerator().generate_test_file([CALCULATOR_ADD])
        assert result.compilation_result is not None
        assert result.compilation_result.success, result.compilation_result.error_message

    def test_valid_pest_code_passes_validation(self):
        result = PestCodeGenerator().generate_test_file([CALCULATOR_DIVIDE_ZERO])
        assert result.compilation_result is not None
        assert result.compilation_result.success, result.compilation_result.error_message

    def test_code_without_php_tag_fails(self):
        gen = PhpUnitCodeGenerator()
        bad = gen.validate_syntax("echo 'no tag';\n")
        assert bad.success is False

    def test_code_with_unbalanced_braces_fails(self):
        gen = PestCodeGenerator()
        bad = gen.validate_syntax("<?php\nit('x', function () {\n")
        assert bad.success is False

    @pytest.mark.skipif(shutil.which("php") is None, reason="php CLI niedostępny")
    def test_php_lint_available_and_used(self):
        gen = PhpUnitCodeGenerator()
        assert gen._php_binary is not None
        result = gen.validate_syntax("<?php\n$x = 1;\n")
        assert result.success is True
