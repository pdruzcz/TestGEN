"""GapClassifier — classifies mapping results into 4 gap types.

Epic 5, Story 5.2.

Takes the mapping output from ComparatorService (scores per requirement-code
pair) and produces structured GapFindingData with:
- gap_type: missing | different | extra | inconsistent
- context with excerpts (requirement + code)
- severity based on rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.analysis.gap_analyzer import CodeEntity
from app.services.gap_analysis.classification_rules import (
    CONTRADICTION_INDICATORS,
    DIVERGENT_THRESHOLD,
    EXCLUDE_PATTERNS,
    INCONSISTENT_SCORE_SPREAD,
    MISSING_THRESHOLD,
    PRIORITY_SEVERITY,
    SEVERITY_MAP,
)
from app.services.gap_analysis.comparator import (
    GapFindingData,
    RequirementData,
)


@dataclass
class EntityMapping:
    """Best-match mapping for a single requirement."""

    requirement: RequirementData
    best_entity: CodeEntity | None
    best_score: float
    match_method: str = "combined"


@dataclass
class TypeSummary:
    """Count and percentage for a single gap type."""

    count: int = 0
    percentage: float = 0.0


class GapClassifier:
    """Classifies requirement-code mappings into gap types."""

    def classify(
        self,
        mappings: list[EntityMapping],
        requirements: list[RequirementData],
        code_entities: list[CodeEntity],
        all_scores: dict[str, dict[str, float]] | None = None,
    ) -> tuple[list[GapFindingData], dict[str, TypeSummary]]:
        """Classify all mappings and return findings + per-type summary.

        Args:
            mappings: Best-match per requirement.
            requirements: All requirements.
            code_entities: All code entities.
            all_scores: Optional full score matrix {req_id: {entity_id: score}}.

        Returns:
            List of GapFindingData and a dict of TypeSummary per gap_type.
        """
        findings: list[GapFindingData] = []
        matched_entity_ids: set[str] = set()

        # Phase 1: Detect inconsistent (cross-requirement contradictions)
        inconsistent_entities = self._detect_inconsistent(mappings, all_scores)

        # Phase 2: Classify each requirement mapping
        for m in mappings:
            if m.best_entity and m.best_score >= MISSING_THRESHOLD:
                matched_entity_ids.add(m.best_entity.entity_id)

            if m.best_entity is None or m.best_score < MISSING_THRESHOLD:
                findings.append(self._classify_missing(m))
            elif m.best_score < DIVERGENT_THRESHOLD:
                findings.append(self._classify_different(m))
            # else: good match — not a gap

        # Phase 3: Flag inconsistent findings
        for entity_id, req_ids in inconsistent_entities.items():
            for req_id in req_ids:
                # Add or upgrade finding for this requirement to inconsistent
                existing = next(
                    (f for f in findings if f.requirement_id == req_id), None
                )
                if existing:
                    existing.gap_type = "inconsistent"
                    existing.severity = "critical"
                    existing.description = (
                        f"Byt kodu jest mapowany do sprzecznych wymagań "
                        f"({', '.join(req_ids)})"
                    )
                else:
                    req = next(
                        (r for r in requirements if r.req_id == req_id), None
                    )
                    if req:
                        entity = next(
                            (e for e in code_entities if e.entity_id == entity_id),
                            None,
                        )
                        findings.append(GapFindingData(
                            requirement_id=req_id,
                            code_entity_id=entity_id,
                            gap_type="inconsistent",
                            description=(
                                f"Byt kodu '{entity.name if entity else entity_id}' "
                                f"mapowany do sprzecznych wymagań"
                            ),
                            requirement_text=req.text,
                            code_reference=(
                                f"{entity.file_path}:{entity.line_number}"
                                if entity else None
                            ),
                            match_score=0.0,
                            match_method="inconsistency",
                            context={"conflicting_requirements": req_ids},
                            severity="critical",
                        ))

        # Phase 4: Find extra code entities
        findings.extend(
            self._classify_extra(code_entities, matched_entity_ids, requirements)
        )

        # Build summary
        summary = self._build_summary(findings, len(requirements))

        return findings, summary

    # ── Individual classifiers ───────────────────────────────────────────────

    def _classify_missing(self, m: EntityMapping) -> GapFindingData:
        """Requirement with no matching code entity."""
        severity = PRIORITY_SEVERITY.get(m.requirement.priority, "warning")
        return GapFindingData(
            requirement_id=m.requirement.req_id,
            code_entity_id=None,
            gap_type="missing",
            description=(
                f"Wymaganie bez implementacji w kodzie "
                f"(score: {m.best_score:.1f}%)"
            ),
            requirement_text=m.requirement.text,
            code_reference=None,
            match_score=round(m.best_score, 1),
            match_method=m.match_method if m.best_entity else "none",
            context=self._build_context(m.requirement, m.best_entity, m.best_score),
            severity=severity,
        )

    def _classify_different(self, m: EntityMapping) -> GapFindingData:
        """Requirement with partial/divergent code match."""
        return GapFindingData(
            requirement_id=m.requirement.req_id,
            code_entity_id=m.best_entity.entity_id,
            gap_type="different",
            description=(
                f"Implementacja '{m.best_entity.name}' częściowo "
                f"różni się od wymagania (score: {m.best_score:.1f}%)"
            ),
            requirement_text=m.requirement.text,
            code_reference=f"{m.best_entity.file_path}:{m.best_entity.line_number}",
            match_score=round(m.best_score, 1),
            match_method=m.match_method,
            context=self._build_context(m.requirement, m.best_entity, m.best_score),
            severity="warning",
        )

    def _classify_extra(
        self,
        code_entities: list[CodeEntity],
        matched_ids: set[str],
        requirements: list[RequirementData],
    ) -> list[GapFindingData]:
        """Code entities with no matching requirement."""
        extras: list[GapFindingData] = []

        for entity in code_entities:
            if entity.entity_id in matched_ids:
                continue
            if EXCLUDE_PATTERNS.search(entity.name):
                continue
            # Check if mentioned in any requirement text
            if self._entity_in_requirements(entity, requirements):
                continue

            extras.append(GapFindingData(
                requirement_id=None,
                code_entity_id=entity.entity_id,
                gap_type="extra",
                description=(
                    f"Byt kodu '{entity.name}' ({entity.type}) "
                    f"bez odpowiednika w dokumentacji"
                ),
                requirement_text=None,
                code_reference=f"{entity.file_path}:{entity.line_number}",
                match_score=0.0,
                match_method="none",
                context={
                    "entity_name": entity.name,
                    "entity_type": entity.type,
                    "file_path": entity.file_path,
                    "line_number": entity.line_number,
                    "docstring": entity.docstring[:200] if entity.docstring else None,
                },
                severity="info",
            ))

        return extras

    def _detect_inconsistent(
        self,
        mappings: list[EntityMapping],
        all_scores: dict[str, dict[str, float]] | None,
    ) -> dict[str, list[str]]:
        """Detect code entities mapped to multiple requirements with conflicts.

        Returns: {entity_id: [req_id, req_id, ...]}
        """
        if not all_scores:
            return {}

        # Group requirements by their best entity — only those that score
        # above MISSING_THRESHOLD count as real mappings for inconsistency
        entity_to_reqs: dict[str, list[tuple[str, float]]] = {}
        for m in mappings:
            if m.best_entity and m.best_score >= MISSING_THRESHOLD:
                eid = m.best_entity.entity_id
                entity_to_reqs.setdefault(eid, []).append(
                    (m.requirement.req_id, m.best_score)
                )

        inconsistent: dict[str, list[str]] = {}
        for eid, req_scores in entity_to_reqs.items():
            if len(req_scores) < 2:
                continue
            scores = [s for _, s in req_scores]
            spread = max(scores) - min(scores)
            if spread >= INCONSISTENT_SCORE_SPREAD:
                inconsistent[eid] = [r for r, _ in req_scores]

        return inconsistent

    # ── Context builder ──────────────────────────────────────────────────────

    def _build_context(
        self,
        req: RequirementData,
        entity: CodeEntity | None,
        score: float,
    ) -> dict[str, Any]:
        """Build context with excerpts and metadata."""
        ctx: dict[str, Any] = {
            "best_candidate": entity.name if entity else None,
            "best_score": round(score, 1),
            "requirement_excerpt": self._excerpt(req.text, 150),
            "requirement_priority": req.priority,
        }
        if entity:
            ctx["code_excerpt"] = self._excerpt(
                entity.docstring or entity.name, 150
            )
            ctx["file_path"] = entity.file_path
            ctx["line_number"] = entity.line_number
            ctx["entity_type"] = entity.type
        return ctx

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _excerpt(self, text: str, max_len: int) -> str:
        """Truncate text to max_len, adding ellipsis."""
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."

    def _entity_in_requirements(
        self, entity: CodeEntity, requirements: list[RequirementData]
    ) -> bool:
        """Check if entity name appears in any requirement text."""
        import re
        name_clean = re.sub(r"[^a-z0-9]", "", entity.name.lower())
        for req in requirements:
            req_clean = re.sub(r"[^a-z0-9]", "", req.text.lower())
            if name_clean and name_clean in req_clean:
                return True
            if entity.name.lower() in req.text.lower():
                return True
        return False

    def _build_summary(
        self, findings: list[GapFindingData], total_reqs: int
    ) -> dict[str, TypeSummary]:
        """Build per-type summary with counts and percentages."""
        types = ["missing", "different", "extra", "inconsistent"]
        total_findings = len(findings)

        summary: dict[str, TypeSummary] = {}
        for t in types:
            count = sum(1 for f in findings if f.gap_type == t)
            pct = (count / total_findings * 100.0) if total_findings > 0 else 0.0
            summary[t] = TypeSummary(count=count, percentage=round(pct, 1))

        return summary
