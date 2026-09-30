"""Risk engine — Epic 4, Story 4.8.

Scores aggregated findings with CVSS v3.1, escalates priority for dynamically
confirmed vulnerabilities (SAST+DAST correlation), estimates remediation effort
and produces a prioritised repair sequence plus a CVSS distribution and top-10
for the risk dashboard. The pure helpers run over in-memory ``SecurityFinding``
instances so they are fully unit-testable without a database.
"""

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_finding import ScanType, SecurityFinding, Severity
from app.services.security_scan.cvss_calculator import (
    calculate_cvss_base_score,
    cvss_severity,
    default_vector_for,
)

logger = logging.getLogger(__name__)

# CWE → OWASP Top 10 (2021) mapping for the most common classes.
_OWASP_BY_CWE: dict[str, str] = {
    "CWE-89": "A03:2021-Injection",
    "CWE-78": "A03:2021-Injection",
    "CWE-94": "A03:2021-Injection",
    "CWE-79": "A03:2021-Injection",
    "CWE-352": "A01:2021-Broken Access Control",
    "CWE-639": "A01:2021-Broken Access Control",
    "CWE-862": "A01:2021-Broken Access Control",
    "CWE-668": "A01:2021-Broken Access Control",
    "CWE-22": "A01:2021-Broken Access Control",
    "CWE-502": "A08:2021-Software and Data Integrity Failures",
    "CWE-1104": "A06:2021-Vulnerable and Outdated Components",
    "CWE-798": "A07:2021-Identification and Authentication Failures",
    "CWE-259": "A07:2021-Identification and Authentication Failures",
    "CWE-327": "A02:2021-Cryptographic Failures",
    "CWE-200": "A04:2021-Insecure Design",
    "CWE-611": "A05:2021-Security Misconfiguration",
    "CWE-918": "A10:2021-Server-Side Request Forgery",
}

# Remediation effort per vulnerability class (low = quick fix, high = refactor).
_EFFORT_BY_CWE: dict[str, str] = {
    "CWE-89": "low",  # parameterise the query
    "CWE-79": "low",  # output encoding
    "CWE-352": "low",  # add CSRF token
    "CWE-78": "medium",
    "CWE-94": "medium",
    "CWE-502": "medium",
    "CWE-22": "low",
    "CWE-798": "low",  # move secret to vault/env
    "CWE-259": "low",
    "CWE-327": "low",
    "CWE-639": "high",  # authorization redesign
    "CWE-862": "high",
    "CWE-668": "medium",
    "CWE-1104": "low",  # pin image digest
    "CWE-918": "medium",
    "CWE-611": "low",
    "CWE-200": "medium",
}
_DEFAULT_EFFORT = "medium"

_EFFORT_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
    Severity.INFO: 0,
}
# Severity ladder for one-level escalation.
_SEVERITY_LADDER: list[Severity] = [
    Severity.INFO,
    Severity.LOW,
    Severity.MEDIUM,
    Severity.HIGH,
    Severity.CRITICAL,
]

# CVSS distribution buckets (matching the qualitative bands).
_CVSS_BUCKETS = ("critical", "high", "medium", "low", "info")


@dataclass
class CVSSResult:
    base_score: float
    vector_string: str
    severity: str


@dataclass
class RiskAssessment:
    prioritized_findings: list[SecurityFinding]
    cvss_distribution: dict[str, int]
    top_10: list[SecurityFinding]
    effort_estimates: dict[str, str] = field(default_factory=dict)


class RiskEngine:
    def __init__(self, db: AsyncSession | None = None) -> None:
        self.db = db

    async def calculate_risk(
        self,
        project_id: uuid.UUID,
        db: AsyncSession | None = None,
    ) -> RiskAssessment:
        """Load the project's findings and score/prioritise them (AC1-AC3)."""
        session = db or self.db
        if session is None:
            raise ValueError("Brak sesji bazy danych dla risk engine")

        result = await session.execute(
            select(SecurityFinding).where(SecurityFinding.project_id == project_id)
        )
        findings = list(result.scalars().all())
        return self.assess(findings)

    def assess(self, findings: list[SecurityFinding]) -> RiskAssessment:
        """Pure scoring + prioritisation over in-memory findings (deterministic)."""
        effort_estimates: dict[str, str] = {}
        for finding in findings:
            # Respect a scanner-provided CVSS (e.g. the CVE score on dependency
            # findings); otherwise derive one from the CWE / severity.
            if finding.cvss_score is None:
                cvss = self._calculate_cvss(finding)
                finding.cvss_score = cvss.base_score
                finding.cvss_vector = cvss.vector_string
            if not finding.owasp_category and finding.cwe_id:
                finding.owasp_category = _OWASP_BY_CWE.get(finding.cwe_id.upper())
            finding.effort = self._estimate_effort(finding)
            effort_estimates[str(finding.id)] = finding.effort

        # Escalate (one level + reason) from the reported severity, then align the
        # severity with the CVSS band as a floor (never lowers it).
        self._apply_escalation_rules(findings)
        for finding in findings:
            finding.severity = self._adjust_severity_by_cvss(finding.severity, finding.cvss_score)

        prioritized = self._prioritize(findings)
        for index, finding in enumerate(prioritized, start=1):
            finding.priority = index

        return RiskAssessment(
            prioritized_findings=prioritized,
            cvss_distribution=self._cvss_distribution(prioritized),
            top_10=prioritized[:10],
            effort_estimates=effort_estimates,
        )

    def _calculate_cvss(self, finding: SecurityFinding) -> CVSSResult:
        """Compute CVSS from the finding's CWE (or its severity as fallback)."""
        vector = default_vector_for(finding.cwe_id, finding.severity.value if finding.severity else None)
        score = calculate_cvss_base_score(vector)
        return CVSSResult(base_score=score, vector_string=vector.to_string(), severity=cvss_severity(score))

    @staticmethod
    def _adjust_severity_by_cvss(severity: Severity, cvss_score: float) -> Severity:
        """Align the finding's severity with the computed CVSS band, taking the higher."""
        computed = Severity(cvss_severity(cvss_score))
        if _SEVERITY_ORDER.get(computed, 0) > _SEVERITY_ORDER.get(severity, 0):
            return computed
        return severity

    def _apply_escalation_rules(self, findings: list[SecurityFinding]) -> None:
        """Raise priority for dynamically confirmed / exploitable findings (AC2)."""
        for finding in findings:
            sources = set((finding.finding_metadata or {}).get("sources", []))
            confirmed = ScanType.SAST.value in sources and ScanType.DAST.value in sources
            if confirmed and finding.severity != Severity.CRITICAL:
                self._escalate(finding, "Potwierdzona dynamicznie (SAST+DAST)")
            elif (
                finding.scan_type == ScanType.DEPENDENCY
                and (finding.cvss_score or 0.0) >= 9.0
                and finding.severity != Severity.CRITICAL
            ):
                self._escalate(finding, "Zależność z publicznym exploitem (CVSS >= 9.0)")

    @staticmethod
    def _escalate(finding: SecurityFinding, reason: str) -> None:
        original = finding.severity
        idx = _SEVERITY_LADDER.index(original)
        finding.severity = _SEVERITY_LADDER[min(idx + 1, len(_SEVERITY_LADDER) - 1)]
        finding.escalation_reason = reason
        meta = dict(finding.finding_metadata or {})
        meta["escalation"] = reason
        meta["original_severity"] = original.value
        finding.finding_metadata = meta

    @staticmethod
    def _estimate_effort(finding: SecurityFinding) -> str:
        if finding.cwe_id:
            return _EFFORT_BY_CWE.get(finding.cwe_id.upper(), _DEFAULT_EFFORT)
        return _DEFAULT_EFFORT

    @staticmethod
    def _prioritize(findings: list[SecurityFinding]) -> list[SecurityFinding]:
        """Sort by severity DESC, confidence DESC, effort ASC (quick wins first)."""
        return sorted(
            findings,
            key=lambda f: (
                -_SEVERITY_ORDER.get(f.severity, 0),
                -(f.confidence or 0.0),
                _EFFORT_ORDER.get(f.effort or _DEFAULT_EFFORT, 1),
                -(f.cvss_score or 0.0),
            ),
        )

    @staticmethod
    def _cvss_distribution(findings: list[SecurityFinding]) -> dict[str, int]:
        distribution = {bucket: 0 for bucket in _CVSS_BUCKETS}
        for finding in findings:
            band = cvss_severity(finding.cvss_score or 0.0)
            distribution[band] += 1
        return distribution
