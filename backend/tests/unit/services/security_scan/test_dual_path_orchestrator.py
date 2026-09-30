"""Unit tests for the dual-path security orchestrator — Story 4.13.

Covers the pure merge strategy, comparison-report generation, derivation of a
report from persisted findings (by ``source``) and engine_mode routing.
"""

from app.services.security_scan.dual_path_orchestrator import (
    SecurityDualPathOrchestrator,
)
from app.services.security_scan.rules import RawFinding


def _raw(vt="sql_injection", file="a.py", line=10, source="native", confidence=0.7, **kw):
    return RawFinding(
        vulnerability_type=vt,
        severity=kw.get("severity", "high"),
        description=kw.get("description", "desc"),
        file_path=file,
        line_start=line,
        line_end=line,
        confidence=confidence,
        source=source,
        recommendation=kw.get("recommendation"),
    )


class TestMergeFindings:
    def test_overlap_marked_hybrid_and_boosted(self):
        native = [_raw(confidence=0.7)]
        llm = [_raw(source="llm", confidence=0.6)]
        merge = SecurityDualPathOrchestrator.merge_findings(native, llm)

        assert len(merge.merged_findings) == 1
        merged = merge.merged_findings[0]
        assert merged.source == "hybrid"
        assert merged.confidence == 0.8  # 0.7 + 0.1
        assert len(merge.overlap) == 1
        assert merge.native_only == []
        assert merge.llm_only == []

    def test_llm_only_appended(self):
        native = [_raw(vt="sql_injection")]
        llm = [_raw(vt="idor", source="llm")]
        merge = SecurityDualPathOrchestrator.merge_findings(native, llm)

        assert len(merge.merged_findings) == 2
        assert len(merge.native_only) == 1
        assert len(merge.llm_only) == 1
        assert merge.overlap == []

    def test_llm_enriches_description_and_recommendation(self):
        native = [_raw(description="short", recommendation=None)]
        llm = [
            _raw(
                source="llm",
                description="a much longer and more contextual description",
                recommendation="use parameterized queries",
            )
        ]
        merge = SecurityDualPathOrchestrator.merge_findings(native, llm)
        merged = merge.merged_findings[0]
        assert merged.description == "a much longer and more contextual description"
        assert merged.recommendation == "use parameterized queries"

    def test_native_only_preserved(self):
        native = [_raw(), _raw(vt="xss", line=20)]
        merge = SecurityDualPathOrchestrator.merge_findings(native, [])
        assert len(merge.merged_findings) == 2
        assert len(merge.native_only) == 2


class TestComparisonReport:
    def test_counts_and_coverage(self):
        native = [_raw(vt="sql_injection"), _raw(vt="xss", line=20)]
        llm = [_raw(vt="sql_injection", source="llm"), _raw(vt="idor", line=30, source="llm")]
        merge = SecurityDualPathOrchestrator.merge_findings(native, llm)
        report = SecurityDualPathOrchestrator.generate_comparison_report(native, llm, merge)

        assert report.native_count == 2
        assert report.llm_count == 2
        assert report.merged_count == 3  # sql(overlap) + xss + idor
        assert report.native_only == 1  # xss
        assert report.llm_only == 1  # idor
        assert report.overlap_count == 1  # sql_injection
        assert report.coverage_improvement_pct == round((1 / 3) * 100, 1)

    def test_empty_yields_zero_coverage(self):
        merge = SecurityDualPathOrchestrator.merge_findings([], [])
        report = SecurityDualPathOrchestrator.generate_comparison_report([], [], merge)
        assert report.merged_count == 0
        assert report.coverage_improvement_pct == 0.0


class TestRunAnalysisRouting:
    def test_native_mode_returns_native_only(self):
        orch = SecurityDualPathOrchestrator()
        result = orch.run_analysis([_raw()], [_raw(source="llm")], engine_mode="native")
        assert result.engine_mode_used == "native"
        assert len(result.findings) == 1
        assert result.comparison_report is None

    def test_llm_mode_returns_llm_only(self):
        orch = SecurityDualPathOrchestrator()
        result = orch.run_analysis([_raw()], [_raw(source="llm", vt="idor")], engine_mode="llm")
        assert result.engine_mode_used == "llm"
        assert result.findings[0].vulnerability_type == "idor"

    def test_hybrid_mode_merges_with_report(self):
        orch = SecurityDualPathOrchestrator()
        native = [_raw(vt="sql_injection")]
        llm = [_raw(vt="idor", line=30, source="llm")]
        result = orch.run_analysis(native, llm, engine_mode="hybrid")
        assert result.engine_mode_used == "hybrid"
        assert len(result.findings) == 2
        assert result.comparison_report is not None
        assert result.comparison_report.llm_only == 1
