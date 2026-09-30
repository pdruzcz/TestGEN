"""Unit tests for ComplianceEngine — Epic 5, Story 5.3.

Tests project/module/function scoring, penalty weights, CSV export,
and edge cases (empty findings, all critical, mixed severities).
"""

import pytest

from app.models.gap_finding import GapType
from app.services.gap_analysis.compliance_engine import (
    PENALTY_WEIGHTS,
    ComplianceEngine,
)


def _make_finding(
    gap_type: GapType = GapType.MISSING,
    severity: str = "warning",
    code_reference: str | None = None,
    code_entity_id: str | None = None,
    context: dict | None = None,
):
    """Create a minimal mock GapFinding for scoring tests."""
    from types import SimpleNamespace

    return SimpleNamespace(
        gap_type=gap_type,
        severity=severity,
        code_reference=code_reference,
        code_entity_id=code_entity_id,
        context=context,
    )


# ── Project score ────────────────────────────────────────────────────────────


class TestProjectScore:
    def test_empty_findings_perfect_score(self):
        engine = ComplianceEngine()
        result = engine.calculate_project_score([])
        assert result.score == 100.0
        assert result.total_findings == 0

    def test_single_missing_critical_penalty(self):
        engine = ComplianceEngine()
        f = _make_finding(GapType.MISSING, "critical")
        result = engine.calculate_project_score([f])
        assert result.score == 100.0 - PENALTY_WEIGHTS["missing"]["critical"]
        assert result.score == 85.0

    def test_single_missing_warning_penalty(self):
        engine = ComplianceEngine()
        f = _make_finding(GapType.MISSING, "warning")
        result = engine.calculate_project_score([f])
        assert result.score == 92.0

    def test_single_different_warning_penalty(self):
        engine = ComplianceEngine()
        f = _make_finding(GapType.DIFFERENT, "warning")
        result = engine.calculate_project_score([f])
        assert result.score == 95.0

    def test_single_extra_info_penalty(self):
        engine = ComplianceEngine()
        f = _make_finding(GapType.EXTRA, "info")
        result = engine.calculate_project_score([f])
        assert result.score == 99.0

    def test_single_inconsistent_critical_penalty(self):
        engine = ComplianceEngine()
        f = _make_finding(GapType.INCONSISTENT, "critical")
        result = engine.calculate_project_score([f])
        assert result.score == 90.0

    def test_score_clamped_to_zero(self):
        """Many critical findings should not produce negative scores."""
        engine = ComplianceEngine()
        findings = [_make_finding(GapType.MISSING, "critical") for _ in range(20)]
        result = engine.calculate_project_score(findings)
        assert result.score == 0.0

    def test_mixed_findings_score(self):
        engine = ComplianceEngine()
        findings = [
            _make_finding(GapType.MISSING, "critical"),      # -15
            _make_finding(GapType.DIFFERENT, "warning"),      # -5
            _make_finding(GapType.EXTRA, "info"),             # -1
            _make_finding(GapType.INCONSISTENT, "critical"),  # -10
        ]
        result = engine.calculate_project_score(findings)
        assert result.score == 100.0 - (15 + 5 + 1 + 10)
        assert result.score == 69.0

    def test_breakdown_counts_by_type(self):
        engine = ComplianceEngine()
        findings = [
            _make_finding(GapType.MISSING, "warning"),
            _make_finding(GapType.MISSING, "critical"),
            _make_finding(GapType.EXTRA, "info"),
        ]
        result = engine.calculate_project_score(findings)
        assert result.breakdown["missing"] == 2
        assert result.breakdown["extra"] == 1
        assert result.breakdown["different"] == 0
        assert result.breakdown["inconsistent"] == 0
        assert result.total_findings == 3


# ── Module scores ────────────────────────────────────────────────────────────


class TestModuleScores:
    def test_grouped_by_file_path(self):
        engine = ComplianceEngine()
        findings = [
            _make_finding(GapType.MISSING, "critical", code_reference="src/app.py:10"),
            _make_finding(GapType.EXTRA, "info", code_reference="src/utils.py:5"),
            _make_finding(GapType.DIFFERENT, "warning", code_reference="src/app.py:20"),
        ]
        results = engine.calculate_module_scores(findings)
        assert len(results) == 2

        app_module = next(m for m in results if m.file_path == "src/app.py")
        assert app_module.total_findings == 2
        assert app_module.breakdown["missing"] == 1
        assert app_module.breakdown["different"] == 1

        utils_module = next(m for m in results if m.file_path == "src/utils.py")
        assert utils_module.total_findings == 1

    def test_context_file_path_fallback(self):
        engine = ComplianceEngine()
        f = _make_finding(
            GapType.MISSING,
            "warning",
            code_reference=None,
            context={"file_path": "lib/auth.py"},
        )
        results = engine.calculate_module_scores([f])
        assert len(results) == 1
        assert results[0].file_path == "lib/auth.py"

    def test_unknown_file_when_no_reference(self):
        engine = ComplianceEngine()
        f = _make_finding(GapType.MISSING, "warning")
        results = engine.calculate_module_scores([f])
        assert len(results) == 1
        assert results[0].file_path == "—unknown—"

    def test_empty_findings_no_modules(self):
        engine = ComplianceEngine()
        results = engine.calculate_module_scores([])
        assert results == []


# ── Function scores ──────────────────────────────────────────────────────────


class TestFunctionScores:
    def test_grouped_by_code_entity_id(self):
        engine = ComplianceEngine()
        findings = [
            _make_finding(GapType.MISSING, "critical", code_entity_id="fn-a"),
            _make_finding(GapType.DIFFERENT, "warning", code_entity_id="fn-a"),
            _make_finding(GapType.EXTRA, "info", code_entity_id="fn-b"),
        ]
        results = engine.calculate_function_scores(findings)
        assert len(results) == 2

        fn_a = next(f for f in results if f.code_entity_id == "fn-a")
        assert fn_a.total_findings == 2
        assert fn_a.score == 100.0 - (15 + 5)  # missing+critical, different+warning

    def test_unmapped_findings_grouped(self):
        engine = ComplianceEngine()
        findings = [
            _make_finding(GapType.MISSING, "warning", code_entity_id=None),
        ]
        results = engine.calculate_function_scores(findings)
        assert len(results) == 1
        assert results[0].code_entity_id == "—unmapped—"

    def test_entity_name_from_context(self):
        engine = ComplianceEngine()
        f = _make_finding(
            GapType.EXTRA,
            "info",
            code_entity_id="fn-x",
            context={"entity_name": "generate_report"},
        )
        results = engine.calculate_function_scores([f])
        assert results[0].entity_name == "generate_report"


# ── CSV export ────────────────────────────────────────────────────────────────


class TestCsvExport:
    def test_csv_has_sections(self):
        engine = ComplianceEngine()
        csv = engine.export_csv([])
        assert "COMPLIANCE REPORT" in csv
        assert "MODULE SCORES" in csv
        assert "FUNCTION SCORES" in csv

    def test_csv_with_data(self):
        engine = ComplianceEngine()
        findings = [
            _make_finding(GapType.MISSING, "critical", code_reference="app.py:10",
                          code_entity_id="fn-1", context={"entity_name": "login"}),
        ]
        csv = engine.export_csv(findings)
        assert "app.py" in csv
        assert "fn-1" in csv
        assert "login" in csv

    def test_csv_project_score_in_output(self):
        engine = ComplianceEngine()
        findings = [_make_finding(GapType.MISSING, "critical")]
        csv = engine.export_csv(findings)
        score = engine.calculate_project_score(findings)
        assert str(score.score) in csv


# ── Penalty weights ──────────────────────────────────────────────────────────


class TestPenaltyWeights:
    def test_missing_critical_is_highest_penalty(self):
        assert PENALTY_WEIGHTS["missing"]["critical"] == 15.0

    def test_extra_info_is_lowest_penalty(self):
        assert PENALTY_WEIGHTS["extra"]["info"] == 1.0

    def test_all_gap_types_have_all_severities(self):
        for gap_type in ["missing", "different", "inconsistent", "extra"]:
            for severity in ["critical", "warning", "info"]:
                assert severity in PENALTY_WEIGHTS[gap_type]
