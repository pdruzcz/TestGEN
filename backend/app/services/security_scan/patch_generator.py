"""Patch generator — Epic 4, Story 4.11.

Turns a remediation :class:`Recommendation` (Story 4.9) into a ``git apply``-ready
unified-diff patch for a single finding, validates that the patch's original lines
match the source, and — for batches — groups patches per file and flags pairs whose
edited line ranges overlap or sit adjacent (potential merge conflicts).

The patch is derived data: it is generated on demand and persisted inline in
``SecurityFinding.finding_metadata['patch']`` so it can be previewed and downloaded
without object storage.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field

from app.models.security_finding import SecurityFinding
from app.services.security_scan.diff_generator import generate_unified_diff
from app.services.security_scan.recommendation_engine import Recommendation, RecommendationEngine

logger = logging.getLogger(__name__)

_CONFLICT_CRITICAL = "critical"
_CONFLICT_WARNING = "warning"


@dataclass
class PatchValidation:
    is_valid: bool
    can_apply: bool
    error_message: str | None = None


@dataclass
class ConflictReport:
    patch_a_id: str
    patch_b_id: str
    overlapping_lines: list[int]
    severity: str  # critical (same lines) | warning (adjacent lines)


@dataclass
class PatchResult:
    finding_id: str
    file_path: str
    patch_content: str  # unified diff
    patch_filename: str  # "fix_sql_injection_login_py_a1b2c3.patch"
    is_valid: bool
    conflicts: list[ConflictReport] = field(default_factory=list)


class PatchGenerator:
    """Builds unified-diff patches for findings (single or batch) with conflict detection."""

    def __init__(self, recommendation_engine: RecommendationEngine | None = None) -> None:
        self._engine = recommendation_engine or RecommendationEngine()

    async def generate_patch(
        self,
        finding: SecurityFinding,
        recommendation: Recommendation,
        source_code: str,
    ) -> PatchResult:
        """Create a minimal unified-diff patch for one finding (AC1, AC2)."""
        file_path = finding.file_path or "code"
        line_start = finding.line_start or 1
        original = source_code if source_code else (finding.code_snippet or "")
        patch_content = self._create_unified_diff(
            original, recommendation.fixed_code_snippet, file_path, line_start
        )
        validation = self._validate_patch(patch_content, original)
        return PatchResult(
            finding_id=str(finding.id),
            file_path=file_path,
            patch_content=patch_content,
            patch_filename=self._patch_filename(finding),
            is_valid=validation.is_valid and bool(patch_content),
        )

    async def generate_batch_patches(
        self,
        findings: list[SecurityFinding],
        db,
        engine_mode: str = "native",
    ) -> list[PatchResult]:
        """Generate one patch per finding and annotate same-file conflicts (AC3)."""
        results: list[PatchResult] = []
        for finding in findings:
            recommendation = await self._engine.generate_recommendation(
                finding, source_code=finding.code_snippet, engine_mode=engine_mode
            )
            results.append(
                await self.generate_patch(finding, recommendation, finding.code_snippet or "")
            )

        conflicts = self._detect_conflicts(findings)
        by_finding: dict[str, list[ConflictReport]] = {}
        for conflict in conflicts:
            by_finding.setdefault(conflict.patch_a_id, []).append(conflict)
            by_finding.setdefault(conflict.patch_b_id, []).append(conflict)
        for result in results:
            result.conflicts = by_finding.get(result.finding_id, [])
        return results

    @staticmethod
    def _create_unified_diff(original: str, fixed: str, file_path: str, line_start: int) -> str:
        """Unified diff (3 lines of context) reflecting the finding's location (AC1)."""
        return generate_unified_diff(original, fixed, file_path=file_path, line_start=line_start)

    @staticmethod
    def _validate_patch(patch: str, source_code: str) -> PatchValidation:
        """Check the patch's context/removed lines actually exist in the source (AC2)."""
        if not patch:
            return PatchValidation(is_valid=False, can_apply=False, error_message="Pusty patch")

        source_lines = source_code.splitlines()
        expected: list[str] = []
        for line in patch.splitlines():
            if line.startswith(("---", "+++", "@@")):
                continue
            if line.startswith("+"):
                continue
            if line.startswith((" ", "-")):
                expected.append(line[1:])

        for needle in expected:
            if needle.strip() and needle not in source_lines:
                return PatchValidation(
                    is_valid=False,
                    can_apply=False,
                    error_message=f"Linia patcha nie odpowiada źródłu: {needle.strip()[:60]}",
                )
        return PatchValidation(is_valid=True, can_apply=True)

    def _detect_conflicts(self, findings: list[SecurityFinding]) -> list[ConflictReport]:
        """Flag pairs of same-file findings with overlapping/adjacent line ranges (AC3)."""
        conflicts: list[ConflictReport] = []
        by_file: dict[str, list[SecurityFinding]] = {}
        for finding in findings:
            if finding.file_path:
                by_file.setdefault(finding.file_path, []).append(finding)

        for grouped in by_file.values():
            for i in range(len(grouped)):
                for j in range(i + 1, len(grouped)):
                    report = self._pair_conflict(grouped[i], grouped[j])
                    if report is not None:
                        conflicts.append(report)
        return conflicts

    def _pair_conflict(
        self, a: SecurityFinding, b: SecurityFinding
    ) -> ConflictReport | None:
        a_start, a_end = self._line_range(a)
        b_start, b_end = self._line_range(b)

        overlap = range(max(a_start, b_start), min(a_end, b_end) + 1)
        if len(overlap) > 0:
            return ConflictReport(
                patch_a_id=str(a.id),
                patch_b_id=str(b.id),
                overlapping_lines=list(overlap),
                severity=_CONFLICT_CRITICAL,
            )
        if a_end + 1 == b_start or b_end + 1 == a_start:
            return ConflictReport(
                patch_a_id=str(a.id),
                patch_b_id=str(b.id),
                overlapping_lines=[],
                severity=_CONFLICT_WARNING,
            )
        return None

    @staticmethod
    def _line_range(finding: SecurityFinding) -> tuple[int, int]:
        start = finding.line_start or 1
        end = finding.line_end or start
        return (start, end) if start <= end else (end, start)

    @staticmethod
    def _patch_filename(finding: SecurityFinding) -> str:
        stem = re.sub(r"[^a-zA-Z0-9]+", "_", (finding.file_path or "code")).strip("_").lower()
        vuln = re.sub(r"[^a-zA-Z0-9]+", "_", finding.vulnerability_type).strip("_").lower()
        short = str(finding.id).replace("-", "")[:6] if finding.id else uuid.uuid4().hex[:6]
        return f"fix_{vuln}_{stem}_{short}.patch"
