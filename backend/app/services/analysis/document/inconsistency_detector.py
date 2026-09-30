"""Inconsistency detector module for Epic 2.

This module detects inconsistencies within documentation including:
- Contradictory requirements
- Terminology inconsistencies (>2 names for same entity)
- Missing requirement references
- Duplicate requirements
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.document import (
        DocumentStructure,
        ExtractedRequirementSchema,
    )


@dataclass
class Inconsistency:
    """Detected inconsistency in documentation."""

    inconsistency_id: str
    type: str  # 'contradiction', 'terminology', 'missing_reference', 'duplicate'
    severity: str  # 'critical', 'high', 'medium', 'low'
    description: str
    affected_requirements: list[str]
    suggestion: str | None
    source_section_id: str | None


@dataclass
class ContradictionInconsistency(Inconsistency):
    """Contradictory requirements inconsistency."""

    req1_id: str
    req2_id: str
    conflict_type: str  # 'mutually_exclusive', 'contradictory_values', 'opposite_action'
    req1_text: str
    req2_text: str


@dataclass
class TerminologyInconsistency(Inconsistency):
    """Terminology inconsistency (multiple names for same entity)."""

    entity: str  # Normalized entity name
    variants: list[str]  # Different names used
    sections: list[str]  # Where each variant appears


@dataclass
class MissingReferenceInconsistency(Inconsistency):
    """Missing requirement reference inconsistency."""

    requirement_id: str
    requirement_text: str
    referenced_id: str  # The missing ID
    reference_context: str


@dataclass
class DuplicateInconsistency(Inconsistency):
    """Duplicate requirement inconsistency."""

    req1_id: str
    req2_id: str
    similarity_score: float
    merged_text: str | None


class InconsistencyDetector:
    """Detect inconsistencies within documentation.

    Analyzes requirements and document structure to find:
    - Contradictions (mutually exclusive requirements)
    - Terminology issues (inconsistent naming)
    - Missing references (IDs that don't exist)
    - Duplicates (similar requirements)
    """

    def __init__(self) -> None:
        self.inconsistencies: list[Inconsistency] = []

    def detect(
        self,
        doc: DocumentStructure,
        requirements: list[ExtractedRequirementSchema],
    ) -> list[Inconsistency]:
        """Detect all inconsistencies in documentation.

        Args:
            doc: Document structure
            requirements: Extracted requirements

        Returns:
            List of detected inconsistencies
        """
        self.inconsistencies = []

        # 1. Check for contradictions
        contradictions = self._detect_contradictions(requirements)
        self.inconsistencies.extend(contradictions)

        # 2. Check for terminology inconsistencies
        terminology = self._detect_terminology_inconsistencies(doc, requirements)
        self.inconsistencies.extend(terminology)

        # 3. Check for missing references
        missing_refs = self._detect_missing_references(requirements)
        self.inconsistencies.extend(missing_refs)

        # 4. Check for duplicates
        duplicates = self._detect_duplicates(requirements)
        self.inconsistencies.extend(duplicates)

        return self.inconsistencies

    def _detect_contradictions(self, requirements: list[ExtractedRequirementSchema]) -> list[Inconsistency]:
        """Detect contradictory requirements.

        Args:
            requirements: List of requirements to check

        Returns:
            List of contradiction inconsistencies
        """
        contradictions: list[Inconsistency] = []

        # Group requirements by type and keywords
        functional_reqs = [r for r in requirements if r["type"] == "functional"]

        # Pairs of mutually-exclusive patterns (positive vs negative obligation).
        # Matched case-insensitively against lowercased requirement text. Polish
        # phrasing: numeric "maksimum N" vs "minimum N" (kept unchanged), the
        # obligation pair "musi / ma obsługiwać" vs "nie może" (FIXED — the prior
        # ``musi\sfować`` / ``nie\s+może\s+fzać`` were typos that never matched),
        # "wymagane jest" vs "zabronione/niedozwolone", and "dla wszystkich" vs
        # "tylko dla administratora/admina".
        mutually_exclusive_patterns = [
            (r"(maksimum|max)\s+(\d+)", r"(minimum|min)\s+(\d+)"),  # Max/min limits
            (r"\b(musi|ma\s+obsługiwać)\b", r"\bnie\s+może\b"),  # Must / cannot
            (r"\bwymagane\s+jest\b", r"\b(zabronione|niedozwolone)\b"),  # Required / forbidden
            (r"\bdla\s+wszystkich\b", r"\btylko\s+dla\s+(administrator(?:a|zy)?|admina)\b"),  # All vs only specific
        ]

        for i, req1 in enumerate(functional_reqs):
            for req2 in functional_reqs[i + 1 :]:
                # Only check pairs about the same topic (shared keywords).
                if not self._have_similar_keywords(req1["text"], req2["text"]):
                    continue

                text1_lower = req1["text"].lower()
                text2_lower = req2["text"].lower()

                # Symmetric: the positive pattern in one requirement and the
                # negative in the other, in either order. A pair yields at most
                # one contradiction (first matching pattern wins).
                for pattern1, pattern2 in mutually_exclusive_patterns:
                    if (re.search(pattern1, text1_lower) and re.search(pattern2, text2_lower)) or (
                        re.search(pattern1, text2_lower) and re.search(pattern2, text1_lower)
                    ):
                        contradictions.append(
                            Inconsistency(
                                inconsistency_id=str(uuid.uuid4()),
                                type="contradiction",
                                severity="critical",
                                description=f"Sprzeczność: '{req1['req_id']}' vs '{req2['req_id']}'",
                                affected_requirements=[req1["req_id"], req2["req_id"]],
                                suggestion="Rozważ zmodyfikację jednego z wymagań",
                                source_section_id=req1.get("source_section_id"),
                            )
                        )
                        break

        return contradictions

    def _detect_terminology_inconsistencies(
        self, doc: DocumentStructure, requirements: list[ExtractedRequirementSchema]
    ) -> list[Inconsistency]:
        """Detect terminology inconsistencies.

        Args:
            doc: Document structure
            requirements: Extracted requirements

        Returns:
            List of terminology inconsistencies
        """
        inconsistencies: list[Inconsistency] = []

        # Extract entity mentions from requirements
        entity_variants: dict[str, list[str]] = defaultdict(list)

        for req in requirements:
            entities = self._extract_entities(req["text"])
            for entity in entities:
                entity_variants[entity].append(req["req_id"])

        # Find entities with >2 name variants
        for entity, req_ids in entity_variants.items():
            if len(req_ids) > 2:
                inconsistencies.append(
                    Inconsistency(
                        inconsistency_id=str(uuid.uuid4()),
                        type="terminology",
                        severity="medium",
                        description=f"Niespójna terminologia: '{entity}' ma {len(req_ids)} wariantów nazw",
                        affected_requirements=req_ids,
                        suggestion=f"Ustandaryzuj nazwę na jedną formę: '{entity}'",
                        source_section_id=None,
                    )
                )

        return inconsistencies

    def _detect_missing_references(self, requirements: list[ExtractedRequirementSchema]) -> list[Inconsistency]:
        """Detect missing requirement references.

        Args:
            requirements: List of requirements

        Returns:
            List of missing reference inconsistencies
        """
        inconsistencies: list[Inconsistency] = []

        # Get all valid requirement IDs
        valid_ids = {r["req_id"] for r in requirements}

        # Find references to other requirements
        reference_pattern = re.compile(r"(FR|NF|NFR|REQ|UC|ID)-\d+", re.IGNORECASE)

        for req in requirements:
            # Find all IDs mentioned in requirement text
            mentioned_ids = reference_pattern.findall(req["text"])

            for mentioned_id in mentioned_ids:
                # Check if referenced ID exists
                if mentioned_id not in valid_ids:
                    inconsistencies.append(
                        Inconsistency(
                            inconsistency_id=str(uuid.uuid4()),
                            type="missing_reference",
                            severity="high",
                            description=f"Brakująca referencja: '{req['req_id']}' odnosi się do nieistniejącego wymagania '{mentioned_id}'",
                            affected_requirements=[req["req_id"]],
                            suggestion=f"Usuń referencję do '{mentioned_id}' lub dodaj wymaganie o tym ID",
                            source_section_id=req.get("source_section_id"),
                        )
                    )

        return inconsistencies

    def _detect_duplicates(self, requirements: list[ExtractedRequirementSchema]) -> list[Inconsistency]:
        """Detect duplicate or very similar requirements.

        Args:
            requirements: List of requirements

        Returns:
            List of duplicate inconsistencies
        """
        inconsistencies: list[Inconsistency] = []

        for i, req1 in enumerate(requirements):
            for req2 in requirements[i + 1 :]:
                # Only check same type
                if req1["type"] != req2["type"]:
                    continue

                # Calculate similarity
                similarity = self._calculate_text_similarity(req1["text"], req2["text"])

                # High similarity = potential duplicate
                if similarity > 0.85:
                    inconsistencies.append(
                        Inconsistency(
                            inconsistency_id=str(uuid.uuid4()),
                            type="duplicate",
                            severity="medium",
                            description=f"Podobne wymagania: '{req1['req_id']}' i '{req2['req_id']}' ({similarity:.0%} podobienstwa)",
                            affected_requirements=[req1["req_id"], req2["req_id"]],
                            suggestion="Rozważ połączenie w jedno wymaganie lub usuń jednego jako duplikat",
                            source_section_id=req1.get("source_section_id"),
                        )
                    )

        return inconsistencies

    def _have_similar_keywords(self, text1: str, text2: str) -> bool:
        """Check if two texts mention similar keywords.

        Args:
            text1: First text
            text2: Second text

        Returns:
            True if similar keywords found
        """
        # Extract important words (nouns, technical terms)
        words1 = set(re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ]{3,}\b", text1))
        words2 = set(re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ]{3,}\b", text2))

        # Check for overlap
        intersection = words1.intersection(words2)
        return len(intersection) >= 2

    def _extract_entities(self, text: str) -> list[str]:
        """Extract potential entity names from text.

        Args:
            text: Text to extract from

        Returns:
            List of entity names
        """
        # Capitalized words and phrases (potential entities)
        entities = re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)*\b", text)
        return list(set(entities))

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score 0-1
        """
        # Simple word-based similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0


def detect_inconsistencies(
    doc: DocumentStructure,
    requirements: list[ExtractedRequirementSchema],
) -> list[Inconsistency]:
    """Convenience function to detect inconsistencies.

    Args:
        doc: Document structure
        requirements: Extracted requirements

    Returns:
        List of detected inconsistencies
    """
    detector = InconsistencyDetector()
    return detector.detect(doc, requirements)


# ── Persistence helpers (mirror requirement_extractor / glossary_extractor) ──

# Allowed ``status`` values persisted in result_data (AC4 workflow).
INCONSISTENCY_STATUSES = ("open", "accepted", "false_positive", "fixed")
# Allowed ``type`` / ``severity`` values persisted in result_data.
INCONSISTENCY_TYPES = ("contradiction", "terminology", "missing_reference", "duplicate")
INCONSISTENCY_SEVERITIES = ("critical", "high", "medium", "low")


def inconsistencies_to_result_data(items: list[Inconsistency]) -> dict[str, Any]:
    """Serialize detected inconsistencies into an ``AnalysisResult.result_data`` payload.

    Each element carries the workflow ``status`` (default ``open``); the status
    lives only in the persisted payload (it is not part of the ``Inconsistency``
    dataclass), mirroring how the glossary/requirements flows embed workflow
    state into ``result_data``.

    Returns:
        ``{"items": [...]}`` dict ready for ``AnalysisResult.result_data``.
    """
    return {
        "items": [
            {
                "inconsistency_id": it.inconsistency_id,
                "type": it.type,
                "severity": it.severity,
                "description": it.description,
                "affected_requirements": list(it.affected_requirements),
                "suggestion": it.suggestion,
                "source_section_id": it.source_section_id,
                "status": "open",
            }
            for it in items
        ]
    }


def from_result_data(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Read the raw inconsistency elements persisted in result_data.

    Normalizes every element: missing keys get safe defaults and ``status``
    falls back to ``open`` when absent (e.g. payloads written before the
    workflow existed).

    Args:
        data: ``AnalysisResult.result_data`` (or None)

    Returns:
        List of inconsistency dicts (empty when nothing persisted)
    """
    if not data:
        return []
    items: list[dict[str, Any]] = []
    for it in data.get("items") or []:
        items.append(
            {
                "inconsistency_id": it.get("inconsistency_id", ""),
                "type": it.get("type", ""),
                "severity": it.get("severity", "medium"),
                "description": it.get("description", ""),
                "affected_requirements": list(it.get("affected_requirements") or []),
                "suggestion": it.get("suggestion"),
                "source_section_id": it.get("source_section_id"),
                "status": it.get("status", "open"),
            }
        )
    return items
