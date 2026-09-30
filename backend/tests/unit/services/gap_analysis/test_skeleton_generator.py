"""Unit tests for SkeletonGenerator — Epic 5, Story 5.6.

Tests template rendering for Python/TypeScript/Java/C#,
function name extraction, summary extraction, and edge cases.
"""

from types import SimpleNamespace

import pytest

from app.models.gap_finding import GapType
from app.services.gap_analysis.skeleton_generator import (
    SkeletonGenerator,
    SkeletonResult,
)


def _make_finding(
    gap_type: GapType = GapType.MISSING,
    requirement_text: str = "Funkcja calculateTax powinna obliczać podatek.",
    description: str = "Brak implementacji wymagania",
):
    return SimpleNamespace(
        gap_type=gap_type,
        requirement_text=requirement_text,
        description=description,
    )


# ── Python template ──────────────────────────────────────────────────────────


class TestPythonSkeleton:
    def test_generates_valid_python(self):
        gen = SkeletonGenerator()
        f = _make_finding()
        result = gen.generate(f, "python")
        assert "def " in result.code
        assert "NotImplementedError" in result.code
        assert result.language == "python"

    def test_function_name_from_requirement(self):
        gen = SkeletonGenerator()
        f = _make_finding(
            requirement_text="Funkcja validateUser powinna walidować dane użytkownika"
        )
        result = gen.generate(f, "python")
        assert result.function_name == "validateuser"
        assert "def validateuser(" in result.code

    def test_docstring_contains_summary(self):
        gen = SkeletonGenerator()
        f = _make_finding(
            requirement_text="System powinien wysyłać powiadomienia email po rejestracji"
        )
        result = gen.generate(f, "python")
        assert "wysyłać powiadomienia" in result.code or "powiadomienia" in result.code


# ── Other languages ─────────────────────────────────────────────────────────


class TestOtherLanguages:
    def test_typescript_template(self):
        gen = SkeletonGenerator()
        f = _make_finding()
        result = gen.generate(f, "typescript")
        assert "export function" in result.code
        assert "throw new Error" in result.code
        assert result.language == "typescript"

    def test_java_template(self):
        gen = SkeletonGenerator()
        f = _make_finding()
        result = gen.generate(f, "java")
        assert "public " in result.code
        assert "UnsupportedOperationException" in result.code
        assert result.language == "java"

    def test_csharp_template(self):
        gen = SkeletonGenerator()
        f = _make_finding()
        result = gen.generate(f, "csharp")
        assert "public" in result.code
        assert "NotImplementedException" in result.code
        assert result.language == "csharp"

    def test_unsupported_language_returns_error(self):
        gen = SkeletonGenerator()
        f = _make_finding()
        result = gen.generate(f, "ruby")
        assert result.code == ""
        assert result.error is not None
        assert "ruby" in result.error


# ── Function name extraction ────────────────────────────────────────────────


class TestFunctionNameExtraction:
    def test_english_function_pattern(self):
        gen = SkeletonGenerator()
        f = _make_finding(
            requirement_text="The function processData should handle input validation"
        )
        result = gen.generate(f, "python")
        assert result.function_name == "processdata"

    def test_polish_metoda_pattern(self):
        gen = SkeletonGenerator()
        f = _make_finding(
            requirement_text="Metoda authenticate weryfikuje tożsamość użytkownika"
        )
        result = gen.generate(f, "python")
        assert result.function_name == "authenticate"

    def test_fallback_first_significant_word(self):
        gen = SkeletonGenerator()
        f = _make_finding(
            requirement_text="Login powinien działać poprawnie po wdrożeniu"
        )
        result = gen.generate(f, "python")
        assert result.function_name == "login"

    def test_empty_text_uses_default(self):
        gen = SkeletonGenerator()
        f = _make_finding(requirement_text="", description="")
        result = gen.generate(f, "python")
        assert result.function_name == "implement_requirement"

    def test_name_is_valid_identifier(self):
        gen = SkeletonGenerator()
        f = _make_finding(
            requirement_text="Funkcja process-user-data powinna działać"
        )
        result = gen.generate(f, "python")
        # Should sanitize special chars
        assert result.function_name.replace("_", "").isalnum()


# ── Batch generation ─────────────────────────────────────────────────────────


class TestBatchGeneration:
    def test_only_missing_gaps_processed(self):
        gen = SkeletonGenerator()
        findings = [
            _make_finding(GapType.MISSING, "Funkcja alpha"),
            _make_finding(GapType.DIFFERENT, "Funkcja beta"),
            _make_finding(GapType.EXTRA, "Funkcja gamma"),
            _make_finding(GapType.MISSING, "Funkcja delta"),
        ]
        results = gen.generate_batch(findings, "python")
        assert len(results) == 2
        assert all(r.language == "python" for r in results)

    def test_empty_list_returns_empty(self):
        gen = SkeletonGenerator()
        assert gen.generate_batch([], "python") == []


# ── Summary extraction ──────────────────────────────────────────────────────


class TestSummaryExtraction:
    def test_truncates_long_text(self):
        gen = SkeletonGenerator()
        long_text = "To jest bardzo długi tekst wymagania " * 20
        f = _make_finding(requirement_text=long_text)
        result = gen.generate(f, "python")
        # The summary inside the code should be truncated
        assert "..." in result.code

    def test_first_sentence_only(self):
        gen = SkeletonGenerator()
        f = _make_finding(
            requirement_text="Pierwsze zdanie. Drugie zdanie nie powinno być w summary."
        )
        result = gen.generate(f, "python")
        assert "Pierwsze zdanie" in result.code
        assert "Drugie zdanie" not in result.code
