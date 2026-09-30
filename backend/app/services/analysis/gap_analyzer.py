"""Gap analysis module for Epic 2.

This module compares documentation requirements with code implementation
to identify gaps, divergences, and coverage issues.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.document import (
        DocumentStructure,
        ExtractedRequirementSchema,
    )


@dataclass
class CodeEntity:
    """Code entity (function, class, module) for comparison."""

    entity_id: str
    name: str
    type: str  # 'function', 'class', 'module', 'method'
    file_path: str
    line_number: int
    language: str
    docstring: str | None


@dataclass
class GapAnalysisResult:
    """Result of comparing requirement with code."""

    requirement_id: str
    requirement_text: str
    status: str  # 'implemented', 'not_implemented', 'partial', 'divergent'
    mapped_entities: list[str]
    issue_description: str | None
    confidence: float


@dataclass
class CoverageReport:
    """Overall coverage report for document vs code."""

    total_requirements: int
    implemented: int
    not_implemented: int
    partial: int
    divergent: int
    coverage_percentage: float
    critical_gaps: list[str]  # Requirement IDs of critical gaps


class GapAnalyzer:
    """Analyze gaps between documentation and code implementation.

    Compares extracted requirements with code entities to determine:
    - Which requirements are implemented
    - Which are missing
    - Which have partial/divergent implementation
    """

    def __init__(self) -> None:
        self.fuzzy_match_threshold: float = 0.6

    def analyze(
        self,
        doc: DocumentStructure,
        requirements: list[ExtractedRequirementSchema],
        code_entities: list[CodeEntity],
    ) -> CoverageReport:
        """Analyze coverage gaps between docs and code (aggregate report only).

        Args:
            doc: Document structure
            requirements: Extracted requirements
            code_entities: Available code entities

        Returns:
            Coverage report with gap analysis
        """
        report, _ = self.analyze_detailed(doc, requirements, code_entities)
        return report

    def analyze_detailed(
        self,
        doc: DocumentStructure,
        requirements: list[ExtractedRequirementSchema],
        code_entities: list[CodeEntity],
    ) -> tuple[CoverageReport, list[GapAnalysisResult]]:
        """Analyze gaps and return both the aggregate report and per-item list.

        Story 2.8 closure: ``analyze`` only surfaces the aggregate
        ``CoverageReport``; this variant also returns the per-requirement
        ``GapAnalysisResult`` list so the pipeline/API can persist and serve
        each item. The matching algorithm is unchanged.
        """
        results: list[GapAnalysisResult] = [self._analyze_requirement(req, code_entities) for req in requirements]
        return self._build_report(results), results

    def _build_report(self, results: list[GapAnalysisResult]) -> CoverageReport:
        """Aggregate per-requirement results into a coverage report."""
        total = len(results)
        implemented = len([r for r in results if r.status == "implemented"])
        not_implemented = len([r for r in results if r.status == "not_implemented"])
        partial = len([r for r in results if r.status == "partial"])
        divergent = len([r for r in results if r.status == "divergent"])

        coverage_percentage = (implemented / total * 100) if total > 0 else 0.0

        # Identify critical gaps (critical or high priority, not implemented)
        critical_gaps = [
            r.requirement_id
            for r in results
            if r.status in ["not_implemented", "divergent", "partial"] and self._is_critical_requirement(r)
        ]

        return CoverageReport(
            total_requirements=total,
            implemented=implemented,
            not_implemented=not_implemented,
            partial=partial,
            divergent=divergent,
            coverage_percentage=coverage_percentage,
            critical_gaps=critical_gaps,
        )

    def _analyze_requirement(
        self,
        req: ExtractedRequirementSchema,
        code_entities: list[CodeEntity],
    ) -> GapAnalysisResult:
        """Analyze a single requirement against code entities.

        Args:
            req: Requirement to analyze
            code_entities: Available code entities

        Returns:
            Gap analysis result
        """
        # Find potential matches in code
        mapped_entities = self._find_matching_entities(req, code_entities)

        if not mapped_entities:
            return GapAnalysisResult(
                requirement_id=req["req_id"],
                requirement_text=req["text"],
                status="not_implemented",
                mapped_entities=[],
                issue_description="Brak implementacji w kodzie",
                confidence=0.0,
            )

        # Assess implementation quality
        confidence = self._calculate_implementation_confidence(req, mapped_entities, code_entities)

        if confidence >= 0.9:
            status = "implemented"
        elif confidence >= 0.6:
            status = "partial"
        else:
            status = "divergent"

        issue_description = self._generate_issue_description(req, mapped_entities, status)

        return GapAnalysisResult(
            requirement_id=req["req_id"],
            requirement_text=req["text"],
            status=status,
            mapped_entities=[e.name for e in mapped_entities],
            issue_description=issue_description,
            confidence=confidence,
        )

    def _find_matching_entities(
        self,
        req: ExtractedRequirementSchema,
        code_entities: list[CodeEntity],
    ) -> list[CodeEntity]:
        """Find code entities that match the requirement.

        Args:
            req: Requirement to match
            code_entities: Available code entities

        Returns:
            List of matching code entities
        """
        matches: list[tuple[CodeEntity, float]] = []
        req_text_lower = req["text"].lower()

        # Extract key terms from requirement
        req_terms = self._extract_requirement_terms(req["text"])

        for entity in code_entities:
            similarity = self._calculate_entity_similarity(req_text_lower, req_terms, entity)

            if similarity >= self.fuzzy_match_threshold:
                matches.append((entity, similarity))

        # Sort by similarity and return top matches
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches[:3]]  # Top 3 matches

    def _calculate_entity_similarity(
        self,
        req_text_lower: str,
        req_terms: list[str],
        entity: CodeEntity,
    ) -> float:
        """Calculate similarity between requirement and code entity.

        Args:
            req_text_lower: Lowercase requirement text
            req_terms: Key terms from requirement
            entity: Code entity to compare

        Returns:
            Similarity score 0-1
        """
        entity_lower = entity.name.lower()
        similarity = 0.0

        # Direct name match (high weight)
        if entity_lower in req_text_lower:
            similarity += 0.5

        # Term match (medium weight)
        for term in req_terms:
            if term.lower() in entity_lower or entity_lower in term.lower():
                similarity += 0.2

        # Docstring match (lower weight)
        if entity.docstring:
            docstring_lower = entity.docstring.lower()
            words_in_req = len([w for w in req_text_lower.split() if w in docstring_lower])
            similarity += (words_in_req / max(len(req_text_lower.split()), 1)) * 0.3

        return min(1.0, similarity)

    def _extract_requirement_terms(self, text: str) -> list[str]:
        """Extract key terms from requirement text.

        Args:
            text: Requirement text

        Returns:
            List of key terms
        """
        # Remove common words
        stop_words = {
            "system",
            "musi",
            "powinien",
            "może",
            "ma",
            "jest",
            "dla",
            "przez",
            "do",
            "z",
            "w",
            "na",
            "lub",
            "oraz",
            "nie",
            "się",
            "niech",
            "są",
        }

        # Extract capitalized words and technical terms
        words = re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ]{3,}\b", text)

        # Filter out stop words
        terms = [w for w in words if w.lower() not in stop_words]

        return list(set(terms))

    def _calculate_implementation_confidence(
        self,
        req: ExtractedRequirementSchema,
        mapped_entities: list[CodeEntity],
        all_entities: list[CodeEntity],
    ) -> float:
        """Calculate confidence of implementation.

        Args:
            req: Requirement being analyzed
            mapped_entities: Entities that match the requirement
            all_entities: All code entities

        Returns:
            Confidence score 0-1
        """
        if not mapped_entities:
            return 0.0

        # Start with base confidence from entity similarity
        # (would need to be passed from _find_matching_entities)
        base_confidence = 0.7  # Base for having matches

        # Boost if multiple entities match (comprehensive implementation)
        if len(mapped_entities) >= 2:
            base_confidence += 0.1

        # Boost if docstrings reference requirement terms
        for entity in mapped_entities:
            if entity.docstring:
                req_terms = self._extract_requirement_terms(req["text"])
                docstring_lower = entity.docstring.lower()
                matched_terms = sum(1 for t in req_terms if t.lower() in docstring_lower)
                if matched_terms >= 2:
                    base_confidence += 0.1

        return min(1.0, base_confidence)

    def _generate_issue_description(
        self,
        req: ExtractedRequirementSchema,
        mapped: list[CodeEntity],
        status: str,
    ) -> str | None:
        """Generate human-readable issue description.

        Args:
            req: Requirement analyzed
            mapped: Mapped entities
            status: Implementation status

        Returns:
            Description string or None
        """
        if status == "implemented":
            return None

        if status == "not_implemented":
            return f"Brak implementacji dla wymagania '{req['req_id']}'"

        if status == "partial":
            entity_names = [e.name for e in mapped]
            return f"Częściowa implementacja '{req['req_id']}' (znaleziono: {', '.join(entity_names)})"

        if status == "divergent":
            entity_names = [e.name for e in mapped]
            return f"Rozbieżność między wymaganiem '{req['req_id']}' a implementacją ({', '.join(entity_names)})"

        return None

    def _is_critical_requirement(self, result: GapAnalysisResult) -> bool:
        """Check if a requirement is critical.

        Args:
            result: Gap analysis result

        Returns:
            True if requirement is critical
        """
        # Would need priority from requirement
        # For now, assume requirements with "musi", "wymagane", "krytyczne" are critical
        critical_keywords = ["musi", "wymagane", "krytyczne", "obowiązkowe"]
        req_lower = result.requirement_text.lower()

        return any(kw in req_lower for kw in critical_keywords)


def analyze_gap(
    doc: DocumentStructure,
    requirements: list[ExtractedRequirementSchema],
    code_entities: list[CodeEntity],
) -> CoverageReport:
    """Convenience function to analyze documentation-code gap.

    Args:
        doc: Document structure
        requirements: Extracted requirements
        code_entities: Code entities to compare

    Returns:
        Coverage report
    """
    analyzer = GapAnalyzer()
    return analyzer.analyze(doc, requirements, code_entities)


# ── Epic 1 logic_structures → CodeEntity (Story 2.8 closure) ─────────────────


def code_entities_from_logic_structures(
    data: dict[str, Any] | None,
) -> list[CodeEntity]:
    """Flatten a ``logic_structures`` payload into ``CodeEntity`` objects.

    Mirrors ``TerminologyMapper._entities_from_logic_structures`` (Story 2.6):
    functions, classes, class methods and modules each become a ``CodeEntity``.
    Returns an empty list when no payload is available (non-fatal — the document
    still reaches READY; every requirement then resolves to ``not_implemented``).
    """
    if not data:
        return []

    entities: list[CodeEntity] = []

    def _entity(
        name: str,
        etype: str,
        raw: dict[str, Any],
        fallback_path: str = "",
    ) -> CodeEntity:
        return CodeEntity(
            entity_id=str(uuid.uuid4()),
            name=name,
            type=etype,
            file_path=raw.get("file_path") or fallback_path,
            line_number=int(raw.get("line_number") or raw.get("line") or 0),
            language=raw.get("language") or "python",
            docstring=raw.get("docstring"),
        )

    for fn in data.get("functions") or []:
        name = fn.get("name")
        if not name:
            continue
        ftype = "method" if fn.get("is_class_method") else "function"
        entities.append(_entity(name, ftype, fn))

    for cls in data.get("classes") or []:
        cls_path = cls.get("file_path") or ""
        cls_name = cls.get("name")
        if cls_name:
            entities.append(_entity(cls_name, "class", cls))
        for method in cls.get("methods") or []:
            mname = method.get("name")
            if mname:
                entities.append(_entity(mname, "method", method, fallback_path=cls_path))

    for mod in data.get("modules") or []:
        name = mod.get("name")
        if name:
            entities.append(_entity(name, "module", mod))

    return entities


# ── Persistence (result_data) — Story 2.8 closure ────────────────────────────


def gap_analysis_to_result_data(
    report: CoverageReport,
    items: list[GapAnalysisResult],
) -> dict[str, Any]:
    """Serialize a coverage report + per-requirement items into ``result_data``.

    Mirrors ``inconsistencies_to_result_data`` (Story 2.7): the payload is
    ``{"summary": {...}, "items": [...]}``, ready for
    ``AnalysisResult.result_data``.
    """
    return {
        "summary": {
            "total_requirements": report.total_requirements,
            "implemented": report.implemented,
            "not_implemented": report.not_implemented,
            "partial": report.partial,
            "divergent": report.divergent,
            "coverage_percentage": report.coverage_percentage,
            "critical_gaps": list(report.critical_gaps),
        },
        "items": [
            {
                "requirement_id": it.requirement_id,
                "requirement_text": it.requirement_text,
                "status": it.status,
                "mapped_entities": list(it.mapped_entities),
                "issue_description": it.issue_description,
                "confidence": it.confidence,
            }
            for it in items
        ],
    }


def from_result_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """Deserialize ``result_data`` with safe defaults.

    Normalizes ``summary`` (every ``CoverageReport`` key with a default) and
    passes ``items`` through. Returns an all-zero summary + empty items when
    nothing is persisted (e.g. detection not yet run).

    Args:
        data: ``AnalysisResult.result_data`` (or None)

    Returns:
        ``{"summary": {...}, "items": [...]}``.
    """
    zero_summary = {
        "total_requirements": 0,
        "implemented": 0,
        "not_implemented": 0,
        "partial": 0,
        "divergent": 0,
        "coverage_percentage": 0.0,
        "critical_gaps": [],
    }
    if not data:
        return {"summary": zero_summary, "items": []}

    summary = data.get("summary") or {}
    return {
        "summary": {
            "total_requirements": summary.get("total_requirements", 0),
            "implemented": summary.get("implemented", 0),
            "not_implemented": summary.get("not_implemented", 0),
            "partial": summary.get("partial", 0),
            "divergent": summary.get("divergent", 0),
            "coverage_percentage": summary.get("coverage_percentage", 0.0),
            "critical_gaps": list(summary.get("critical_gaps") or []),
        },
        "items": list(data.get("items") or []),
    }
