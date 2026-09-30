"""Unit tests for the finding aggregator — Story 4.7.

Exercises deduplication, SAST↔DAST/taint correlation, confidence scoring and the
report summary over in-memory ``SecurityFinding`` instances (no DB).
"""

import uuid

from app.models.security_finding import (
    AnalysisSource,
    ScanType,
    SecurityFinding,
    Severity,
)
from app.services.security_scan.finding_aggregator import FindingAggregator


def _finding(
    scan_type: ScanType,
    vuln: str = "sql_injection",
    severity: Severity = Severity.HIGH,
    file_path: str | None = "app/db.py",
    line: int | None = 10,
    cwe: str | None = "CWE-89",
    source: AnalysisSource = AnalysisSource.NATIVE,
    taint_path: dict | None = None,
) -> SecurityFinding:
    f = SecurityFinding(
        project_id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        scan_type=scan_type,
        vulnerability_type=vuln,
        severity=severity,
        cwe_id=cwe,
        file_path=file_path,
        line_start=line,
        description="opis",
        confidence=0.5,
        source=source,
        taint_path=taint_path,
    )
    f.id = uuid.uuid4()
    return f


class TestDeduplication:
    def test_same_file_line_type_merged(self):
        sast = _finding(ScanType.SAST)
        taint = _finding(ScanType.TAINT, taint_path={"source": "req"})
        # Align dedup key (file/line/type/cwe identical).
        result = FindingAggregator().aggregate_findings([sast, taint])
        assert len(result.findings) == 1
        assert result.dedup_count == 1

    def test_different_lines_not_merged(self):
        a = _finding(ScanType.SAST, line=10)
        b = _finding(ScanType.SAST, line=20)
        result = FindingAggregator().aggregate_findings([a, b])
        assert len(result.findings) == 2
        assert result.dedup_count == 0

    def test_merged_finding_records_sources(self):
        sast = _finding(ScanType.SAST)
        taint = _finding(ScanType.TAINT)
        result = FindingAggregator().aggregate_findings([sast, taint])
        sources = result.findings[0].finding_metadata["sources"]
        assert "sast" in sources
        assert "taint" in sources

    def test_merge_keeps_taint_path(self):
        sast = _finding(ScanType.SAST, taint_path=None)
        taint = _finding(ScanType.TAINT, taint_path={"source": "request.args"})
        result = FindingAggregator().aggregate_findings([sast, taint])
        assert result.findings[0].taint_path == {"source": "request.args"}


class TestCorrelation:
    def test_sast_dast_correlation_detected(self):
        sast = _finding(ScanType.SAST, file_path="app/db.py")
        dast = _finding(ScanType.DAST, file_path="https://app/login", line=None)
        result = FindingAggregator().aggregate_findings([sast, dast])
        assert any(c.correlation_type == "sast_dast" for c in result.correlations)

    def test_sast_dast_boosts_confidence_above_90(self):
        sast = _finding(ScanType.SAST, file_path="app/db.py")
        dast = _finding(ScanType.DAST, file_path="https://app/login", line=None)
        result = FindingAggregator().aggregate_findings([sast, dast])
        sast_out = next(f for f in result.findings if f.scan_type == ScanType.SAST)
        # base 0.70 + correlation 0.20 = 0.90
        assert sast_out.confidence >= 0.90

    def test_no_correlation_when_types_differ(self):
        sast = _finding(ScanType.SAST, vuln="sql_injection", cwe="CWE-89")
        dast = _finding(ScanType.DAST, vuln="xss", cwe="CWE-79", line=None)
        result = FindingAggregator().aggregate_findings([sast, dast])
        assert result.correlations == []


class TestConfidence:
    def test_base_confidence_per_tool(self):
        dep = _finding(ScanType.DEPENDENCY, vuln="vuln_dep", cwe=None, file_path=None, line=None)
        result = FindingAggregator().aggregate_findings([dep])
        assert result.findings[0].confidence == 0.90

    def test_llm_source_uses_llm_base(self):
        f = _finding(ScanType.SAST, source=AnalysisSource.LLM)
        result = FindingAggregator().aggregate_findings([f])
        assert result.findings[0].confidence == 0.60

    def test_multiple_sources_boost(self):
        # SAST + taint at same key → sources_count 2 → +0.05 over taint merge base.
        sast = _finding(ScanType.SAST)
        taint = _finding(ScanType.TAINT)
        result = FindingAggregator().aggregate_findings([sast, taint])
        # base sast 0.70 + correlation 0.10 (sast_taint) + source boost 0.05
        assert result.findings[0].confidence >= 0.80

    def test_confidence_capped_at_one(self):
        f = _finding(ScanType.DEPENDENCY, cwe=None)
        f2 = _finding(ScanType.DAST, cwe=None, line=None, file_path=None)
        result = FindingAggregator().aggregate_findings([f, f2])
        assert all(x.confidence <= 1.0 for x in result.findings)


class TestSummaryAndSort:
    def test_summary_counts(self):
        findings = [
            _finding(ScanType.SAST, severity=Severity.CRITICAL, line=1),
            _finding(ScanType.DAST, severity=Severity.HIGH, line=2, file_path="u", cwe=None),
            _finding(ScanType.CONFIG, severity=Severity.LOW, line=3, file_path="c", cwe=None),
        ]
        result = FindingAggregator().aggregate_findings(findings)
        assert result.summary["total_findings"] == 3
        assert result.summary["severity_counts"]["critical"] == 1
        assert result.summary["source_counts"]["sast"] == 1

    def test_sorted_by_severity_then_confidence(self):
        low = _finding(ScanType.CONFIG, severity=Severity.LOW, line=1, file_path="a", cwe=None)
        crit = _finding(ScanType.SAST, severity=Severity.CRITICAL, line=2, file_path="b")
        result = FindingAggregator().aggregate_findings([low, crit])
        assert result.findings[0].severity == Severity.CRITICAL
