"""Glossary and terminology extractor module for Epic 2.

Extracts glossary terms and domain-specific terminology from document sections
(glossary section → definition patterns → frequency), classifies each term, and
maps terms onto project code entities (Story 2.6 closure).

Persistence uses ``AnalysisResult.result_data`` JSONB — no dedicated table
(mirror of the requirements flow, Story 2.4). The term-to-code mapping reuses
the existing ``logic_structures`` analysis from Epic 1 and the
``suggest_code_mappings`` helper.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.analysis_result import AnalysisResult, AnalysisStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.document import DocumentStructure, SectionStructure

logger = logging.getLogger(__name__)

# Patterns for identifying glossary sections (matched against section titles).
GLOSSARY_SECTION_PATTERNS = [
    r"glosariusz",
    r"glossary",
    r"słownik\s+pojęć",
    r"definicje",
    r"definitions",
    r"terminologia",
    r"terminology",
    r"lista\s+pojęć",
    r"spis\s+terminów",
]

# Patterns for extracting term-definition pairs from the glossary section.
# The character class includes the EN DASH (U+2013), a common Polish definition
# separator; RUF001 is silenced because the character is intentional.
TERM_DEFINITION_PATTERNS = [
    # Term in bold/quotes followed by definition
    r"\*\*([^*]+)\*\*\s*[:–-]\s*([^\n]+)",  # noqa: RUF001
    r'"([^"]+)"\s*[:–-]\s*([^\n]+)',  # noqa: RUF001
    r"'([^']+)'\s*[:–-]\s*([^\n]+)",  # noqa: RUF001
    # Term: definition format
    r"([A-ZĄĆĘŁŃÓŚŹŻ][a-zA-ZąćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ]+)\s*[:–-]\s*([^\n]+)",  # noqa: RUF001
]

# Acronym: 2-8 uppercase letters/digits, e.g. API, JWT, BLIK, HTTP.
ACRONYM_RE = re.compile(r"^[A-Z0-9]{2,8}$")
# Technical-domain keyword hints (lowercase; Polish/English tolerant).
TECHNICAL_KEYWORDS = (
    "api",
    "endpoint",
    "moduł",
    "modul",
    "serwis",
    "service",
    "baza",
    "database",
    "klasa",
    "class",
    "funkcja",
    "function",
    "metoda",
    "method",
    "token",
    "kolejka",
    "queue",
    "komponent",
    "component",
    "serwer",
    "server",
    "mikrousługa",
    "mikrousugi",
)

# Allowed ``term_type`` values persisted in result_data.
TERM_TYPES = ("domain", "technical", "business", "acronym")


def _classify_term_type(term: str, definition: str | None) -> str:
    """Classify a glossary term (Task 1.2).

    Priority: acronym → domain (has a definition from the glossary section) →
    technical (technical keyword present) → business.
    """
    if ACRONYM_RE.match(term):
        return "acronym"
    if definition:
        return "domain"
    haystack = f"{term} {definition or ''}".lower()
    if any(kw in haystack for kw in TECHNICAL_KEYWORDS):
        return "technical"
    return "business"


@dataclass
class GlossaryTerm:
    """Extracted glossary term with definition, classification and code mappings.

    Persisted into ``AnalysisResult.result_data["terms"]`` via
    ``glossary_terms_to_result_data``.
    """

    term: str
    definition: str | None = None
    occurrences_count: int = 0
    term_type: str = "business"
    # ``[{section_id, title}]`` — sections where the term appears.
    source_sections: list[dict[str, Any]] = field(default_factory=list)
    is_verified: bool = False
    # ``[{name, type, similarity, is_confirmed}]`` — code-entity mappings (AC2).
    code_mappings: list[dict[str, Any]] = field(default_factory=list)


class GlossaryExtractor:
    """Extract glossary terms from document structures.

    Three strategies, in priority order:
    1. Glossary section → term-definition pairs (enter regardless of frequency).
    2. Definition patterns elsewhere.
    3. Frequent candidate terms without a definition (``min_frequency`` threshold).
    Each term is classified (``term_type``) and tagged with its source sections.
    """

    def __init__(self, min_frequency: int = 3) -> None:
        self.min_frequency: int = min_frequency
        self.term_counter: dict[str, int] = {}
        # term_lower -> list of {section_id, title} (deduped by section_id)
        self.term_sections: dict[str, list[dict[str, Any]]] = {}
        # term_lower -> original-cased display term
        self.term_display: dict[str, str] = {}

    def extract(self, doc: DocumentStructure) -> list[GlossaryTerm]:
        """Extract glossary terms from document structure.

        Args:
            doc: Preprocessed document structure

        Returns:
            List of glossary terms (definitions first, then frequency-only)
        """
        self._count_terms(doc)
        definitions = self._extract_definitions(doc)

        by_key: dict[str, GlossaryTerm] = {}

        # Strategy 1+2: terms with a definition enter regardless of frequency.
        for term, definition in definitions.items():
            key = term.lower()
            by_key[key] = self._build_term(term, definition)

        # Strategy 3: frequent candidate terms without a definition.
        for key, count in self.term_counter.items():
            if count < self.min_frequency or key in by_key:
                continue
            display = self.term_display.get(key, key)
            by_key[key] = self._build_term(display, None)

        return list(by_key.values())

    def _build_term(self, term: str, definition: str | None) -> GlossaryTerm:
        key = term.lower()
        return GlossaryTerm(
            term=term,
            definition=definition,
            occurrences_count=self.term_counter.get(key, 0),
            term_type=_classify_term_type(term, definition),
            source_sections=[
                {"section_id": s["section_id"], "title": s["title"]} for s in self.term_sections.get(key, [])
            ],
        )

    def _count_terms(self, doc: DocumentStructure) -> None:
        """Count occurrences of candidate terms and record source sections."""
        self.term_counter = {}
        self.term_sections = {}
        self.term_display = {}

        for section in self._flatten_sections(doc.sections):
            text = f"{section.title} {section.content}"
            for term in self._extract_candidate_terms(text):
                key = term.lower()
                self.term_counter[key] = self.term_counter.get(key, 0) + 1
                self.term_display[key] = term
                sections = self.term_sections.setdefault(key, [])
                if not any(s["section_id"] == section.section_id for s in sections):
                    sections.append({"section_id": section.section_id, "title": section.title})

    def _extract_definitions(self, doc: DocumentStructure) -> dict[str, str]:
        """Extract term-definition pairs from the glossary section.

        Args:
            doc: Document structure

        Returns:
            Dictionary mapping terms to definitions
        """
        definitions: dict[str, str] = {}

        glossary_section = self._find_glossary_section(doc.sections)
        if not glossary_section:
            return definitions

        content = glossary_section.content

        for pattern in TERM_DEFINITION_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                term = match.group(1).strip()
                definition = match.group(2).strip()
                if term and definition:
                    definitions[term] = definition

        return definitions

    def _find_glossary_section(self, sections: list[SectionStructure]) -> SectionStructure | None:
        """Find section containing glossary/definitions (recursively)."""
        for section in sections:
            title_lower = section.title.lower()
            for pattern in GLOSSARY_SECTION_PATTERNS:
                if re.search(pattern, title_lower, re.IGNORECASE):
                    return section

            if section.children:
                found = self._find_glossary_section(section.children)
                if found:
                    return found

        return None

    def _extract_candidate_terms(self, text: str) -> list[str]:
        """Extract candidate glossary terms from text (deduped, len > 2)."""
        terms: list[str] = []

        # Multi-word technical terms (2-4 words, capitalized)
        pattern = r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ]+){1,3}\b"
        terms.extend(re.findall(pattern, text))

        # Single capitalized words (likely technical terms / acronyms)
        pattern = r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ]+\b"
        terms.extend(re.findall(pattern, text))

        seen: set[str] = set()
        unique_terms: list[str] = []
        for term in terms:
            key = term.lower()
            if key not in seen and len(term) > 2:
                seen.add(key)
                unique_terms.append(term)

        return unique_terms

    def _flatten_sections(self, sections: list[SectionStructure]) -> list[SectionStructure]:
        """Flatten hierarchical section list depth-first (pre-order)."""
        result: list[SectionStructure] = []
        for section in sections:
            result.append(section)
            if section.children:
                result.extend(self._flatten_sections(section.children))
        return result


@dataclass
class CodeMapping:
    """Suggested mapping between glossary term and code entities."""

    term: str
    code_entities: list[str]
    confidence: float
    mapping_type: str  # "exact_match", "fuzzy_match", "semantic"


def suggest_code_mappings(
    term: str,
    available_entities: list[str],
) -> list[CodeMapping]:
    """Suggest code entity mappings for a glossary term.

    Args:
        term: Glossary term
        available_entities: List of code entity names

    Returns:
        Top-5 potential mappings with confidence scores (exact then fuzzy)
    """
    mappings: list[CodeMapping] = []

    term_lower = term.lower()
    term_variations = [
        term_lower,
        term_lower.replace(" ", "_"),
        term_lower.replace(" ", ""),
        term_lower.replace("-", "_"),
        term_lower.replace("-", ""),
    ]

    for entity in available_entities:
        entity_lower = entity.lower()

        # Exact match
        if entity_lower in term_variations or term_lower in entity_lower:
            mappings.append(
                CodeMapping(
                    term=term,
                    code_entities=[entity],
                    confidence=1.0,
                    mapping_type="exact_match",
                )
            )

        # Fuzzy match (contained in)
        elif term_lower in entity_lower or entity_lower in term_lower:
            confidence = len(term_lower) / max(len(entity_lower), 1)
            if confidence >= 0.6:
                mappings.append(
                    CodeMapping(
                        term=term,
                        code_entities=[entity],
                        confidence=confidence,
                        mapping_type="fuzzy_match",
                    )
                )

    mappings.sort(key=lambda m: m.confidence, reverse=True)

    return mappings[:5]  # Return top 5 suggestions


def extract_glossary(doc: DocumentStructure) -> list[GlossaryTerm]:
    """Convenience function to extract glossary from a document (native, sync).

    Args:
        doc: Preprocessed document structure

    Returns:
        List of glossary terms
    """
    extractor = GlossaryExtractor()
    return extractor.extract(doc)


# ── Persistence helpers (mirror requirement_extractor) ───────────────────────


def glossary_terms_to_result_data(terms: list[GlossaryTerm]) -> dict[str, Any]:
    """Serialize glossary terms into an ``AnalysisResult.result_data`` payload.

    Returns:
        ``{"terms": [...]}`` dict ready for ``AnalysisResult.result_data``.
    """
    return {
        "terms": [
            {
                "term": t.term,
                "definition": t.definition,
                "occurrences_count": t.occurrences_count,
                "term_type": t.term_type,
                "source_sections": [dict(s) for s in t.source_sections],
                "is_verified": t.is_verified,
                "code_mappings": [dict(m) for m in t.code_mappings],
            }
            for t in terms
        ]
    }


def from_result_data(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Read the raw glossary term elements persisted in result_data.

    Args:
        data: ``AnalysisResult.result_data`` (or None)

    Returns:
        List of term dicts (empty when nothing persisted)
    """
    if not data:
        return []
    return list(data.get("terms") or [])


# ── Terminology mapping onto project code (AC2, v1-light) ────────────────────


class TerminologyMapper:
    """Map glossary terms onto project code entities (Story 2.6, AC2).

    Reads code entities from the persisted ``logic_structures`` AnalysisResult
    (Epic 1) and reuses ``suggest_code_mappings`` (exact/fuzzy, top-5). The
    resulting mappings are embedded into each term's ``code_mappings`` — no
    dedicated ``terminology_mappings`` table.
    """

    async def _load_code_entities(self, project_id: Any, db: AsyncSession) -> list[dict[str, Any]]:
        """Read ``{name, type, file_path}`` entities from ``logic_structures``.

        Non-fatal: returns an empty list when no analysis exists.
        """
        result = await db.execute(
            select(AnalysisResult).where(
                AnalysisResult.project_id == project_id,
                AnalysisResult.module == "logic_structures",
                AnalysisResult.status == AnalysisStatus.COMPLETED,
            )
        )
        ar = result.scalar_one_or_none()
        if not ar or not ar.result_data:
            return []
        return self._entities_from_logic_structures(ar.result_data)

    @staticmethod
    def _entities_from_logic_structures(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Flatten a ``CodeStructureCatalog.to_dict()`` payload into entities.

        Functions, classes, class methods and modules each become an entity
        ``{name, type, file_path}``.
        """
        entities: list[dict[str, Any]] = []

        for fn in data.get("functions") or []:
            name = fn.get("name")
            if not name:
                continue
            ftype = "method" if fn.get("is_class_method") else "function"
            entities.append({"name": name, "type": ftype, "file_path": fn.get("file_path")})

        for cls in data.get("classes") or []:
            cls_path = cls.get("file_path")
            cls_name = cls.get("name")
            if cls_name:
                entities.append({"name": cls_name, "type": "class", "file_path": cls_path})
            for method in cls.get("methods") or []:
                mname = method.get("name")
                if mname:
                    entities.append({"name": mname, "type": "method", "file_path": cls_path})

        for mod in data.get("modules") or []:
            name = mod.get("name")
            if name:
                entities.append({"name": name, "type": "module", "file_path": mod.get("file_path")})

        return entities

    async def map_to_code(
        self,
        terms: list[Any],
        project_id: Any,
        db: AsyncSession,
    ) -> dict[str, list[dict[str, Any]]]:
        """Map each term onto top code entities.

        Args:
            terms: Glossary terms (dicts with ``term`` or ``GlossaryTerm``)
            project_id: Project whose code to map against
            db: Async session (RLS-scoped by the caller)

        Returns:
            ``{term_text: [{name, type, similarity, is_confirmed}, ...]}``.
            Empty lists when no code analysis is available (non-fatal).
        """
        entities = await self._load_code_entities(project_id, db)
        names = [e["name"] for e in entities]
        by_name = {e["name"]: e for e in entities}

        result: dict[str, list[dict[str, Any]]] = {}
        for term_obj in terms:
            term_text = term_obj["term"] if isinstance(term_obj, dict) else getattr(term_obj, "term", "")
            if not entities:
                result[term_text] = []
                continue

            suggestions = suggest_code_mappings(term_text, names)
            result[term_text] = [
                {
                    "name": suggestion.code_entities[0] if suggestion.code_entities else "",
                    "type": by_name.get(
                        suggestion.code_entities[0] if suggestion.code_entities else "",
                        {},
                    ).get("type", "function"),
                    "similarity": round(float(suggestion.confidence), 3),
                    "is_confirmed": False,
                }
                for suggestion in suggestions
            ]
        return result
