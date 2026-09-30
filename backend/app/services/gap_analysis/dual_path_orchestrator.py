"""Dual-path orchestrator for functional gap analysis — Epic 5, Story 5.10.

Coordinates the *native* (deterministic fuzzy matching via ComparatorService)
and *LLM* (semantic via LLMGapAnalyzer) gap analysis engines. In ``hybrid``
mode, merges their findings and produces a comparison report.

Pattern follows SecurityDualPathOrchestrator (Story 4.13).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.gap_analysis.comparator import GapFindingData

logger = logging.getLogger(__name__)


@dataclass
class GapComparisonReport:
    """Venn-style breakdown of native vs LLM gap coverage."""

    native_count: int = 0
    llm_count: int = 0
    merged_count: int = 0
    native_only_count: int = 0
    llm_only_count: int = 0
    overlap_count: int = 0
    coverage_improvement_pct: float = 0.0


@dataclass
class GapMergeResult:
    """Outcome of merging native + LLM gap findings."""

    merged_findings: list[GapFindingData] = field(default_factory=list)
    native_only: list[GapFindingData] = field(default_factory=list)
    llm_only: list[GapFindingData] = field(default_factory=list)
    overlap: list[GapFindingData] = field(default_factory=list)


@dataclass
class GapDualPathResult:
    """Result of a dual-path gap analysis run."""

    findings: list[GapFindingData] = field(default_factory=list)
    comparison_report: GapComparisonReport | None = None
    engine_mode_used: str = "native"


def _dedup_key(f: GapFindingData) -> tuple:
    """Build a dedup key from requirement_id + code_entity_id.

    Falls back to description if IDs are missing.
    """
    if f.requirement_id and f.code_entity_id:
        return (f.requirement_id, f.code_entity_id)
    if f.requirement_id:
        return (f.requirement_id, "")
    if f.code_entity_id:
        return ("", f.code_entity_id)
    return ("", f.description[:80])


class GapDualPathOrchestrator:
    """Routes gap analysis through native / llm / hybrid paths."""

    def run_analysis(
        self,
        native_findings: list[GapFindingData],
        llm_findings: list[GapFindingData],
        engine_mode: str = "hybrid",
    ) -> GapDualPathResult:
        """Combine pre-computed native and LLM findings per engine_mode.

        - ``native``: returns native findings unchanged.
        - ``llm``: returns LLM findings unchanged.
        - ``hybrid``: merges both and attaches a comparison report.
        """
        if engine_mode == "native":
            return GapDualPathResult(
                findings=list(native_findings),
                engine_mode_used="native",
            )
        if engine_mode == "llm":
            return GapDualPathResult(
                findings=list(llm_findings),
                engine_mode_used="llm",
            )

        merge = self.merge_findings(native_findings, llm_findings)
        report = self.generate_comparison_report(
            native_findings,
            llm_findings,
            merge,
        )
        return GapDualPathResult(
            findings=merge.merged_findings,
            comparison_report=report,
            engine_mode_used="hybrid",
        )

    @classmethod
    def merge_findings(
        cls,
        native: list[GapFindingData],
        llm: list[GapFindingData],
    ) -> GapMergeResult:
        """Merge by (requirement_id, code_entity_id); native is base.

        Overlapping findings: mark source=hybrid, prefer the higher match_score,
        and use the LLM description if it's longer.
        LLM-only findings are appended with source=llm.
        """
        index: dict[tuple, GapFindingData] = {}
        native_only: list[GapFindingData] = []

        for f in native:
            f.context = {**(f.context or {}), "source": "native"}
            index[_dedup_key(f)] = f
            native_only.append(f)

        llm_only: list[GapFindingData] = []
        overlap: list[GapFindingData] = []

        for f in llm:
            key = _dedup_key(f)
            base = index.get(key)
            if base is not None:
                # Merge: native is authoritative, LLM enriches
                base.context = {**(base.context or {}), "source": "hybrid"}
                if len(f.description) > len(base.description):
                    base.description = f.description
                if f.match_score > base.match_score:
                    base.match_score = f.match_score
                    base.match_method = "hybrid"
                overlap.append(base)
                if base in native_only:
                    native_only.remove(base)
            else:
                f.context = {**(f.context or {}), "source": "llm"}
                index[key] = f
                llm_only.append(f)

        return GapMergeResult(
            merged_findings=list(index.values()),
            native_only=native_only,
            llm_only=llm_only,
            overlap=overlap,
        )

    @staticmethod
    def generate_comparison_report(
        native: list[GapFindingData],
        llm: list[GapFindingData],
        merge: GapMergeResult,
    ) -> GapComparisonReport:
        """Build the native-vs-LLM coverage report."""
        merged_count = len(merge.merged_findings)
        llm_only_n = len(merge.llm_only)
        coverage = (
            round(
                (llm_only_n / merged_count) * 100,
                1,
            )
            if merged_count
            else 0.0
        )
        return GapComparisonReport(
            native_count=len(native),
            llm_count=len(llm),
            merged_count=merged_count,
            native_only_count=len(merge.native_only),
            llm_only_count=llm_only_n,
            overlap_count=len(merge.overlap),
            coverage_improvement_pct=coverage,
        )
