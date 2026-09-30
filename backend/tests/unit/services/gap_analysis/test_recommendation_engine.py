"""Unit tests for RecommendationEngine — Epic 5, Story 5.5.

Tests priority mapping, confidence scoring, template text generation,
sorting (priority then confidence), and edge cases.
"""

from types import SimpleNamespace

import pytest

from app.models.code_error import ErrorCategory
from app.models.gap_finding import GapType
from app.models.recommendation import RecommendationPriority
from app.services.gap_analysis.recommendation_engine import (
    GeneratedRecommendation,
    RecommendationEngine,
)


def _make_finding(
    gap_type: GapType = GapType.MISSING,
    severity: str = "warning",
    match_score: float = 50.0,
    requirement_id: str | None = "REQ-001",
    code_entity_id: str | None = None,
    code_reference: str | None = None,
    fid: str = "00000000-0000-0000-0000-000000000001",
):
    return SimpleNamespace(
        id=fid,
        gap_type=gap_type,
        severity=severity,
        match_score=match_score,
        requirement_id=requirement_id,
        code_entity_id=code_entity_id,
        code_reference=code_reference,
    )


def _make_error(
    category: ErrorCategory = ErrorCategory.SYNTAX,
    severity: str = "critical",
    message: str = "Unexpected token",
    file_path: str | None = "src/app.py",
    line_start: int | None = 10,
    rule_id: str | None = "SYNTAX001",
    suggestion: str | None = None,
    eid: str = "00000000-0000-0000-0000-000000000002",
):
    return SimpleNamespace(
        id=eid,
        category=category,
        severity=severity,
        message=message,
        file_path=file_path,
        line_start=line_start,
        rule_id=rule_id,
        suggestion=suggestion,
    )


# ── Gap-based recommendations ────────────────────────────────────────────────


class TestGapFindingRecommendations:
    def test_missing_maps_to_p1(self):
        engine = RecommendationEngine()
        f = _make_finding(GapType.MISSING, "critical")
        recs = engine.generate_from_gap_findings([f])
        assert len(recs) == 1
        assert recs[0].priority == RecommendationPriority.P1
        assert recs[0].source_type == "gap_finding"

    def test_inconsistent_maps_to_p1(self):
        engine = RecommendationEngine()
        f = _make_finding(GapType.INCONSISTENT, "critical")
        recs = engine.generate_from_gap_findings([f])
        assert recs[0].priority == RecommendationPriority.P1

    def test_different_maps_to_p2(self):
        engine = RecommendationEngine()
        f = _make_finding(GapType.DIFFERENT, "warning")
        recs = engine.generate_from_gap_findings([f])
        assert recs[0].priority == RecommendationPriority.P2

    def test_extra_maps_to_p4(self):
        engine = RecommendationEngine()
        f = _make_finding(
            GapType.EXTRA, "info", code_entity_id="UserService.login"
        )
        recs = engine.generate_from_gap_findings([f])
        assert recs[0].priority == RecommendationPriority.P4

    def test_confidence_in_range(self):
        engine = RecommendationEngine()
        f = _make_finding(GapType.MISSING, "critical", match_score=90.0)
        recs = engine.generate_from_gap_findings([f])
        assert 0.0 <= recs[0].confidence <= 1.0

    def test_critical_severity_higher_confidence_than_info(self):
        engine = RecommendationEngine()
        f_crit = _make_finding(GapType.MISSING, "critical", match_score=80.0)
        f_info = _make_finding(GapType.MISSING, "info", match_score=80.0)
        recs = engine.generate_from_gap_findings([f_crit, f_info])
        assert recs[0].confidence > recs[1].confidence

    def test_template_text_is_polish(self):
        engine = RecommendationEngine()
        f = _make_finding(GapType.MISSING, "warning")
        recs = engine.generate_from_gap_findings([f])
        assert "Brak" in recs[0].title or "implementacji" in recs[0].description

    def test_suggestion_present(self):
        engine = RecommendationEngine()
        f = _make_finding(GapType.DIFFERENT, "warning")
        recs = engine.generate_from_gap_findings([f])
        assert recs[0].suggestion is not None
        assert len(recs[0].suggestion) > 10

    def test_gap_finding_id_propagated(self):
        engine = RecommendationEngine()
        f = _make_finding(fid="11111111-1111-1111-1111-111111111111")
        recs = engine.generate_from_gap_findings([f])
        assert recs[0].gap_finding_id == "11111111-1111-1111-1111-111111111111"

    def test_context_contains_gap_type(self):
        engine = RecommendationEngine()
        f = _make_finding(GapType.MISSING, "critical")
        recs = engine.generate_from_gap_findings([f])
        assert recs[0].context["gap_type"] == "missing"

    def test_empty_findings_returns_empty(self):
        engine = RecommendationEngine()
        assert engine.generate_from_gap_findings([]) == []


# ── Code error recommendations ───────────────────────────────────────────────


class TestCodeErrorRecommendations:
    def test_syntax_maps_to_p1(self):
        engine = RecommendationEngine()
        e = _make_error(ErrorCategory.SYNTAX, "critical")
        recs = engine.generate_from_code_errors([e])
        assert recs[0].priority == RecommendationPriority.P1

    def test_logic_maps_to_p2(self):
        engine = RecommendationEngine()
        e = _make_error(ErrorCategory.LOGIC, "warning")
        recs = engine.generate_from_code_errors([e])
        assert recs[0].priority == RecommendationPriority.P2

    def test_semantic_maps_to_p3(self):
        engine = RecommendationEngine()
        e = _make_error(ErrorCategory.SEMANTIC, "warning")
        recs = engine.generate_from_code_errors([e])
        assert recs[0].priority == RecommendationPriority.P3

    def test_conformance_maps_to_p3(self):
        engine = RecommendationEngine()
        e = _make_error(ErrorCategory.CONFORMANCE, "info")
        recs = engine.generate_from_code_errors([e])
        assert recs[0].priority == RecommendationPriority.P3

    def test_confidence_in_range(self):
        engine = RecommendationEngine()
        e = _make_error(ErrorCategory.SYNTAX, "critical")
        recs = engine.generate_from_code_errors([e])
        assert 0.0 <= recs[0].confidence <= 1.0

    def test_syntax_rule_higher_confidence(self):
        """Syntax rules with SYNTAX prefix get higher rule confidence."""
        engine = RecommendationEngine()
        e_syntax = _make_error(
            ErrorCategory.SYNTAX, "warning", rule_id="SYNTAX001",
            eid="33333333-3333-3333-3333-333333333333",
        )
        e_logic = _make_error(
            ErrorCategory.LOGIC, "warning", rule_id="LOGIC001",
            eid="44444444-4444-4444-4444-444444444444",
        )
        recs = engine.generate_from_code_errors([e_syntax, e_logic])
        syntax_rec = [r for r in recs if r.code_error_id == e_syntax.id][0]
        logic_rec = [r for r in recs if r.code_error_id == e_logic.id][0]
        assert syntax_rec.confidence > logic_rec.confidence

    def test_error_suggestion_used_over_template(self):
        engine = RecommendationEngine()
        e = _make_error(
            ErrorCategory.SYNTAX,
            suggestion="Dodaj średnik na końcu linii",
        )
        recs = engine.generate_from_code_errors([e])
        assert "średnik" in recs[0].suggestion

    def test_code_error_id_propagated(self):
        engine = RecommendationEngine()
        e = _make_error(eid="22222222-2222-2222-2222-222222222222")
        recs = engine.generate_from_code_errors([e])
        assert recs[0].code_error_id == "22222222-2222-2222-2222-222222222222"

    def test_empty_errors_returns_empty(self):
        engine = RecommendationEngine()
        assert engine.generate_from_code_errors([]) == []


# ── Combined generate() ─────────────────────────────────────────────────────


class TestCombinedGenerate:
    def test_sorted_by_priority_then_confidence(self):
        engine = RecommendationEngine()
        f_missing = _make_finding(
            GapType.MISSING, "critical", match_score=95.0,
            fid="aaaaaaaa-0000-0000-0000-000000000001",
        )
        f_extra = _make_finding(
            GapType.EXTRA, "info", match_score=10.0,
            fid="aaaaaaaa-0000-0000-0000-000000000002",
        )
        f_diff = _make_finding(
            GapType.DIFFERENT, "warning", match_score=60.0,
            fid="aaaaaaaa-0000-0000-0000-000000000003",
        )

        recs = engine.generate(findings=[f_missing, f_extra, f_diff])
        priorities = [r.priority.value for r in recs]
        # P1 should come before P2, P4 should be last
        assert priorities[0] == "P1"
        assert priorities[-1] == "P4"

    def test_mixed_sources(self):
        engine = RecommendationEngine()
        f = _make_finding(GapType.MISSING, "critical")
        e = _make_error(ErrorCategory.SYNTAX, "critical")
        recs = engine.generate(findings=[f], code_errors=[e])
        assert len(recs) == 2
        source_types = {r.source_type for r in recs}
        assert "gap_finding" in source_types
        assert "code_error" in source_types

    def test_no_inputs_returns_empty(self):
        engine = RecommendationEngine()
        assert engine.generate() == []

    def test_none_inputs_handled(self):
        engine = RecommendationEngine()
        recs = engine.generate(findings=None, code_errors=None)
        assert recs == []
