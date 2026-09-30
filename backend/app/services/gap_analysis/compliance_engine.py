"""ComplianceEngine — compute compliance scores from gap findings.

Epic 5, Story 5.3.

Computes scores on-the-fly from the ``gap_findings`` table — no persistence.
Scores are 0-100 where 100 = full compliance (no gaps) and 0 = maximally
non-compliant.

Penalty weights per gap type and severity:

    missing+critical     = 15
    missing+warning      = 8
    missing+info         = 3
    different+critical   = 10
    different+warning    = 5
    different+info       = 2
    inconsistent+critical   = 10
    inconsistent+warning    = 5
    inconsistent+info       = 2
    extra+critical       = 5
    extra+warning        = 3
    extra+info           = 1
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any

from app.models.gap_finding import GapFinding, GapType

# ── Penalty weights ──────────────────────────────────────────────────────────

PENALTY_WEIGHTS: dict[str, dict[str, float]] = {
    GapType.MISSING.value: {"critical": 15.0, "warning": 8.0, "info": 3.0},
    GapType.DIFFERENT.value: {"critical": 10.0, "warning": 5.0, "info": 2.0},
    GapType.INCONSISTENT.value: {"critical": 10.0, "warning": 5.0, "info": 2.0},
    GapType.EXTRA.value: {"critical": 5.0, "warning": 3.0, "info": 1.0},
}


@dataclass
class ComplianceScore:
    """Single compliance score for project, module, or function."""

    score: float
    total_findings: int
    breakdown: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleScore:
    """Compliance score for a single module (file)."""

    file_path: str
    score: float
    total_findings: int
    breakdown: dict[str, int] = field(default_factory=dict)


@dataclass
class FunctionScore:
    """Compliance score for a single function/code entity."""

    code_entity_id: str
    score: float
    total_findings: int
    breakdown: dict[str, int] = field(default_factory=dict)
    file_path: str | None = None
    entity_name: str | None = None


class ComplianceEngine:
    """Compute compliance scores from gap findings."""

    def calculate_project_score(self, findings: list[GapFinding]) -> ComplianceScore:
        """Global project compliance score (0-100)."""
        penalty = 0.0
        breakdown: dict[str, int] = {
            GapType.MISSING.value: 0,
            GapType.DIFFERENT.value: 0,
            GapType.EXTRA.value: 0,
            GapType.INCONSISTENT.value: 0,
        }

        for f in findings:
            gap_type = f.gap_type.value if isinstance(f.gap_type, GapType) else str(f.gap_type)
            severity = f.severity or "warning"
            breakdown[gap_type] = breakdown.get(gap_type, 0) + 1
            penalty += self._penalty(gap_type, severity)

        score = max(0.0, 100.0 - penalty)
        return ComplianceScore(
            score=round(score, 1),
            total_findings=len(findings),
            breakdown=breakdown,
        )

    def calculate_module_scores(self, findings: list[GapFinding]) -> list[ModuleScore]:
        """Scores grouped by file_path (module)."""
        by_module: dict[str, list[GapFinding]] = {}
        for f in findings:
            path = self._extract_file_path(f)
            by_module.setdefault(path, []).append(f)

        results: list[ModuleScore] = []
        for file_path, module_findings in sorted(by_module.items()):
            penalty = 0.0
            breakdown: dict[str, int] = {}
            for f in module_findings:
                gap_type = f.gap_type.value if isinstance(f.gap_type, GapType) else str(f.gap_type)
                severity = f.severity or "warning"
                breakdown[gap_type] = breakdown.get(gap_type, 0) + 1
                penalty += self._penalty(gap_type, severity)
            score = max(0.0, 100.0 - penalty)
            results.append(ModuleScore(
                file_path=file_path,
                score=round(score, 1),
                total_findings=len(module_findings),
                breakdown=breakdown,
            ))
        return results

    def calculate_function_scores(self, findings: list[GapFinding]) -> list[FunctionScore]:
        """Scores per code_entity_id (function/method/class)."""
        by_entity: dict[str, list[GapFinding]] = {}
        entity_meta: dict[str, dict[str, Any]] = {}

        for f in findings:
            eid = f.code_entity_id or "—unmapped—"
            by_entity.setdefault(eid, []).append(f)
            if eid not in entity_meta:
                entity_meta[eid] = {
                    "file_path": self._extract_file_path(f),
                    "entity_name": self._extract_entity_name(f),
                }

        results: list[FunctionScore] = []
        for entity_id, entity_findings in sorted(by_entity.items()):
            penalty = 0.0
            breakdown: dict[str, int] = {}
            for f in entity_findings:
                gap_type = f.gap_type.value if isinstance(f.gap_type, GapType) else str(f.gap_type)
                severity = f.severity or "warning"
                breakdown[gap_type] = breakdown.get(gap_type, 0) + 1
                penalty += self._penalty(gap_type, severity)
            score = max(0.0, 100.0 - penalty)
            meta = entity_meta.get(entity_id, {})
            results.append(FunctionScore(
                code_entity_id=entity_id,
                score=round(score, 1),
                total_findings=len(entity_findings),
                breakdown=breakdown,
                file_path=meta.get("file_path"),
                entity_name=meta.get("entity_name"),
            ))
        return results

    def export_csv(self, findings: list[GapFinding]) -> str:
        """Export compliance report as CSV string."""
        project_score = self.calculate_project_score(findings)
        module_scores = self.calculate_module_scores(findings)
        function_scores = self.calculate_function_scores(findings)

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["=== COMPLIANCE REPORT ==="])
        writer.writerow([])
        writer.writerow(["Project Score", project_score.score, "Total findings", project_score.total_findings])
        writer.writerow([])

        writer.writerow(["Breakdown"])
        for gap_type, count in project_score.breakdown.items():
            writer.writerow([gap_type, count])
        writer.writerow([])

        writer.writerow(["=== MODULE SCORES ==="])
        writer.writerow(["File", "Score", "Findings", "Missing", "Different", "Extra", "Inconsistent"])
        for m in module_scores:
            writer.writerow([
                m.file_path, m.score, m.total_findings,
                m.breakdown.get("missing", 0),
                m.breakdown.get("different", 0),
                m.breakdown.get("extra", 0),
                m.breakdown.get("inconsistent", 0),
            ])
        writer.writerow([])

        writer.writerow(["=== FUNCTION SCORES ==="])
        writer.writerow(["Entity ID", "Entity Name", "File", "Score", "Findings"])
        for fn in function_scores:
            writer.writerow([
                fn.code_entity_id, fn.entity_name or "", fn.file_path or "",
                fn.score, fn.total_findings,
            ])

        return output.getvalue()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _penalty(self, gap_type: str, severity: str) -> float:
        weights = PENALTY_WEIGHTS.get(gap_type, {})
        return weights.get(severity, weights.get("warning", 5.0))

    def _extract_file_path(self, f: GapFinding) -> str:
        """Extract file_path from code_reference or context."""
        if f.code_reference:
            parts = f.code_reference.rsplit(":", 1)
            if len(parts) == 2:
                return parts[0]
            return f.code_reference
        if f.context and isinstance(f.context, dict):
            fp = f.context.get("file_path")
            if fp:
                return str(fp)
        return "—unknown—"

    def _extract_entity_name(self, f: GapFinding) -> str | None:
        """Extract entity name from context."""
        if f.context and isinstance(f.context, dict):
            name = f.context.get("entity_name") or f.context.get("best_candidate")
            if name:
                return str(name)
        return f.code_entity_id
