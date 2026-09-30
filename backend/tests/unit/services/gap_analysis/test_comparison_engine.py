"""Unit tests for ComparisonEngine — Epic 5, Story 5.7.

Tests snapshot comparison (score deltas, direction), per-finding diff
(fixed/new/unchanged/worsened), and trend computation.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.gap_analysis.comparison_engine import ComparisonEngine


def _make_snapshot(
    score: float = 80.0,
    total: int = 10,
    missing: int = 3,
    different: int = 2,
    extra: int = 4,
    inconsistent: int = 1,
    avg_match: float = 0.65,
    coverage: float = 60.0,
    label: str | None = None,
    created_at: datetime | None = None,
):
    return SimpleNamespace(
        id="snap-id",
        project_id="proj-id",
        tenant_id="tid",
        analysis_id=None,
        score=score,
        total_findings=total,
        missing_count=missing,
        different_count=different,
        extra_count=extra,
        inconsistent_count=inconsistent,
        avg_match_score=avg_match,
        coverage_percentage=coverage,
        label=label,
        notes=None,
        created_at=created_at or datetime(2026, 7, 1, tzinfo=timezone.utc),
        updated_at=None,
    )


def _make_finding(
    requirement_id: str = "REQ-001",
    code_entity_id: str | None = "fn:calculateTax",
    gap_type="missing",
    severity="warning",
    match_score=0.5,
    description="Brak implementacji",
    requirement_text="System powinien...",
):
    return SimpleNamespace(
        requirement_id=requirement_id,
        code_entity_id=code_entity_id,
        gap_type=gap_type,
        severity=severity,
        match_score=match_score,
        description=description,
        requirement_text=requirement_text,
    )


# ── Snapshot comparison ──────────────────────────────────────────────────────


class TestCompareSnapshots:
    def test_improved_direction(self):
        eng = ComparisonEngine()
        v1 = _make_snapshot(score=60.0)
        v2 = _make_snapshot(score=85.0)
        diff = eng.compare_snapshots(v1, v2)
        assert diff.direction == "improved"
        assert diff.score_delta == 25.0

    def test_regressed_direction(self):
        eng = ComparisonEngine()
        v1 = _make_snapshot(score=80.0)
        v2 = _make_snapshot(score=50.0)
        diff = eng.compare_snapshots(v1, v2)
        assert diff.direction == "regressed"
        assert diff.score_delta == -30.0

    def test_stable_direction(self):
        eng = ComparisonEngine()
        v1 = _make_snapshot(score=75.0)
        v2 = _make_snapshot(score=75.2)
        diff = eng.compare_snapshots(v1, v2)
        assert diff.direction == "stable"

    def test_gap_count_deltas(self):
        eng = ComparisonEngine()
        v1 = _make_snapshot(missing=5, different=3, extra=2, inconsistent=1)
        v2 = _make_snapshot(missing=2, different=4, extra=1, inconsistent=3)
        diff = eng.compare_snapshots(v1, v2)
        assert diff.missing_delta == -3
        assert diff.different_delta == 1
        assert diff.extra_delta == -1
        assert diff.inconsistent_delta == 2

    def test_total_delta(self):
        eng = ComparisonEngine()
        v1 = _make_snapshot(total=12)
        v2 = _make_snapshot(total=8)
        diff = eng.compare_snapshots(v1, v2)
        assert diff.total_delta == -4

    def test_coverage_delta(self):
        eng = ComparisonEngine()
        v1 = _make_snapshot(coverage=50.0)
        v2 = _make_snapshot(coverage=75.0)
        diff = eng.compare_snapshots(v1, v2)
        assert diff.coverage_delta == 25.0


# ── Per-finding comparison ───────────────────────────────────────────────────


class TestCompareFindings:
    def test_fixed_finding(self):
        eng = ComparisonEngine()
        f1 = [_make_finding(requirement_id="REQ-001")]
        f2 = []
        diffs = eng.compare_findings(f1, f2)
        assert len(diffs) == 1
        assert diffs[0].status == "fixed"

    def test_new_finding(self):
        eng = ComparisonEngine()
        f1 = []
        f2 = [_make_finding(requirement_id="REQ-002")]
        diffs = eng.compare_findings(f1, f2)
        assert len(diffs) == 1
        assert diffs[0].status == "new"

    def test_unchanged_finding(self):
        eng = ComparisonEngine()
        f1 = [_make_finding(requirement_id="REQ-001", severity="warning", match_score=0.5)]
        f2 = [_make_finding(requirement_id="REQ-001", severity="warning", match_score=0.5)]
        diffs = eng.compare_findings(f1, f2)
        assert len(diffs) == 1
        assert diffs[0].status == "unchanged"

    def test_worsened_severity(self):
        eng = ComparisonEngine()
        f1 = [_make_finding(requirement_id="REQ-001", severity="warning")]
        f2 = [_make_finding(requirement_id="REQ-001", severity="critical")]
        diffs = eng.compare_findings(f1, f2)
        assert diffs[0].status == "worsened"

    def test_worsened_score_drop(self):
        eng = ComparisonEngine()
        f1 = [_make_finding(requirement_id="REQ-001", match_score=0.8)]
        f2 = [_make_finding(requirement_id="REQ-001", match_score=0.5)]
        diffs = eng.compare_findings(f1, f2)
        assert diffs[0].status == "worsened"

    def test_mixed_findings(self):
        eng = ComparisonEngine()
        f1 = [
            _make_finding(requirement_id="REQ-001"),  # fixed
            _make_finding(requirement_id="REQ-002", severity="warning"),
        ]
        f2 = [
            _make_finding(requirement_id="REQ-002", severity="warning"),  # unchanged
            _make_finding(requirement_id="REQ-003"),  # new
        ]
        diffs = eng.compare_findings(f1, f2)
        statuses = {d.key: d.status for d in diffs}
        assert statuses["req:REQ-001"] == "fixed"
        assert statuses["req:REQ-002"] == "unchanged"
        assert statuses["req:REQ-003"] == "new"

    def test_empty_both(self):
        eng = ComparisonEngine()
        assert eng.compare_findings([], []) == []


# ── Full comparison ──────────────────────────────────────────────────────────


class TestFullComparison:
    def test_summary_counts(self):
        eng = ComparisonEngine()
        snap1 = _make_snapshot(score=50.0, total=5)
        snap2 = _make_snapshot(score=80.0, total=3)
        f1 = [
            _make_finding(requirement_id="REQ-001"),  # fixed
            _make_finding(requirement_id="REQ-002", severity="warning"),
        ]
        f2 = [
            _make_finding(requirement_id="REQ-002", severity="warning"),  # unchanged
            _make_finding(requirement_id="REQ-003"),  # new
        ]
        result = eng.compare(snap1, snap2, f1, f2)
        assert result.fixed_count == 1
        assert result.new_count == 1
        assert result.unchanged_count == 1
        assert result.worsened_count == 0
        assert result.snapshot_diff.direction == "improved"


# ── Trend computation ────────────────────────────────────────────────────────


class TestComputeTrend:
    def test_ordered_by_timestamp(self):
        eng = ComparisonEngine()
        snaps = [
            _make_snapshot(score=50.0, created_at=datetime(2026, 7, 3, tzinfo=timezone.utc)),
            _make_snapshot(score=40.0, created_at=datetime(2026, 7, 1, tzinfo=timezone.utc)),
            _make_snapshot(score=70.0, created_at=datetime(2026, 7, 2, tzinfo=timezone.utc)),
        ]
        trend = eng.compute_trend(snaps)
        assert len(trend) == 3
        assert trend[0]["score"] == 40.0  # oldest first
        assert trend[1]["score"] == 70.0
        assert trend[2]["score"] == 50.0

    def test_empty_snapshots(self):
        eng = ComparisonEngine()
        assert eng.compute_trend([]) == []

    def test_trend_has_gap_counts(self):
        eng = ComparisonEngine()
        snap = _make_snapshot(
            score=75.0,
            missing=3,
            different=2,
            extra=1,
            inconsistent=0,
            coverage=65.0,
        )
        trend = eng.compute_trend([snap])
        assert trend[0]["missing"] == 3
        assert trend[0]["different"] == 2
        assert trend[0]["extra"] == 1
        assert trend[0]["inconsistent"] == 0
        assert trend[0]["coverage"] == 65.0
