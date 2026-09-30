"""Unit + golden tests for unittest/TestNG/MSTest generators — Story 1.57.

Pokrywa §Testy: 1 (enumy na 4 warstwach), 2 (test case → kod unittest),
3 (TestNG: adnotacje + Assert), 4 (MSTest: atrybuty + Assert), 5 (golden
data — próbka wejściowa + oczekiwane wyjście per framework), 6 (smoke:
wygenerowany unittest uruchamialny przez ``python -m unittest``).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from app.models.test_case import TestFramework as ModelTestFramework
from app.services.generators.llm_test_generator import LLMTestFramework
from app.services.generators.native_test_generator import (
    TestFramework as GenTestFramework,
)
from app.services.test_generation.codegen import CodeGenRegistry

GOLDEN_DIR = Path(__file__).resolve().parents[3] / "golden_data" / "codegen"

CALCULATOR_ADD = {
    "title": "Dodawanie dwóch liczb dodatnich",
    "scenario_name": "Dodawanie liczb dodatnich",
    "description": "Sprawdza czy Calculator::add poprawnie dodaje liczby.",
    "test_type": "unit",
    "source_class": "Calculator",
    "source_function": "add",
    "test_data": {"sets": [{"a": 1, "b": 2, "expected": 3}]},
    "expected_result": "3",
    "comparison_type": "equals",
}

CALCULATOR_DIVIDE_ZERO = {
    "title": "Dzielenie przez zero",
    "scenario_name": "Dzielenie przez zero rzuca wyjątek",
    "description": "Sprawdza czy Calculator::divide rzuca wyjątek.",
    "test_type": "unit",
    "source_class": "Calculator",
    "source_function": "divide",
    "test_data": {"sets": [{"a": 1, "b": 0}]},
    "expected_result": "ValueError",
    "comparison_type": "throws",
}

SMOKE_CASE = {
    # Samowystarczalny: brak zewnętrznych importów — python -m unittest przechodzi.
    "title": "Smoke — suma literalna",
    "scenario_name": "Smoke suma",
    "description": "Wygenerowany test musi być uruchamialny.",
    "test_type": "unit",
    "steps": ["result = 2 + 3"],
    "expected_result": "5",
    "comparison_type": "equals",
}


# ── §Test 1 — enumy na 4 warstwach + rejestr ─────────────────────────────────


class TestXUnitEnums:
    def test_model_test_framework_has_new_entries(self):
        assert ModelTestFramework.UNITTEST == "unittest"
        assert ModelTestFramework.TESTNG == "testng"
        assert ModelTestFramework.MSTEST == "mstest"

    def test_native_generator_framework_has_new_entries(self):
        assert GenTestFramework.UNITTEST == "unittest"
        assert GenTestFramework.TESTNG == "testng"
        assert GenTestFramework.MSTEST == "mstest"

    def test_llm_test_framework_has_new_entries(self):
        assert LLMTestFramework.UNITTEST == "unittest"
        assert LLMTestFramework.TESTNG == "testng"
        assert LLMTestFramework.MSTEST == "mstest"

    def test_registry_has_new_generators(self):
        registry = CodeGenRegistry.get_instance()
        for fw in ("unittest", "testng", "mstest"):
            assert registry.is_supported(fw), f"Brak generatora {fw} w rejestrze"


def _generate(framework: str, test_cases: list[dict]):
    registry = CodeGenRegistry.get_instance()
    generator = registry.get_generator(framework)
    return generator.generate_test_file(test_cases)


# ── §Test 2 — unittest (Python) ──────────────────────────────────────────────


class TestUnittestGenerator:
    def test_generates_testcase_class_with_assert_equal(self):
        file = _generate("unittest", [CALCULATOR_ADD])

        assert file.framework == "unittest"
        assert file.language == "python"
        assert "import unittest" in file.content
        assert "class CalculatorTest(unittest.TestCase):" in file.content
        assert "self.assertEqual" in file.content
        assert file.file_path.endswith(".py")

    def test_compilation_via_py_compile(self):
        file = _generate("unittest", [CALCULATOR_ADD])

        assert file.compilation_result is not None
        assert file.compilation_result.success, file.compilation_result.error_message

    def test_throws_renders_assert_raises(self):
        file = _generate("unittest", [CALCULATOR_DIVIDE_ZERO])

        assert "self.assertRaises(ValueError)" in file.content

    def test_main_block_for_unittest_runner(self):
        file = _generate("unittest", [SMOKE_CASE])

        assert 'if __name__ == "__main__":' in file.content
        assert "unittest.main()" in file.content

    def test_smoke_generated_test_runs_green(self):
        """AC1: python -m unittest uruchamia wygenerowany kod z exit 0."""
        file = _generate("unittest", [SMOKE_CASE])

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "test_smoke_unittest_gen.py"
            target.write_text(file.content, encoding="utf-8")
            proc = subprocess.run(  # sys.executable + stała nazwa modułu — bezpośrednio kontrolowane
                [sys.executable, "-m", "unittest", "test_smoke_unittest_gen"],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        assert proc.returncode == 0, proc.stderr


# ── §Test 3 — TestNG (Java) ──────────────────────────────────────────────────


class TestTestNgGenerator:
    def test_generates_annotations_and_asserts(self):
        file = _generate("testng", [CALCULATOR_ADD])

        assert file.framework == "testng"
        assert file.language == "java"
        assert "import org.testng.annotations.Test;" in file.content
        assert "@Test" in file.content
        assert "Assert.assertEquals" in file.content
        assert "public class CalculatorTest" in file.content
        assert file.file_path.endswith(".java")

    def test_before_method_when_setup_present(self):
        file = _generate("testng", [CALCULATOR_ADD])

        # Instancja testowanej klasy → @BeforeMethod z inicjalizacją
        assert "@BeforeMethod" in file.content
        assert "new Calculator()" in file.content

    def test_throws_renders_assert_throws(self):
        file = _generate("testng", [CALCULATOR_DIVIDE_ZERO])

        assert "Assert.assertThrows" in file.content

    def test_structural_validation(self):
        file = _generate("testng", [CALCULATOR_ADD])

        assert file.compilation_result is not None
        assert file.compilation_result.success


# ── §Test 4 — MSTest (C#) ────────────────────────────────────────────────────


class TestMsTestGenerator:
    def test_generates_attributes_and_asserts(self):
        file = _generate("mstest", [CALCULATOR_ADD])

        assert file.framework == "mstest"
        assert file.language == "csharp"
        assert "using Microsoft.VisualStudio.TestTools.UnitTesting;" in file.content
        assert "[TestClass]" in file.content
        assert "[TestMethod]" in file.content
        assert "Assert.AreEqual" in file.content
        assert file.file_path.endswith(".cs")

    def test_test_initialize_when_setup_present(self):
        file = _generate("mstest", [CALCULATOR_ADD])

        assert "[TestInitialize]" in file.content
        assert "new Calculator()" in file.content

    def test_throws_renders_throws_exception(self):
        file = _generate("mstest", [CALCULATOR_DIVIDE_ZERO])

        assert "Assert.ThrowsException" in file.content

    def test_structural_validation(self):
        file = _generate("mstest", [CALCULATOR_ADD])

        assert file.compilation_result is not None
        assert file.compilation_result.success


# ── §Test 5 — golden data (próbka wejściowa + oczekiwane wyjście) ───────────


class TestGoldenOutputs:
    """AC5: stabilizacja wyjścia generatorów na golden próbkach."""

    def test_golden_unittest_output_matches(self):
        _assert_golden("unittest")

    def test_golden_testng_output_matches(self):
        _assert_golden("testng")

    def test_golden_mstest_output_matches(self):
        _assert_golden("mstest")


def _assert_golden(framework: str) -> None:
    import json

    package_dir = GOLDEN_DIR / framework
    input_spec = json.loads((package_dir / "input.json").read_text(encoding="utf-8"))
    expected = (package_dir / "expected_output.txt").read_text(encoding="utf-8")

    file = _generate(framework, [input_spec])
    normalized = _normalize(file.content)
    assert normalized == _normalize(expected), (
        f"Golden mismatch dla {framework} — zaktualizuj expected_output.txt jeśli zmiana wyjścia jest zamierzona"
    )


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())
