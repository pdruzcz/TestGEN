"""Dual-path security orchestrator — Story 4.13.

Coordinates the *native* (deterministic rules) and *LLM* (semantic) security
engines per module and, in ``hybrid`` mode, merges their findings and produces a
comparison report. The merge keeps native findings as the authoritative base and
treats LLM findings as enrichment (better descriptions) or net-new coverage.

The merge and comparison logic are pure/static so they are fully testable
offline; ``run_analysis`` wires them to already-computed finding lists.
"""

import logging
from dataclasses import dataclass, field

from app.services.security_scan.rules import RawFinding

logger = logging.getLogger(__name__)

# Dedup key for cross-path matching.
_DedupKey = tuple


@dataclass
class ComparisonReport:
    """Venn-style breakdown of native vs LLM coverage (AC3)."""

    native_count: int = 0
    llm_count: int = 0
    merged_count: int = 0
    native_only: int = 0
    llm_only: int = 0
    overlap_count: int = 0
    coverage_improvement_pct: float = 0.0


@dataclass
class MergeResult:
    """Outcome of merging native + LLM findings."""

    merged_findings: list[RawFinding] = field(default_factory=list)
    native_only: list[RawFinding] = field(default_factory=list)
    llm_only: list[RawFinding] = field(default_factory=list)
    overlap: list[RawFinding] = field(default_factory=list)


@dataclass
class DualPathResult:
    """Result of a dual-path run for one scan."""

    findings: list[RawFinding] = field(default_factory=list)
    comparison_report: ComparisonReport | None = None
    engine_mode_used: str = "native"


class SecurityDualPathOrchestrator:
    """Routes a security analysis through native / llm / hybrid paths."""

    def run_analysis(
        self,
        native_findings: list[RawFinding],
        llm_findings: list[RawFinding],
        engine_mode: str = "hybrid",
    ) -> DualPathResult:
        """Combine pre-computed native and LLM findings per ``engine_mode``.

        - ``native``: returns native findings unchanged.
        - ``llm``: returns LLM findings unchanged.
        - ``hybrid``: merges both and attaches a comparison report.
        """
        if engine_mode == "native":
            return DualPathResult(findings=list(native_findings), engine_mode_used="native")
        if engine_mode == "llm":
            return DualPathResult(findings=list(llm_findings), engine_mode_used="llm")

        merge = self.merge_findings(native_findings, llm_findings)
        report = self.generate_comparison_report(native_findings, llm_findings, merge)
        return DualPathResult(
            findings=merge.merged_findings,
            comparison_report=report,
            engine_mode_used="hybrid",
        )

    @staticmethod
    def _key(finding: RawFinding) -> _DedupKey:
        return (finding.file_path, finding.line_start, finding.vulnerability_type)

    @classmethod
    def merge_findings(
        cls,
        native: list[RawFinding],
        llm: list[RawFinding],
    ) -> MergeResult:
        """Merge by (file_path, line_start, vulnerability_type); native is base.

        Overlapping findings are marked ``source="hybrid"``, get a small
        confidence boost and inherit the LLM description/recommendation when the
        native finding lacks a richer one. LLM-only findings are appended.
        """
        index: dict[_DedupKey, RawFinding] = {}
        native_only: list[RawFinding] = []
        overlap: list[RawFinding] = []
        for f in native:
            index[cls._key(f)] = f
            native_only.append(f)

        llm_only: list[RawFinding] = []
        for f in llm:
            key = cls._key(f)
            base = index.get(key)
            if base is not None:
                base.source = "hybrid"
                base.confidence = round(min(0.99, base.confidence + 0.1), 2)
                # LLM enrichment: prefer the longer, more contextual description.
                if f.description and len(f.description) > len(base.description or ""):
                    base.description = f.description
                if f.recommendation and not base.recommendation:
                    base.recommendation = f.recommendation
                overlap.append(base)
                if base in native_only:
                    native_only.remove(base)
            else:
                index[key] = f
                llm_only.append(f)

        return MergeResult(
            merged_findings=list(index.values()),
            native_only=native_only,
            llm_only=llm_only,
            overlap=overlap,
        )

    @staticmethod
    def generate_comparison_report(
        native: list[RawFinding],
        llm: list[RawFinding],
        merge: MergeResult,
    ) -> ComparisonReport:
        """Build the native-vs-LLM coverage report (AC3)."""
        merged_count = len(merge.merged_findings)
        llm_only = len(merge.llm_only)
        coverage = round((llm_only / merged_count) * 100, 1) if merged_count else 0.0
        return ComparisonReport(
            native_count=len(native),
            llm_count=len(llm),
            merged_count=merged_count,
            native_only=len(merge.native_only),
            llm_only=llm_only,
            overlap_count=len(merge.overlap),
            coverage_improvement_pct=coverage,
        )
