"""ComparisonEngine — compare compliance snapshots and gap findings across versions.

Epic 5, Story 5.7.

Computes deltas between two analysis versions:
- Score delta (improved / regressed / stable)
- Gap-type count deltas (missing, different, extra, inconsistent)
- Per-finding status: fixed, new, unchanged, worsened

Uses requirement_id + code_entity_id as natural keys to match findings
between versions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.compliance_snapshot import ComplianceSnapshot
from app.models.gap_finding import GapFinding, GapType


@dataclass
class SnapshotDiff:
    """Result of comparing two compliance snapshots."""

    v1_score: float
    v2_score: float
    score_delta: float
    direction: str  # "improved" | "regressed" | "stable"

    v1_total: int
    v2_total: int
    total_delta: int

    missing_delta: int = 0
    different_delta: int = 0
    extra_delta: int = 0
    inconsistent_delta: int = 0

    coverage_delta: float = 0.0
    avg_match_score_delta: float = 0.0


@dataclass
class FindingDiff:
    """Status of a single finding across two versions."""

    key: str
    status: str  # "fixed" | "new" | "unchanged" | "worsened"
    gap_type: str
    v1_severity: str | None = None
    v2_severity: str | None = None
    v1_score: float | None = None
    v2_score: float | None = None
    requirement_text: str | None = None


@dataclass
class ComparisonResult:
    """Full comparison between two analysis versions."""

    snapshot_diff: SnapshotDiff
    finding_diffs: list[FindingDiff] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    @property
    def fixed_count(self) -> int:
        return self.summary.get("fixed", 0)

    @property
    def new_count(self) -> int:
        return self.summary.get("new", 0)

    @property
    def unchanged_count(self) -> int:
        return self.summary.get("unchanged", 0)

    @property
    def worsened_count(self) -> int:
        return self.summary.get("worsened", 0)


class ComparisonEngine:
    """Compare compliance snapshots and gap findings across versions."""

    SEVERITY_RANK: dict[str, int] = {"info": 1, "warning": 2, "critical": 3}

    def compare_snapshots(
        self,
        v1: ComplianceSnapshot,
        v2: ComplianceSnapshot,
    ) -> SnapshotDiff:
        """Compare two compliance snapshots at metric level."""
        delta = v2.score - v1.score
        if delta > 0.5:
            direction = "improved"
        elif delta < -0.5:
            direction = "regressed"
        else:
            direction = "stable"

        return SnapshotDiff(
            v1_score=v1.score,
            v2_score=v2.score,
            score_delta=round(delta, 1),
            direction=direction,
            v1_total=v1.total_findings,
            v2_total=v2.total_findings,
            total_delta=v2.total_findings - v1.total_findings,
            missing_delta=v2.missing_count - v1.missing_count,
            different_delta=v2.different_count - v1.different_count,
            extra_delta=v2.extra_count - v1.extra_count,
            inconsistent_delta=v2.inconsistent_count - v1.inconsistent_count,
            coverage_delta=round(
                v2.coverage_percentage - v1.coverage_percentage, 1
            ),
            avg_match_score_delta=round(
                v2.avg_match_score - v1.avg_match_score, 1
            ),
        )

    def compare_findings(
        self,
        v1_findings: list[GapFinding],
        v2_findings: list[GapFinding],
    ) -> list[FindingDiff]:
        """Compare per-finding status across two versions.

        Matches findings by requirement_id when available, falling back to
        code_entity_id, then to description text.
        """
        v1_map = self._build_finding_map(v1_findings)
        v2_map = self._build_finding_map(v2_findings)

        all_keys = set(v1_map.keys()) | set(v2_map.keys())
        diffs: list[FindingDiff] = []

        for key in sorted(all_keys):
            f1 = v1_map.get(key)
            f2 = v2_map.get(key)

            if f1 and not f2:
                diffs.append(FindingDiff(
                    key=key,
                    status="fixed",
                    gap_type=self._gap_str(f1.gap_type),
                    v1_severity=f1.severity,
                    requirement_text=f1.requirement_text,
                ))
            elif f2 and not f1:
                diffs.append(FindingDiff(
                    key=key,
                    status="new",
                    gap_type=self._gap_str(f2.gap_type),
                    v2_severity=f2.severity,
                    v2_score=f2.match_score,
                    requirement_text=f2.requirement_text,
                ))
            elif f1 and f2:
                status = self._classify_pair(f1, f2)
                diffs.append(FindingDiff(
                    key=key,
                    status=status,
                    gap_type=self._gap_str(f2.gap_type),
                    v1_severity=f1.severity,
                    v2_severity=f2.severity,
                    v1_score=f1.match_score,
                    v2_score=f2.match_score,
                    requirement_text=f2.requirement_text,
                ))

        return diffs

    def compare(
        self,
        v1_snapshot: ComplianceSnapshot,
        v2_snapshot: ComplianceSnapshot,
        v1_findings: list[GapFinding],
        v2_findings: list[GapFinding],
    ) -> ComparisonResult:
        """Full comparison: snapshot metrics + per-finding diff."""
        snap_diff = self.compare_snapshots(v1_snapshot, v2_snapshot)
        finding_diffs = self.compare_findings(v1_findings, v2_findings)

        summary: dict[str, int] = {"fixed": 0, "new": 0, "unchanged": 0, "worsened": 0}
        for fd in finding_diffs:
            summary[fd.status] = summary.get(fd.status, 0) + 1

        return ComparisonResult(
            snapshot_diff=snap_diff,
            finding_diffs=finding_diffs,
            summary=summary,
        )

    def compute_trend(
        self,
        snapshots: list[ComplianceSnapshot],
    ) -> list[dict[str, Any]]:
        """Build trend data points from ordered snapshots."""
        snapshots_sorted = sorted(snapshots, key=lambda s: s.created_at)
        trend: list[dict[str, Any]] = []
        for snap in snapshots_sorted:
            trend.append({
                "snapshot_id": str(snap.id),
                "timestamp": snap.created_at.isoformat() if snap.created_at else None,
                "score": snap.score,
                "total_findings": snap.total_findings,
                "missing": snap.missing_count,
                "different": snap.different_count,
                "extra": snap.extra_count,
                "inconsistent": snap.inconsistent_count,
                "coverage": snap.coverage_percentage,
                "label": snap.label,
            })
        return trend

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_finding_map(
        self,
        findings: list[GapFinding],
    ) -> dict[str, GapFinding]:
        """Build lookup map keyed by requirement_id → code_entity_id → description."""
        m: dict[str, GapFinding] = {}
        for f in findings:
            key = self._finding_key(f)
            if key not in m:
                m[key] = f
        return m

    def _finding_key(self, f: GapFinding) -> str:
        if f.requirement_id:
            return f"req:{f.requirement_id}"
        if f.code_entity_id:
            return f"ent:{f.code_entity_id}"
        return f"desc:{f.description[:100]}"

    def _classify_pair(self, f1: GapFinding, f2: GapFinding) -> str:
        """Classify the change between two matched findings."""
        sev1 = self.SEVERITY_RANK.get(f1.severity or "warning", 2)
        sev2 = self.SEVERITY_RANK.get(f2.severity or "warning", 2)

        if sev2 > sev1:
            return "worsened"
        if f2.match_score < f1.match_score - 0.1:
            return "worsened"
        if sev2 < sev1 or f2.match_score > f1.match_score + 0.1:
            return "unchanged"
        return "unchanged"

    def _gap_str(self, gap_type: GapType | str) -> str:
        if isinstance(gap_type, GapType):
            return gap_type.value
        return str(gap_type)
