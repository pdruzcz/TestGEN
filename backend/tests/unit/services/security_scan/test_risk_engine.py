"""Unit tests for the risk engine — Story 4.8.

Covers CVSS assignment, OWASP/effort mapping, priority escalation for
dynamically confirmed findings and the prioritised repair sequence.
"""

import uuid

from app.models.security_finding import (
    AnalysisSource,
    ScanType,
    SecurityFinding,
    Severity,
)
from app.services.security_scan.risk_engine import RiskEngine


def _finding(
    scan_type: ScanType = ScanType.SAST,
    vuln: str = "sql_injection",
    severity: Severity = Severity.MEDIUM,
    cwe: str | None = "CWE-89",
    confidence: float = 0.7,
    sources: list[str] | None = None,
    cvss_score: float | None = None,
) -> SecurityFinding:
    f = SecurityFinding(
        project_id=uuid.uuid4(),
        scan_id=uuid.uuid4(),
        scan_type=scan_type,
        vulnerability_type=vuln,
        severity=severity,
        cwe_id=cwe,
        file_path="app/db.py",
        line_start=10,
        description="opis",
        confidence=confidence,
        source=AnalysisSource.NATIVE,
        finding_metadata={"sources": sources} if sources else None,
    )
    f.id = uuid.uuid4()
    if cvss_score is not None:
        f.cvss_score = cvss_score
    return f


class TestCVSSAssignment:
    def test_sqli_gets_high_cvss(self):
        f = _finding(cwe="CWE-89")
        RiskEngine().assess([f])
        assert f.cvss_score == 9.8
        assert f.cvss_vector.startswith("CVSS:3.1/")

    def test_severity_raised_to_cvss_band(self):
        # SQLi reported as MEDIUM should be lifted to CRITICAL by its 9.8 CVSS.
        f = _finding(severity=Severity.MEDIUM, cwe="CWE-89")
        RiskEngine().assess([f])
        assert f.severity == Severity.CRITICAL

    def test_owasp_category_assigned(self):
        f = _finding(cwe="CWE-89")
        RiskEngine().assess([f])
        assert f.owasp_category == "A03:2021-Injection"

    def test_effort_estimated(self):
        f = _finding(cwe="CWE-89")
        RiskEngine().assess([f])
        assert f.effort == "low"

    def test_authz_effort_is_high(self):
        f = _finding(vuln="broken_authz", cwe="CWE-862", severity=Severity.HIGH)
        RiskEngine().assess([f])
        assert f.effort == "high"


class TestEscalation:
    def test_sast_dast_confirmed_escalates_one_level(self):
        f = _finding(
            severity=Severity.MEDIUM,
            cwe="CWE-352",  # CSRF, CVSS 6.5 → stays medium by band
            sources=["sast", "dast"],
        )
        RiskEngine().assess([f])
        assert f.escalation_reason is not None
        assert f.finding_metadata["original_severity"] == "medium"
        assert f.severity == Severity.HIGH

    def test_no_escalation_without_dual_confirmation(self):
        f = _finding(severity=Severity.MEDIUM, cwe="CWE-352", sources=["sast"])
        RiskEngine().assess([f])
        assert f.escalation_reason is None

    def test_dependency_with_high_cvss_escalates(self):
        f = _finding(
            scan_type=ScanType.DEPENDENCY,
            vuln="vulnerable_dependency",
            cwe=None,
            severity=Severity.HIGH,
            cvss_score=9.5,
        )
        # Provide a CWE-less finding whose band would be HIGH, then escalate.
        RiskEngine().assess([f])
        assert f.severity == Severity.CRITICAL
        assert "exploit" in f.escalation_reason.lower()

    def test_escalation_does_not_exceed_critical(self):
        f = _finding(severity=Severity.CRITICAL, cwe="CWE-89", sources=["sast", "dast"])
        RiskEngine().assess([f])
        assert f.severity == Severity.CRITICAL


class TestPrioritization:
    def test_sorted_by_severity_then_effort(self):
        crit_high_effort = _finding(severity=Severity.CRITICAL, cwe="CWE-862", vuln="authz")
        crit_low_effort = _finding(severity=Severity.CRITICAL, cwe="CWE-89")
        result = RiskEngine().assess([crit_high_effort, crit_low_effort])
        # Same severity → quick win (low effort) first.
        assert result.prioritized_findings[0].cwe_id == "CWE-89"
        assert result.prioritized_findings[0].priority == 1

    def test_priority_numbers_are_sequential(self):
        findings = [_finding(cwe="CWE-89"), _finding(cwe="CWE-79")]
        result = RiskEngine().assess(findings)
        assert sorted(f.priority for f in result.prioritized_findings) == [1, 2]

    def test_top_10_limited(self):
        findings = [_finding(cwe="CWE-89") for _ in range(15)]
        result = RiskEngine().assess(findings)
        assert len(result.top_10) == 10

    def test_cvss_distribution_buckets(self):
        findings = [
            _finding(cwe="CWE-89"),  # critical 9.8
            _finding(cwe="CWE-200", severity=Severity.LOW),  # 5.3 medium
        ]
        result = RiskEngine().assess(findings)
        assert result.cvss_distribution["critical"] == 1
        assert result.cvss_distribution["medium"] == 1
