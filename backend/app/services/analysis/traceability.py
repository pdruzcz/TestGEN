"""Traceability matrix module for Epic 2.

This module generates traceability matrices linking requirements to
code entities and test cases, providing visibility into coverage and relationships.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.document import (
        DocumentStructure,
        ExtractedRequirementSchema,
    )


@dataclass
class TraceabilityEntry:
    """Single entry in traceability matrix."""

    requirement_id: str
    requirement_text: str
    code_entities: list[str]
    test_cases: list[str]
    coverage_status: str  # 'full', 'partial', 'none'
    source_section_id: str


@dataclass
class TraceabilityMatrix:
    """Complete traceability matrix for a document."""

    document_name: str
    entries: list[TraceabilityEntry]
    total_requirements: int
    full_coverage: int
    partial_coverage: int
    no_coverage: int
    coverage_percentage: float


class TraceabilityMatrixGenerator:
    """Generate traceability matrices from requirements and code/test data.

    Links requirements to code entities and test cases for complete
    traceability and coverage tracking.
    """

    def __init__(self) -> None:
        pass

    def generate(
        self,
        doc: DocumentStructure,
        requirements: list[ExtractedRequirementSchema],
        code_entities: list[Any] | None = None,
        test_cases: list[Any] | None = None,
    ) -> TraceabilityMatrix:
        """Generate traceability matrix.

        Args:
            doc: Document structure
            requirements: Extracted requirements
            code_entities: Optional list of code entities
            test_cases: Optional list of test cases

        Returns:
            Traceability matrix
        """
        entries: list[TraceabilityEntry] = []

        # Normalize inputs
        code_list = code_entities if code_entities else []
        test_list = test_cases if test_cases else []

        for req in requirements:
            # Find matching code entities
            mapped_code = self._find_code_entities(req, code_list)

            # Find matching test cases
            mapped_tests = self._find_test_cases(req, test_list)

            # Determine coverage status
            coverage = self._determine_coverage(mapped_code, mapped_tests)

            entry = TraceabilityEntry(
                requirement_id=req["req_id"],
                requirement_text=req["text"],
                code_entities=mapped_code,
                test_cases=mapped_tests,
                coverage_status=coverage,
                source_section_id=req.get("source_section_id", ""),
            )
            entries.append(entry)

        # Calculate statistics
        total = len(entries)
        full = len([e for e in entries if e.coverage_status == "full"])
        partial = len([e for e in entries if e.coverage_status == "partial"])
        none_count = len([e for e in entries if e.coverage_status == "none"])
        coverage_pct = (full / total * 100) if total > 0 else 0.0

        return TraceabilityMatrix(
            document_name=doc.metadata.get("filename", "Unknown"),
            entries=entries,
            total_requirements=total,
            full_coverage=full,
            partial_coverage=partial,
            no_coverage=none_count,
            coverage_percentage=coverage_pct,
        )

    def _find_code_entities(
        self,
        req: ExtractedRequirementSchema,
        code_entities: list[Any],
    ) -> list[str]:
        """Find code entities matching a requirement.

        Args:
            req: Requirement to match
            code_entities: List of code entities

        Returns:
            List of matched entity names
        """
        # Simplified implementation - would use fuzzy matching in production
        req_text_lower = req["text"].lower()
        matched = []

        for entity in code_entities:
            entity_name = entity.name if hasattr(entity, "name") else str(entity)
            if entity_name.lower() in req_text_lower:
                matched.append(entity_name)

        return matched

    def _find_test_cases(
        self,
        req: ExtractedRequirementSchema,
        test_cases: list[Any],
    ) -> list[str]:
        """Find test cases covering a requirement.

        Args:
            req: Requirement to match
            test_cases: List of test cases

        Returns:
            List of matched test IDs/names
        """
        # Simplified implementation
        req_id = req["req_id"]
        matched = []

        for test in test_cases:
            test_id = test.id if hasattr(test, "id") else str(test)
            # Check if test references requirement ID
            if hasattr(test, "requirement_ids") and req_id in test.requirement_ids:
                matched.append(test_id)

        return matched

    def _determine_coverage(
        self,
        code_entities: list[str],
        test_cases: list[str],
    ) -> str:
        """Determine coverage status based on code and test matches.

        Args:
            code_entities: Matched code entities
            test_cases: Matched test cases

        Returns:
            Coverage status: 'full', 'partial', or 'none'
        """
        has_code = len(code_entities) > 0
        has_tests = len(test_cases) > 0

        if has_code and has_tests:
            return "full"
        elif has_code or has_tests:
            return "partial"
        else:
            return "none"


def generate_traceability_matrix(
    doc: DocumentStructure,
    requirements: list[ExtractedRequirementSchema],
    code_entities: list[Any] | None = None,
    test_cases: list[Any] | None = None,
) -> TraceabilityMatrix:
    """Convenience function to generate traceability matrix.

    Args:
        doc: Document structure
        requirements: Extracted requirements
        code_entities: Optional code entities
        test_cases: Optional test cases

    Returns:
        Traceability matrix
    """
    generator = TraceabilityMatrixGenerator()
    return generator.generate(doc, requirements, code_entities, test_cases)


# ── Persistence (result_data) — Story 2.9 closure ──────────────────────────────


def traceability_to_result_data(matrix: TraceabilityMatrix) -> dict[str, Any]:
    """Serialize a ``TraceabilityMatrix`` into a flat ``result_data`` payload.

    Mirrors the gap-analysis serializer (Story 2.8) but the traceability shape is
    already **flat** (no ``summary``/``items`` nesting) — it is stored 1:1 in the
    frontend's ``TraceabilityMatrix`` interface shape, so the API returns
    ``result_data`` directly without a deserializer. Each entry matches
    ``TraceabilityEntry`` (``requirement_id`` / ``requirement_text`` /
    ``code_entities`` / ``test_cases`` / ``coverage_status`` /
    ``source_section_id``); ``coverage_status`` is a string ``full``/``partial``/
    ``none`` (NOT the Epic 3 enum).
    """
    return {
        "document_name": matrix.document_name,
        "total_requirements": matrix.total_requirements,
        "full_coverage": matrix.full_coverage,
        "partial_coverage": matrix.partial_coverage,
        "no_coverage": matrix.no_coverage,
        "coverage_percentage": matrix.coverage_percentage,
        "entries": [
            {
                "requirement_id": e.requirement_id,
                "requirement_text": e.requirement_text,
                "code_entities": list(e.code_entities),
                "test_cases": list(e.test_cases),
                "coverage_status": e.coverage_status,
                "source_section_id": e.source_section_id,
            }
            for e in matrix.entries
        ],
    }
