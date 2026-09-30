"""Finding aggregator — Epic 4, Story 4.7.

Consolidates findings from every security scanner (SAST / taint / dependency /
config / DAST) into a single report. It deduplicates findings that describe the
same vulnerability (same file + line + type + CWE), correlates SAST findings
confirmed by DAST to raise their confidence, and computes a 0-1 confidence score
per finding from the contributing tools, their base reliability and the
correlations. The pure helpers operate on in-memory ``SecurityFinding`` instances
so they are fully unit-testable without a database.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_finding import (
    AnalysisSource,
    ScanType,
    SecurityFinding,
    Severity,
)

logger = logging.getLogger(__name__)

# Base reliability per tool (AC1, Task 2).
_TOOL_CONFIDENCE: dict[ScanType, float] = {
    ScanType.SAST: 0.70,
    ScanType.TAINT: 0.80,
    ScanType.DEPENDENCY: 0.90,
    ScanType.DAST: 0.85,
    ScanType.CONFIG: 0.75,
}
_LLM_CONFIDENCE = 0.60

# Correlation boost when SAST is confirmed by DAST / taint (Task 2).
_BOOST_SAST_DAST = 0.20
_BOOST_SAST_TAINT = 0.10

# Severity ordering for the report sort (highest first).
_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
    Severity.INFO: 0,
}


@dataclass
class Correlation:
    sast_finding_id: str
    dast_finding_id: str
    correlation_type: str  # "sast_dast" / "sast_taint"
    confidence_boost: float


@dataclass
class AggregationResult:
    findings: list[SecurityFinding]
    summary: dict
    correlations: list[Correlation]
    dedup_count: int


def _dedup_key(f: SecurityFinding) -> tuple:
    return (
        f.file_path or "",
        f.line_start or 0,
        f.vulnerability_type,
        f.cwe_id or "",
    )


class FindingAggregator:
    def __init__(self, db: AsyncSession | None = None) -> None:
        self.db = db

    async def aggregate(
        self,
        project_id: uuid.UUID,
        scan_ids: list[uuid.UUID],
        db: AsyncSession | None = None,
    ) -> AggregationResult:
        """Load the findings for the given scans and aggregate them (AC1, AC2)."""
        session = db or self.db
        if session is None:
            raise ValueError("Brak sesji bazy danych dla agregacji")

        conditions = [SecurityFinding.project_id == project_id]
        if scan_ids:
            conditions.append(SecurityFinding.scan_id.in_(scan_ids))
        result = await session.execute(select(SecurityFinding).where(*conditions))
        findings = list(result.scalars().all())
        return self.aggregate_findings(findings)

    def aggregate_findings(self, findings: list[SecurityFinding]) -> AggregationResult:
        """Pure aggregation over in-memory findings (deterministic, testable)."""
        correlations = self._correlate(findings)
        boost_by_key = self._boost_by_key(findings, correlations)

        deduped, sources_by_key = self._deduplicate(findings)

        for finding in deduped:
            key = _dedup_key(finding)
            sources = sources_by_key.get(key, set())
            finding.confidence = self._calculate_confidence(
                finding, len(sources), boost_by_key.get(key, 0.0)
            )
            meta = dict(finding.finding_metadata or {})
            meta["sources"] = sorted(s.value for s in sources)
            finding.finding_metadata = meta

        deduped.sort(
            key=lambda f: (_SEVERITY_ORDER.get(f.severity, 0), f.confidence),
            reverse=True,
        )

        return AggregationResult(
            findings=deduped,
            summary=self._build_summary(deduped),
            correlations=correlations,
            dedup_count=len(findings) - len(deduped),
        )

    def _deduplicate(
        self, findings: list[SecurityFinding]
    ) -> tuple[list[SecurityFinding], dict[tuple, set[ScanType]]]:
        merged: dict[tuple, SecurityFinding] = {}
        sources: dict[tuple, set[ScanType]] = {}
        for finding in findings:
            key = _dedup_key(finding)
            sources.setdefault(key, set()).add(finding.scan_type)
            if key not in merged:
                merged[key] = finding
            else:
                merged[key] = self._merge_findings(merged[key], finding)
        return list(merged.values()), sources

    @staticmethod
    def _merge_findings(
        base: SecurityFinding, duplicate: SecurityFinding
    ) -> SecurityFinding:
        """Merge a duplicate into the base: keep higher confidence, join taint."""
        if duplicate.confidence > base.confidence:
            base.confidence = duplicate.confidence
        if base.taint_path is None and duplicate.taint_path is not None:
            base.taint_path = duplicate.taint_path
        if not base.recommendation and duplicate.recommendation:
            base.recommendation = duplicate.recommendation
        return base

    def _correlate(self, findings: list[SecurityFinding]) -> list[Correlation]:
        sast = [f for f in findings if f.scan_type == ScanType.SAST]
        dast = [f for f in findings if f.scan_type == ScanType.DAST]
        taint = [f for f in findings if f.scan_type == ScanType.TAINT]

        correlations: list[Correlation] = []
        for s in sast:
            for d in dast:
                if self._matches(s, d):
                    correlations.append(
                        Correlation(
                            sast_finding_id=str(s.id),
                            dast_finding_id=str(d.id),
                            correlation_type="sast_dast",
                            confidence_boost=_BOOST_SAST_DAST,
                        )
                    )
            for t in taint:
                if self._matches(s, t):
                    correlations.append(
                        Correlation(
                            sast_finding_id=str(s.id),
                            dast_finding_id=str(t.id),
                            correlation_type="sast_taint",
                            confidence_boost=_BOOST_SAST_TAINT,
                        )
                    )
        return correlations

    @staticmethod
    def _matches(a: SecurityFinding, b: SecurityFinding) -> bool:
        if a.cwe_id and b.cwe_id and a.cwe_id == b.cwe_id:
            return True
        ta = (a.vulnerability_type or "").lower()
        tb = (b.vulnerability_type or "").lower()
        return bool(ta and tb and (ta in tb or tb in ta))

    def _boost_by_key(
        self, findings: list[SecurityFinding], correlations: list[Correlation]
    ) -> dict[tuple, float]:
        by_id = {str(f.id): f for f in findings}
        boost: dict[tuple, float] = {}
        for corr in correlations:
            for fid in (corr.sast_finding_id, corr.dast_finding_id):
                finding = by_id.get(fid)
                if finding is None:
                    continue
                key = _dedup_key(finding)
                boost[key] = min(boost.get(key, 0.0) + corr.confidence_boost, _BOOST_SAST_DAST)
        return boost

    @staticmethod
    def _calculate_confidence(
        finding: SecurityFinding, sources_count: int, correlation_boost: float
    ) -> float:
        base = (
            _LLM_CONFIDENCE
            if finding.source == AnalysisSource.LLM
            else _TOOL_CONFIDENCE.get(finding.scan_type, 0.5)
        )
        source_boost = min(max(sources_count - 1, 0), 3) * 0.05
        return round(min(base + correlation_boost + source_boost, 1.0), 4)

    @staticmethod
    def _build_summary(findings: list[SecurityFinding]) -> dict:
        severity_counts = {s.value: 0 for s in Severity}
        source_counts = {t.value: 0 for t in ScanType}
        for finding in findings:
            severity_counts[finding.severity.value] += 1
            source_counts[finding.scan_type.value] += 1
        return {
            "total_findings": len(findings),
            "severity_counts": severity_counts,
            "source_counts": source_counts,
        }
