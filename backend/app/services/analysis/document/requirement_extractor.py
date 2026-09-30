"""Requirement extractor module for Epic 2.

This module extracts functional and non-functional requirements from
document structures using NLP patterns and linguistic rules.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.schemas.document import (
    DocumentStructure,
    SectionStructure,
)
from app.services.analysis.document.patterns import (
    calculate_requirement_confidence,
    detect_priority,
    extract_requirement_id,
    is_non_functional,
    is_requirement_section,
    matches_requirement_pattern,
    split_into_sentences,
)
from app.services.analysis.llm.prompts.requirement_extraction import build_extraction_prompt
from app.services.analysis.llm_gateway import LLMError, LLMMessage, get_llm_gateway

logger = logging.getLogger(__name__)

# Requirement workflow statuses persisted in AnalysisResult.result_data.
# An element starts as "extracted" and moves through the accept/reject/edit
# workflow (Story 2.4 closure).
REQUIREMENT_STATUSES = ("extracted", "accepted", "rejected", "edited")


@dataclass
class ExtractedRequirement:
    """Extracted requirement from document."""

    req_id: str
    text: str
    type: str  # 'functional' or 'non-functional'
    priority: str | None
    source_section_id: str
    source_section_title: str
    confidence: float
    extraction_method: str = "native"
    # Extraction origin (Story 2.5). Independent of ``status`` (workflow) and of
    # ``extraction_method`` (technical path). ``hybrid_merged`` joins with the
    # hybrid mode follow-up.
    source: str = "native"
    # Optional LLM justification for the requirement (Story 2.5).
    reasoning: str | None = None


class RequirementExtractor:
    """Extract requirements from document structures using NLP patterns.

    Identifies requirement sentences, extracts their properties, and
    organizes them by section.
    """

    def __init__(self) -> None:
        self.req_counter = 0
        self.section_counter: dict[str, int] = {}

    def extract(self, doc: DocumentStructure) -> list[ExtractedRequirement]:
        """Extract all requirements from document structure.

        Args:
            doc: Preprocessed document structure

        Returns:
            List of extracted requirements
        """
        requirements: list[ExtractedRequirement] = []

        # Process each section (including nested sections)
        for section in doc.sections:
            requirements.extend(self._extract_from_section(section, doc))

        return requirements

    def _extract_from_section(
        self,
        section: SectionStructure,
        doc: DocumentStructure,
    ) -> list[ExtractedRequirement]:
        """Extract requirements from a single section.

        Args:
            section: Section to process
            doc: Full document structure for context

        Returns:
            List of requirements from this section
        """
        requirements: list[ExtractedRequirement] = []

        # Check if this is a requirement section
        is_req_section = is_requirement_section(section.title)

        # Get content to analyze
        content = section.content
        if not content:
            # Also check children
            for child in section.children:
                requirements.extend(self._extract_from_section(child, doc))
            return requirements

        # Split into sentences
        sentences = split_into_sentences(content)

        # Analyze each sentence
        for sentence in sentences:
            req = self._analyze_sentence(sentence, section, is_req_section)
            if req:
                requirements.append(req)

        # Recursively process child sections
        for child in section.children:
            requirements.extend(self._extract_from_section(child, doc))

        return requirements

    def _analyze_sentence(
        self,
        sentence: str,
        section: SectionStructure,
        in_requirement_section: bool,
    ) -> ExtractedRequirement | None:
        """Analyze a sentence to determine if it's a requirement.

        Args:
            sentence: Sentence text to analyze
            section: Source section
            in_requirement_section: Whether from requirement section

        Returns:
            ExtractedRequirement if sentence is a requirement, None otherwise
        """
        # Clean sentence
        sentence = sentence.strip()
        if len(sentence) < 10:
            return None

        # Check for requirement ID
        req_id = extract_requirement_id(sentence)

        # Check if it matches requirement patterns
        matches_pattern = matches_requirement_pattern(sentence)

        # Check if starts with requirement phrase
        starts_with_starter = matches_requirement_pattern(sentence)

        # If no clear indicators, skip unless in requirement section
        if not (req_id or matches_pattern or starts_with_starter or in_requirement_section):
            return None

        # Determine type
        is_non_func = is_non_functional(sentence)
        req_type = "non-functional" if is_non_func else "functional"

        # Detect priority
        priority = detect_priority(sentence)

        # Calculate confidence
        confidence = calculate_requirement_confidence(
            sentence,
            has_id=bool(req_id),
            in_requirement_section=in_requirement_section,
        )

        # Skip low confidence requirements
        if confidence < 50:
            return None

        # Generate requirement ID if not present
        if not req_id:
            req_id = self._generate_requirement_id(section, req_type)

        return ExtractedRequirement(
            req_id=req_id,
            text=sentence,
            type=req_type,
            priority=priority,
            source_section_id=section.section_id,
            source_section_title=section.title,
            confidence=confidence,
            extraction_method="native",
        )

    def _generate_requirement_id(
        self,
        section: SectionStructure,
        req_type: str,
    ) -> str:
        """Generate a requirement ID for sentences without explicit ID.

        Format: FR-XXX (functional) or NFR-XXX (non-functional)
        """
        # Get or initialize section counter
        if section.section_id not in self.section_counter:
            self.section_counter[section.section_id] = 0

        self.section_counter[section.section_id] += 1
        counter = self.section_counter[section.section_id]

        prefix = "FR" if req_type == "functional" else "NFR"
        section_num = abs(hash(section.section_id)) % 1000

        return f"{prefix}-{section_num:03d}-{counter:02d}"

    def extract_from_section_text(
        self,
        text: str,
        section_id: str,
        section_title: str,
    ) -> list[ExtractedRequirement]:
        """Extract requirements from raw section text.

        Args:
            text: Section content
            section_id: Section identifier
            section_title: Section title

        Returns:
            List of extracted requirements
        """
        requirements: list[ExtractedRequirement] = []

        is_req_section = is_requirement_section(section_title)
        sentences = split_into_sentences(text)

        for sentence in sentences:
            req = self._analyze_sentence(
                sentence,
                SectionStructure(
                    section_id=section_id,
                    title=section_title,
                    level=1,
                    content="",
                ),
                in_requirement_section=is_req_section,
            )
            if req:
                requirements.append(req)

        return requirements


def extract_requirements(doc: DocumentStructure) -> list[ExtractedRequirement]:
    """Convenience function to extract requirements from document.

    Args:
        doc: Preprocessed document structure

    Returns:
        List of extracted requirements
    """
    extractor = RequirementExtractor()
    return extractor.extract(doc)


async def extract_requirements_async(
    doc: DocumentStructure,
    engine_mode: str,
    tenant_id: Any = None,
) -> list[ExtractedRequirement]:
    """Async convenience: route requirement extraction via the global ``engine_mode``.

    Mirrors ``classify_document_async``. ``native`` → native NLP; ``llm`` → LLM
    gateway (non-fatal native fallback); ``hybrid`` → warning + native (Story 2.5
    OOS — hybrid is a later phase).
    """
    return await LLMRequirementExtractor().extract_async(doc, engine_mode, tenant_id=tenant_id)


def requirements_to_result_data(
    reqs: list[ExtractedRequirement],
    status_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Serialize extracted requirements into an AnalysisResult.result_data payload.

    Each element carries the workflow ``status`` (default ``extracted``). The
    optional ``status_map`` (keyed by ``req_id``) preserves prior accept/reject
    decisions across re-extraction.

    Args:
        reqs: Extracted requirements to persist
        status_map: Optional mapping of ``req_id`` -> prior status

    Returns:
        ``{"requirements": [...]}`` dict ready for ``AnalysisResult.result_data``
    """
    status_map = status_map or {}
    return {
        "requirements": [
            {
                "req_id": r.req_id,
                "text": r.text,
                "type": r.type,
                "priority": r.priority,
                "source_section_id": r.source_section_id,
                "source_section_title": r.source_section_title,
                "confidence": r.confidence,
                "extraction_method": r.extraction_method,
                "source": r.source,
                "reasoning": r.reasoning,
                "status": status_map.get(r.req_id, "extracted"),
            }
            for r in reqs
        ]
    }


def from_result_data(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Read the raw requirement elements persisted in result_data.

    Args:
        data: ``AnalysisResult.result_data`` (or None)

    Returns:
        List of requirement dicts (empty when nothing persisted)
    """
    if not data:
        return []
    return list(data.get("requirements") or [])


def convert_to_schema(req: ExtractedRequirement) -> dict:
    """Convert ExtractedRequirement to schema for API response.

    Args:
        req: Extracted requirement

    Returns:
        Schema dictionary for API serialization
    """
    return {
        "req_id": req.req_id,
        "text": req.text,
        "type": req.type,
        "priority": req.priority,
        "source_section_id": req.source_section_id,
        "confidence": req.confidence,
        "extraction_method": req.extraction_method,
    }


class LLMRequirementExtractor(RequirementExtractor):
    """LLM-based requirement extractor.

    Uses LLM to extract requirements with semantic understanding.
    Better for implicit requirements and complex sentences.
    """

    # ── Async routing (native / llm / hybrid) — Story 2.5 closure ────────────

    async def extract_async(
        self,
        doc: DocumentStructure,
        engine_mode: str,
        tenant_id: Any = None,
    ) -> list[ExtractedRequirement]:
        """Route requirement extraction by the global ``engine_mode``.

        - ``native`` → native NLP extraction.
        - ``llm``    → LLM gateway (non-fatal native fallback on any error).
        - ``hybrid`` → not implemented in v1 (warning + native).

        ``extract_llm`` tags ``source`` itself (``llm`` on success, ``native`` on
        fallback), so a fallback is never mislabeled as ``llm``.
        """
        engine = (engine_mode or "").strip().lower()

        if engine == "llm":
            return await self.extract_llm(doc, tenant_id=tenant_id)

        if engine == "hybrid":
            logger.warning("Hybrid requirement extraction not implemented; falling back to native")

        # native + unknown + hybrid fallback
        reqs = self.extract(doc)
        for r in reqs:
            r.source = "native"
        return reqs

    async def extract_llm(
        self,
        doc: DocumentStructure,
        tenant_id: Any = None,
    ) -> list[ExtractedRequirement]:
        """Extract requirements via the LLM gateway (non-fatal native fallback).

        Single-chunk v1: the document is flattened to text (cap 8000 chars),
        sent with ``build_extraction_prompt``, and the JSON
        ``{requirements:[{text,type,priority,reasoning}]}`` response is mapped to
        ``ExtractedRequirement(extraction_method="llm")``. Each item is validated
        against the source text (``HallucinationValidator``); rejected items are
        logged and dropped — never persisted. Any failure (gateway/parse/missing
        key) falls back to native extraction tagged ``source="native"``.
        """
        try:
            # Lazy import avoids a circular dependency: the validator reuses
            # ``normalize_text`` defined later in this module.
            from app.services.analysis.document.hallucination_validator import (
                HallucinationValidator,
            )

            settings = get_settings()
            provider = self._select_llm_provider(settings)
            text = self._flatten_to_text(doc)
            prompt = build_extraction_prompt(text)
            messages = [
                LLMMessage(
                    "system",
                    "Zwracasz TYLKO JSON w formacie "
                    '{"requirements":[{"text","type","priority","reasoning"}]}. '
                    "Bez dodatkowego tekstu ani komentarzy.",
                ),
                LLMMessage("user", prompt),
            ]

            gateway = get_llm_gateway()
            resp = await gateway.complete(
                provider=provider,
                messages=messages,
                model=None,
                max_tokens=4096,
                temperature=0.1,
                tenant_id=tenant_id,
                module="requirements",
                task_type="requirement_extraction",
            )

            raw_items = self._parse_llm_requirements(resp.content)
            validator = HallucinationValidator()
            requirements: list[ExtractedRequirement] = []
            for item in raw_items:
                req = self._map_llm_item(item)
                if req is None:
                    continue
                validation = validator.validate(req, source_text=text, document_language="pl")
                if not validation.is_valid:
                    logger.warning(
                        "Hallucination rejected: %s — reasons: %s",
                        req.text[:80],
                        ", ".join(validation.reasons),
                    )
                    continue
                requirements.append(req)
            return requirements
        except Exception as exc:
            logger.warning("LLM requirement extraction failed — fallback to native: %s", exc)
            return self._native_fallback(doc)

    def _native_fallback(self, doc: DocumentStructure) -> list[ExtractedRequirement]:
        """Native extraction tagged ``source="native"`` (used on LLM fallback)."""
        reqs = self.extract(doc)
        for r in reqs:
            r.source = "native"
        return reqs

    def _map_llm_item(self, item: dict[str, Any]) -> ExtractedRequirement | None:
        """Map one parsed LLM requirement dict to an ``ExtractedRequirement``."""
        text = str(item.get("text") or "").strip()
        if len(text) < 10:
            return None

        req_type = str(item.get("type") or "functional").strip().lower()
        if req_type not in ("functional", "non-functional"):
            req_type = "functional"

        priority = item.get("priority")
        if priority is not None:
            priority = str(priority).strip().lower() or None

        reasoning = str(item.get("reasoning") or "").strip() or None

        return ExtractedRequirement(
            req_id=self._generate_llm_req_id(req_type),
            text=text,
            type=req_type,
            priority=priority,
            source_section_id="doc-root",
            source_section_title="Dokument",
            confidence=75.0,
            extraction_method="llm",
            source="llm",
            reasoning=reasoning,
        )

    def _generate_llm_req_id(self, req_type: str) -> str:
        """Generate an id for an LLM requirement (``FR-LLM-001`` / ``NFR-LLM-001``)."""
        self.req_counter += 1
        prefix = "FR" if req_type == "functional" else "NFR"
        return f"{prefix}-LLM-{self.req_counter:03d}"

    def _parse_llm_requirements(self, content: str | None) -> list[dict[str, Any]]:
        """Parse the LLM response into a list of requirement dicts.

        Tolerates ```json fences and surrounding prose, and accepts either a
        top-level ``{"requirements": [...]}`` object or a bare list.
        """
        text = (content or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start, end = text.find("["), text.rfind("]")
        if start == -1 or end <= start:
            raise ValueError("Odpowiedź LLM nie zawiera listy wymagań")
        text = text[start : end + 1]

        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("Odpowiedź LLM nie jest listą wymagań")
        return [r for r in data if isinstance(r, dict)]

    # ── LLM gateway helpers (mirror classifier.py — copied to avoid coupling) ──

    def _select_llm_provider(self, settings: Any) -> str:
        """Pick an LLM provider from configured API keys (Anthropic preferred)."""
        if settings.anthropic_api_key.get_secret_value():
            return "anthropic"
        if settings.openai_api_key.get_secret_value():
            return "openai"
        raise LLMError("Brak skonfigurowanego providera LLM (anthropic_api_key/openai_api_key)")

    def _flatten_to_text(self, doc: DocumentStructure, max_length: int = 8000) -> str:
        """Flatten sections into ``title\\ncontent`` text, capped for the prompt."""
        parts: list[str] = []
        for section in self._flatten_sections(doc.sections):
            if section.title:
                parts.append(section.title)
            if section.content:
                parts.append(section.content)
        text = "\n".join(parts)
        return text[:max_length]

    def _flatten_sections(self, sections: list[SectionStructure]) -> list[SectionStructure]:
        """Flatten a hierarchical section list depth-first (pre-order)."""
        flat: list[SectionStructure] = []
        for section in sections:
            flat.append(section)
            if section.children:
                flat.extend(self._flatten_sections(section.children))
        return flat

    def _chunk_document(self, doc: DocumentStructure, max_chars: int = 4000) -> list[str]:
        """Split document into chunks for LLM processing.

        Args:
            doc: Document structure
            max_chars: Maximum characters per chunk

        Returns:
            List of document chunks
        """
        chunks: list[str] = []
        current_chunk = ""

        def add_section(section: SectionStructure) -> None:
            nonlocal current_chunk, chunks

            section_text = f"{section.title}\n\n{section.content}"
            if len(current_chunk) + len(section_text) > max_chars and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = section_text
            else:
                current_chunk += f"\n\n{section_text}" if current_chunk else section_text

            # Process children
            for child in section.children:
                add_section(child)

        for section in doc.sections:
            add_section(section)

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _validate_requirement(
        self,
        req: ExtractedRequirement,
        doc: DocumentStructure,
    ) -> bool:
        """Validate LLM-extracted requirement against document.

        Args:
            req: Requirement to validate
            doc: Full document structure

        Returns:
            True if requirement appears valid
        """

        # Check if source section exists
        def find_section(sections: list[SectionStructure], section_id: str) -> bool:
            for section in sections:
                if section.section_id == section_id:
                    return True
                if section.children and find_section(section.children, section_id):
                    return True
            return False

        if not find_section(doc.sections, req.source_section_id):
            return False

        # Check if text is too short
        if len(req.text) < 10:
            return False

        # Check if text is too long (possible hallucination)
        return len(req.text) <= 1000


def merge_requirements(
    native: list[ExtractedRequirement],
    llm: list[ExtractedRequirement],
) -> list[ExtractedRequirement]:
    """Merge native and LLM extracted requirements.

    Deduplicates requirements and selects best version based on confidence.

    Args:
        native: Requirements from native extractor
        llm: Requirements from LLM extractor

    Returns:
        Merged list of unique requirements
    """
    merged: list[ExtractedRequirement] = []
    seen_texts: set[str] = set()

    # Index native requirements by normalized text
    native_by_text = {normalize_text(r.text): r for r in native}

    # Process LLM requirements first (they're more accurate)
    for llm_req in llm:
        norm_text = normalize_text(llm_req.text)

        if norm_text in seen_texts:
            continue

        # Check if native has similar requirement
        if norm_text in native_by_text:
            native_req = native_by_text[norm_text]
            # Keep the one with higher confidence
            if llm_req.confidence >= native_req.confidence:
                merged.append(llm_req)
            else:
                merged.append(native_req)
        else:
            merged.append(llm_req)

        seen_texts.add(norm_text)

    # Add native requirements not seen in LLM results
    for native_req in native:
        norm_text = normalize_text(native_req.text)

        if norm_text not in seen_texts:
            merged.append(native_req)
            seen_texts.add(norm_text)

    return merged


def normalize_text(text: str) -> str:
    """Normalize text for comparison.

    Args:
        text: Text to normalize

    Returns:
        Normalized text (lowercase, stripped, whitespace normalized)
    """
    return " ".join(text.lower().split())


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two requirement texts.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score 0-1
    """
    # Simple word-based similarity
    words1 = set(normalize_text(text1).split())
    words2 = set(normalize_text(text2).split())

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    return len(intersection) / len(union) if union else 0.0


def is_duplicate(req1: ExtractedRequirement, req2: ExtractedRequirement) -> bool:
    """Check if two requirements are duplicates.

    Args:
        req1: First requirement
        req2: Second requirement

    Returns:
        True if requirements are considered duplicates
    """
    # Same type and high similarity
    if req1.type != req2.type:
        return False

    similarity = calculate_similarity(req1.text, req2.text)
    return similarity > 0.8
