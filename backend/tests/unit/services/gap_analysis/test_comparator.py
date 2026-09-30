"""Unit tests for ComparatorService — Epic 5, Story 5.1.

Tests the three fuzzy matching algorithms, score combination,
gap identification (missing, extra, different), and summary.
"""

import pytest

from app.services.analysis.gap_analyzer import CodeEntity
from app.services.gap_analysis.comparator import (
    ComparatorService,
    GapAnalysisSummaryData,
    RequirementData,
    _combine_scores,
    _jaro_winkler_match,
    _levenshtein_distance,
    _levenshtein_match,
    _tfidf_cosine_match,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _entity(
    name: str,
    etype: str = "function",
    file_path: str = "src/app.py",
    line_number: int = 10,
    language: str = "python",
    docstring: str | None = None,
) -> CodeEntity:
    return CodeEntity(
        entity_id=f"eid-{name}",
        name=name,
        type=etype,
        file_path=file_path,
        line_number=line_number,
        language=language,
        docstring=docstring,
    )


def _req(req_id: str, text: str, priority: str = "medium") -> RequirementData:
    return RequirementData(req_id=req_id, text=text, priority=priority)


# ── Levenshtein ─────────────────────────────────────────────────────────────


class TestLevenshtein:
    def test_distance_zero_for_identical(self):
        assert _levenshtein_distance("hello", "hello") == 0

    def test_distance_one_for_single_char_diff(self):
        assert _levenshtein_distance("cat", "cot") == 1

    def test_distance_full_insert(self):
        assert _levenshtein_distance("", "abc") == 3

    def test_match_exact_returns_100(self):
        assert _levenshtein_match("login", "login") == 100.0

    def test_match_typo_returns_high(self):
        score = _levenshtein_match("login", "logni")
        assert score > 50.0  # transposition = 2 edits, score = 60%

    def test_match_completely_different_returns_low(self):
        score = _levenshtein_match("abc", "xyz123456789")
        assert score < 30.0

    def test_match_normalizes_special_chars(self):
        score = _levenshtein_match("user-login", "userlogin")
        assert score == 100.0

    def test_match_empty_strings(self):
        assert _levenshtein_match("", "") == 0.0


# ── Jaro-Winkler ────────────────────────────────────────────────────────────


class TestJaroWinkler:
    def test_exact_match_returns_100(self):
        assert _jaro_winkler_match("authenticate", "authenticate") == 100.0

    def test_similar_names_high_score(self):
        score = _jaro_winkler_match("authenticate", "authenticat")
        assert score > 90.0

    def test_prefix_boost(self):
        # Names with common prefix should score higher than without
        score_prefix = _jaro_winkler_match("getUser", "getUserById")
        score_no_prefix = _jaro_winkler_match("getUser", "fetchUserById")
        assert score_prefix > score_no_prefix

    def test_no_similarity_returns_zero(self):
        score = _jaro_winkler_match("abc", "xyz")
        assert score < 30.0


# ── TF-IDF Cosine ───────────────────────────────────────────────────────────


class TestTFIDFCosine:
    def test_identical_text_returns_high(self):
        score = _tfidf_cosine_match(
            "user must login with password",
            "user must login with password",
        )
        assert score > 80.0

    def test_related_words_moderate(self):
        score = _tfidf_cosine_match(
            "system should authenticate users",
            "authenticate users in the system",
        )
        assert score > 40.0

    def test_no_overlap_returns_zero(self):
        score = _tfidf_cosine_match("hello world", "xyz 123")
        assert score == 0.0

    def test_empty_text_returns_zero(self):
        assert _tfidf_cosine_match("", "code") == 0.0
        assert _tfidf_cosine_match("req", "") == 0.0


# ── Combine scores ──────────────────────────────────────────────────────────


class TestCombineScores:
    def test_all_equal_returns_same(self):
        result = _combine_scores(80.0, 80.0, 80.0)
        assert result == pytest.approx(80.0, abs=0.1)

    def test_weights_sum_to_one(self):
        # Levenshtein 0.25, Jaro-Winkler 0.35, Semantic 0.40
        result = _combine_scores(100.0, 0.0, 0.0)
        assert result == pytest.approx(25.0, abs=0.1)

        result = _combine_scores(0.0, 100.0, 0.0)
        assert result == pytest.approx(35.0, abs=0.1)

        result = _combine_scores(0.0, 0.0, 100.0)
        assert result == pytest.approx(40.0, abs=0.1)

    def test_all_max_returns_100(self):
        assert _combine_scores(100.0, 100.0, 100.0) == pytest.approx(100.0)


# ── ComparatorService.compare() ─────────────────────────────────────────────


class TestComparatorCompare:
    def test_empty_inputs_returns_empty_findings(self):
        service = ComparatorService()
        findings, summary = service.compare([], [])
        assert len(findings) == 0
        assert summary.total_requirements == 0
        assert summary.total_code_entities == 0
        assert summary.coverage_percentage == 0.0

    def test_missing_requirement_when_no_code(self):
        """A requirement with no matching code → gap_type=missing."""
        service = ComparatorService()
        reqs = [_req("R1", "The system must implement user authentication")]
        findings, summary = service.compare(reqs, [])

        assert len(findings) == 1
        f = findings[0]
        assert f.gap_type == "missing"
        assert f.requirement_id == "R1"
        assert f.code_entity_id is None
        assert f.severity == "warning"
        assert summary.missing_count == 1

    def test_missing_requirement_high_priority_is_critical(self):
        service = ComparatorService()
        reqs = [_req("R1", "Security module for authentication", priority="high")]
        findings, summary = service.compare(reqs, [])

        assert findings[0].severity == "critical"

    def test_good_match_produces_no_gap(self):
        """A requirement with a strong code match → no finding."""
        service = ComparatorService()
        reqs = [_req("R1", "authenticate user login password")]
        entities = [_entity("authenticate", docstring="authenticate user login password")]
        findings, summary = service.compare(reqs, entities)

        # Should not produce a missing or different finding
        gap_types = [f.gap_type for f in findings]
        assert "missing" not in gap_types
        assert "different" not in gap_types

    def test_extra_code_entity_without_requirement(self):
        """Code entity with no matching requirement → gap_type=extra."""
        service = ComparatorService()
        reqs = [_req("R1", "user login authentication")]
        entities = [
            _entity("authenticate", docstring="user login authentication"),
            _entity("generate_invoice_pdf"),
        ]
        findings, summary = service.compare(reqs, entities)

        extra_findings = [f for f in findings if f.gap_type == "extra"]
        assert len(extra_findings) == 1
        assert extra_findings[0].code_entity_id == "eid-generate_invoice_pdf"
        assert extra_findings[0].severity == "info"
        assert summary.extra_count == 1

    def test_excluded_patterns_skip_extra(self):
        """Test functions, __init__, etc. should not be flagged as extra."""
        service = ComparatorService()
        reqs = [_req("R1", "user login authentication")]
        entities = [
            _entity("authenticate", docstring="user login authentication"),
            _entity("test_authentication"),
            _entity("__init__"),
            _entity("conftest_setup"),
        ]
        findings, summary = service.compare(reqs, entities)

        extra_findings = [f for f in findings if f.gap_type == "extra"]
        assert len(extra_findings) == 0

    def test_summary_coverage_calculation(self):
        """coverage = matched_reqs / total_reqs * 100."""
        service = ComparatorService()
        reqs = [
            _req("R1", "authenticate user login password"),
            _req("R2", "export data to PDF report"),
        ]
        entities = [
            _entity("authenticate", docstring="authenticate user login password"),
        ]
        findings, summary = service.compare(reqs, entities)

        # R1 matched (good match), R2 missing
        assert summary.total_requirements == 2
        assert summary.coverage_percentage == 50.0  # 1 of 2 matched

    def test_findings_have_match_scores(self):
        service = ComparatorService()
        reqs = [_req("R1", "authenticate user")]
        entities = [_entity("authenticate", docstring="authenticate user")]
        findings, summary = service.compare(reqs, entities)

        for f in findings:
            assert 0.0 <= f.match_score <= 100.0

    def test_context_contains_entity_info(self):
        service = ComparatorService()
        reqs = [_req("R1", "unique unknown feature zzz")]
        entities = [_entity("real_implementation")]
        findings, summary = service.compare(reqs, entities)

        missing = [f for f in findings if f.gap_type == "missing"][0]
        assert "best_candidate" in missing.context
        assert "best_score" in missing.context
