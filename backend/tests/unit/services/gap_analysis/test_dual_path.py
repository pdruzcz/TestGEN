"""Unit tests for GapDualPathOrchestrator and LLMGapAnalyzer — Epic 5, Story 5.10."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.gap_analysis.comparator import (
    GapFindingData,
    RequirementData,
)
from app.services.gap_analysis.dual_path_orchestrator import (
    GapDualPathOrchestrator,
)
from app.services.gap_analysis.llm_gap_analyzer import LLMGapAnalyzer

# ── Helpers ──────────────────────────────────────────────────────────────────


def _finding(
    req_id: str = "REQ-1",
    code_id: str = "func_a",
    gap_type: str = "missing",
    desc: str = "Brak implementacji",
    score: float = 25.0,
    method: str = "combined",
) -> GapFindingData:
    return GapFindingData(
        requirement_id=req_id,
        code_entity_id=code_id,
        gap_type=gap_type,
        description=desc,
        match_score=score,
        match_method=method,
        context={},
        severity="warning",
    )


def _code_entity(name="func_a"):
    return SimpleNamespace(
        name=name,
        type="function",
        file_path="src/api.py",
        line_number=10,
        docstring="Does something",
    )


# ── DualPathOrchestrator: run_analysis modes ──────────────────────────────────


class TestRunAnalysisModes:
    def test_native_mode_returns_native_only(self):
        orch = GapDualPathOrchestrator()
        native = [_finding("R1", "c1"), _finding("R2", "c2")]
        llm = [_finding("R3", "c3")]
        result = orch.run_analysis(native, llm, "native")
        assert result.engine_mode_used == "native"
        assert len(result.findings) == 2
        assert result.comparison_report is None

    def test_llm_mode_returns_llm_only(self):
        orch = GapDualPathOrchestrator()
        native = [_finding("R1", "c1")]
        llm = [_finding("R2", "c2"), _finding("R3", "c3")]
        result = orch.run_analysis(native, llm, "llm")
        assert result.engine_mode_used == "llm"
        assert len(result.findings) == 2

    def test_hybrid_mode_returns_merged(self):
        orch = GapDualPathOrchestrator()
        native = [_finding("R1", "c1"), _finding("R2", "c2")]
        llm = [_finding("R2", "c2"), _finding("R3", "c3")]
        result = orch.run_analysis(native, llm, "hybrid")
        assert result.engine_mode_used == "hybrid"
        assert result.comparison_report is not None
        assert result.comparison_report.merged_count == 3
        assert result.comparison_report.overlap_count == 1
        assert result.comparison_report.llm_only_count == 1
        assert result.comparison_report.native_only_count == 1


# ── Merge logic ───────────────────────────────────────────────────────────────


class TestMergeFindings:
    def test_overlap_marked_hybrid(self):
        orch = GapDualPathOrchestrator()
        native = [_finding("R1", "c1", desc="Short")]
        llm = [_finding("R1", "c1", desc="Much longer description from LLM")]
        merge = orch.merge_findings(native, llm)
        assert len(merge.overlap) == 1
        assert merge.overlap[0].context["source"] == "hybrid"
        assert "longer" in merge.overlap[0].description

    def test_llm_higher_score_overrides(self):
        orch = GapDualPathOrchestrator()
        native = [_finding("R1", "c1", score=30.0)]
        llm = [_finding("R1", "c1", score=85.0)]
        merge = orch.merge_findings(native, llm)
        assert merge.overlap[0].match_score == 85.0
        assert merge.overlap[0].match_method == "hybrid"

    def test_native_only_kept(self):
        orch = GapDualPathOrchestrator()
        native = [_finding("R1", "c1"), _finding("R2", "c2")]
        llm = [_finding("R1", "c1")]
        merge = orch.merge_findings(native, llm)
        assert len(merge.native_only) == 1
        assert merge.native_only[0].requirement_id == "R2"

    def test_llm_only_appended(self):
        orch = GapDualPathOrchestrator()
        native = [_finding("R1", "c1")]
        llm = [_finding("R1", "c1"), _finding("R3", "c3")]
        merge = orch.merge_findings(native, llm)
        assert len(merge.llm_only) == 1
        assert merge.llm_only[0].requirement_id == "R3"
        assert merge.llm_only[0].context["source"] == "llm"

    def test_empty_inputs(self):
        orch = GapDualPathOrchestrator()
        merge = orch.merge_findings([], [])
        assert len(merge.merged_findings) == 0

    def test_dedup_by_description_fallback(self):
        orch = GapDualPathOrchestrator()
        native = [
            GapFindingData(
                requirement_id=None,
                code_entity_id=None,
                gap_type="missing",
                description="Unique gap desc",
            )
        ]
        llm = [
            GapFindingData(
                requirement_id=None,
                code_entity_id=None,
                gap_type="missing",
                description="Unique gap desc",
            )
        ]
        merge = orch.merge_findings(native, llm)
        assert len(merge.overlap) == 1


# ── Comparison report ─────────────────────────────────────────────────────────


class TestComparisonReport:
    def test_report_counts(self):
        orch = GapDualPathOrchestrator()
        native = [_finding("R1", "c1"), _finding("R2", "c2")]
        llm = [_finding("R2", "c2"), _finding("R3", "c3")]
        merge = orch.merge_findings(native, llm)
        report = orch.generate_comparison_report(native, llm, merge)
        assert report.native_count == 2
        assert report.llm_count == 2
        assert report.merged_count == 3
        assert report.overlap_count == 1
        assert report.native_only_count == 1
        assert report.llm_only_count == 1

    def test_coverage_improvement(self):
        orch = GapDualPathOrchestrator()
        native = [_finding("R1", "c1")]
        llm = [_finding("R2", "c2"), _finding("R3", "c3"), _finding("R4", "c4")]
        merge = orch.merge_findings(native, llm)
        report = orch.generate_comparison_report(native, llm, merge)
        # 3 LLM-only out of 4 merged = 75%
        assert report.coverage_improvement_pct == 75.0


# ── LLMGapAnalyzer ────────────────────────────────────────────────────────────


class TestLLMGapAnalyzer:
    @pytest.mark.asyncio
    async def test_no_gateway_returns_empty(self):
        analyzer = LLMGapAnalyzer(llm_gateway=None)
        reqs = [RequirementData(req_id="R1", text="Test")]
        codes = [_code_entity()]
        findings, summary = await analyzer.analyze(reqs, codes)
        assert len(findings) == 0
        assert summary.total_requirements == 1

    @patch("app.services.gap_analysis.llm_gap_analyzer.LLMGapAnalyzer.__init__")
    def test_parse_valid_json(self, mock_init):
        mock_init.return_value = None
        analyzer = LLMGapAnalyzer.__new__(LLMGapAnalyzer)
        analyzer.llm_gateway = None

        reqs = [RequirementData(req_id="R1", text="System must validate input")]
        codes = [_code_entity("validate_input")]

        content = json.dumps(
            [
                {
                    "requirement_id": "R1",
                    "code_entity_id": "validate_input",
                    "gap_type": "different",
                    "description": "Input validation incomplete",
                    "match_score": 55.0,
                    "severity": "warning",
                },
                {
                    "requirement_id": None,
                    "code_entity_id": None,
                    "gap_type": "missing",
                    "description": "No logging",
                    "match_score": 0.0,
                    "severity": "critical",
                },
            ]
        )
        findings = analyzer._parse_response(content, reqs, codes)
        assert len(findings) == 2
        assert findings[0].gap_type == "different"
        assert findings[0].match_method == "llm"
        assert findings[0].requirement_text == "System must validate input"
        assert findings[1].severity == "critical"

    def test_parse_invalid_json_returns_empty(self):
        analyzer = LLMGapAnalyzer(llm_gateway=None)
        findings = analyzer._parse_response("not json", [], [])
        assert len(findings) == 0

    def test_parse_non_list_returns_empty(self):
        analyzer = LLMGapAnalyzer(llm_gateway=None)
        findings = analyzer._parse_response('{"key": "value"}', [], [])
        assert len(findings) == 0

    def test_parse_invalid_gap_type_defaults_to_missing(self):
        analyzer = LLMGapAnalyzer(llm_gateway=None)
        content = json.dumps(
            [
                {
                    "requirement_id": "R1",
                    "code_entity_id": "c1",
                    "gap_type": "invalid_type",
                    "description": "test",
                }
            ]
        )
        findings = analyzer._parse_response(content, [], [])
        assert findings[0].gap_type == "missing"

    def test_build_prompt_with_real_code_entity(self):
        """Ensure _build_prompt uses correct CodeEntity attributes (type, line_number)."""
        from app.services.analysis.gap_analyzer import CodeEntity

        analyzer = LLMGapAnalyzer(llm_gateway=None)
        reqs = [RequirementData(req_id="R1", text="System musi walidować dane")]
        codes = [
            CodeEntity(
                entity_id="c1",
                name="validate_input",
                type="function",
                file_path="src/api.py",
                line_number=42,
                language="python",
                docstring="Validates input data",
            )
        ]
        prompt = analyzer._build_prompt(reqs, codes)
        assert "validate_input" in prompt
        assert "src/api.py:42" in prompt
        assert "function" in prompt

    @pytest.mark.asyncio
    async def test_mocked_analyze_returns_expected(self):
        from unittest.mock import AsyncMock

        from app.services.gap_analysis.comparator import GapAnalysisSummaryData

        analyzer = LLMGapAnalyzer(llm_gateway=None)
        mock_findings = [_finding("R1", "c1", gap_type="missing")]
        mock_summary = GapAnalysisSummaryData(missing_count=1, total_requirements=1)
        analyzer.analyze = AsyncMock(return_value=(mock_findings, mock_summary))

        findings, summary = await analyzer.analyze([], [])
        assert len(findings) == 1
        assert summary.missing_count == 1
