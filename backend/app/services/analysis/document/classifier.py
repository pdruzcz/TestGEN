"""Document classifier module for Epic 2.

This module classifies documents into types (requirements spec, user manual,
technical guide, API docs, project notes, other) using native NLP rules
and optionally LLM-based classification for higher accuracy.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.schemas.document import (
    ClassificationResult,
    ClassificationSource,
    DocumentStructure,
    DocumentType,
    SectionStructure,
)
from app.services.analysis.llm.prompts.classification import build_classification_prompt
from app.services.analysis.llm_gateway import LLMError, LLMMessage, get_llm_gateway

logger = logging.getLogger(__name__)


# Native classification rules per document type
@dataclass
class ClassificationRule:
    """Rule for native document classification."""

    doc_type: DocumentType
    keywords: list[str]
    title_patterns: list[str]
    section_patterns: list[str]
    structure_indicators: list[str]  # Expected document structure
    weight: float = 1.0  # Rule weight for scoring


# Classification rules for each document type
CLASSIFICATION_RULES: dict[DocumentType, ClassificationRule] = {
    DocumentType.SPECIFIKACJA_WYMAGAN: ClassificationRule(
        doc_type=DocumentType.SPECIFIKACJA_WYMAGAN,
        keywords=[
            "wymaganie",
            "wymagania",
            "wymaganiem",
            "wymaganiu",
            "funkcjonal",
            "niefunkcjonal",
            "akceptacj",
            "kryterium",
            "SRS",
            "BRD",
            "FRD",
            "use case",
            "przypadek użycia",
            "stakeholder",
            "interesariusz",
            "priorytet",
            "requirement",
        ],
        title_patterns=[
            r".*[Ss]pecyfikacja.*wymagań.*",
            r".*[Ww]ymagania.*",
            r".*[Rr]equirements.*",
            r".*[Bb]usiness.*[Rr]equirements.*",
            r".*[Ff]unctional.*[Rr]equirements.*",
            r".*[Ss]oftware.*[Rr]equirements.*",
            r".*SRS.*",
            r".*PRD.*",
            r".*FRD.*",
        ],
        section_patterns=[
            r"1\.\s*[Ww]prowadzenie",
            r"2\.\s*[Ww]ymagania",
            r"2\.\s*[Oo]gólny.*opis",
            r"3\.\s*[Ss]ystem.*interfejs",
            r".*[Aa]ktorzy",
            r".*[Ii]nteresariusze",
            r".*[Zz]akres",
            r".*[Pp]rzypadek.*użycia",
            r".*[Uu]se.*cases?",
        ],
        structure_indicators=[
            "1.",
            "1.1",
            "2.",
            "2.1",  # Hierarchical numbering
            "Table of Contents",
            "Spis treści",
        ],
        weight=1.5,  # Higher weight as this is the primary type
    ),
    DocumentType.PODRECZNIK_UZYTKOWNIKA: ClassificationRule(
        doc_type=DocumentType.PODRECZNIK_UZYTKOWNIKA,
        keywords=[
            "użytkown",
            "instrukcj",
            "obsług",
            "przeznaczon",
            "interfejs",
            "przycisk",
            "menu",
            "ekran",
            "formularz",
            "ręczny",
            "podręcznik",
            "manual",
            "user guide",
            "jak użyć",
            "jak korzystać",
            "krok po kroku",
            "tutorial",
        ],
        title_patterns=[
            r".*[Pp]odręcznik.*użytkownika.*",
            r".*[Ii]nstrukcja.*obsługi.*",
            r".*[Uu]ser.*[Mm]anual.*",
            r".*[Gg]uide.*",
            r".*[Tt]utorial.*",
            r".*[Jj]ak.*używać.*",
            r".*[Jj]ak.*korzystać.*",
        ],
        section_patterns=[
            r"[Pp]ierwsze.*kroki",
            r"[Ii]nstalacj",
            r"[Kk]onfiguracj",
            r"[Pp]odstawy.*",
            r"[Zz]aczęcie",
            r"[Ww]prowadzenie.*program",
            r"[Ii]nterfejs.*użytkownika",
            r"[Zz]asady.*obsługi",
        ],
        structure_indicators=[
            "Step 1",
            "Step 2",
            "Krok 1",
            "Krok 2",
            "Figure 1",
            "Rysunek 1",
        ],
        weight=1.0,
    ),
    DocumentType.INSTRUKCJA_TECHNICZNA: ClassificationRule(
        doc_type=DocumentType.INSTRUKCJA_TECHNICZNA,
        keywords=[
            "instalacj",
            "konfiguracj",
            "wdrożeni",
            "wdrożen",
            "serwis",
            "konserwacj",
            "technical",
            "deployment",
            "setup",
            "architecture",
            "integracj",
            "baza danych",
            "infrastruktur",
            "systemowy",
            "administ",
        ],
        title_patterns=[
            r".*[Ii]nstrukcja.*techniczna.*",
            r".*[Ii]nstallation.*[Gg]uide.*",
            r".*[Aa]dministrator.*[Gg]uide.*",
            r".*[Tt]echnical.*[Dd]ocumentation.*",
            r".*[Dd]eployment.*[Gg]uide.*",
            r".*[Ss]ystem.*[Aa]rchitecture.*",
            r".*[Ii]ntegracj",
        ],
        section_patterns=[
            r"[Ww]ymagania.*systemowe",
            r"[Ii]nstalacj",
            r"[Kk]onfiguracj",
            r"[Ww]drożeni",
            r"[Aa]rchitektura",
            r"[Bb]aza.*danych",
            r"[Ss]erwer",
            r"[Ii]nfrastruktura",
        ],
        structure_indicators=[
            "Prerequisities",
            "Wymagania wstępne",
            "System requirements",
            "Wymagania systemowe",
        ],
        weight=1.2,
    ),
    DocumentType.OPIS_API: ClassificationRule(
        doc_type=DocumentType.OPIS_API,
        keywords=[
            "endpoint",
            "API",
            "REST",
            "POST",
            "GET",
            "PUT",
            "DELETE",
            "JSON",
            "request",
            "response",
            "parametr",
            "autoryzacj",
            "authentication",
            "swagger",
            "openapi",
            "metoda",
            "payload",
            "header",
            "status.*code",
        ],
        title_patterns=[
            r".*[Aa][Pp][Ii].*",
            r".*[Rr]EST.*[Aa][Pp][Ii].*",
            r".*[Oo]pen[Aa][Pp][Ii].*",
            r".*[Ss]wagger.*",
            r".*[Ee]ndpoint.*",
            r".*[Ii]nterface.*[Dd]ocumentation.*",
        ],
        section_patterns=[
            r"[Aa]uthenticat",
            r"[Ee]ndpoints?",
            r".*[Mm]etody",
            r"GET|POST|PUT|DELETE|PATCH",
            r"[Rr]equest.*[Bb]ody",
            r"[Rr]esponse.*[Bb]ody",
            r"[Pp]arametr",
            r"[Ss]chema",
        ],
        structure_indicators=[
            "{",
            "}",  # JSON-like structures
            "curl",
            "http://",
        ],
        weight=1.3,
    ),
    DocumentType.NOTATKI_PROJEKTOWE: ClassificationRule(
        doc_type=DocumentType.NOTATKI_PROJEKTOWE,
        keywords=[
            "spotkanie",
            "decyzj",
            "agenda",
            "notatk",
            "protokół",
            "minutes",
            "discuss",
            "action.*item",
            "task",
            "todo",
            "follow-up",
            "brainstorm",
            "idea",
            "proposal",
            "propozycj",
            "pytanie",
            "question",
        ],
        title_patterns=[
            r".*[Nn]otatk.*",
            r".*[Mm]eeting.*[Nn]otes.*",
            r".*[Pp]rotokół.*",
            r".*[Ss]potkanie.*",
            r".*[Aa]genda.*",
            r".*[Dd]ecyzj.*",
            r".*[Pp]ropozycj.*",
            r".*[Bb]rainstorm.*",
            r".*ROADMAP.*",
            r".*PROJECT.*PLAN.*",
        ],
        section_patterns=[
            r"[Pp]rzypomnienie",
            r"[Dd]ecyzje",
            r"[Aa]ction.*items?",
            r"[Zz]adania",
            r"[Dd]yskusj",
            r"[Nn]astępne.*kroki",
        ],
        structure_indicators=[
            "[ ]",
            "[x]",  # Checkboxes
            "TODO:",
            "FIXME:",
        ],
        weight=1.0,
    ),
    DocumentType.INNY: ClassificationRule(
        doc_type=DocumentType.INNY,
        keywords=[],
        title_patterns=[],
        section_patterns=[],
        structure_indicators=[],
        weight=0.5,
    ),
}


def _normalize_type(value: str | None) -> str:
    """Normalize a document-type string: strip accents, lowercase, trim.

    The LLM may return Polish-accented values (``specyfikacja_wymagań``); we
    match them against ``DocumentType`` values accent-insensitively.
    """
    nfkd = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


# Accent-insensitive lookup: normalized value → DocumentType
_TYPE_LOOKUP: dict[str, DocumentType] = {_normalize_type(t.value): t for t in DocumentType}


class DocumentClassifier:
    """Native document classifier using NLP rules and patterns.

    Classifies documents based on keyword presence, title patterns,
    section structure, and document organization indicators.
    """

    def __init__(self) -> None:
        self.rules = CLASSIFICATION_RULES

    # ── Native (sync) ───────────────────────────────────────────────────────

    def classify(self, doc_structure: DocumentStructure) -> ClassificationResult:
        """Classify a document structure using native NLP rules (sync).

        Preserved for existing callers. The async routing path delegates to
        :meth:`_classify_native` internally.
        """
        return self._classify_native(doc_structure)

    def _classify_native(self, doc: DocumentStructure) -> ClassificationResult:
        """Native NLP classification (keyword/title/section/structure scoring)."""
        scores, evidence = self._compute_scores_and_evidence(doc)

        if not scores or max(scores.values()) < 1.0:
            return ClassificationResult(
                doc_type=DocumentType.INNY,
                confidence=0.0,
                source=ClassificationSource.NATIVE,
                reasoning="Brak wyraźnych wskaźników typu dokumentu",
                native_confidence=0.0,
            )

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        # Calculate confidence (normalize to 0-100)
        confidence = min(100.0, (best_score / 10.0) * 100)
        reasoning = self._build_reasoning(best_type, evidence[best_type], confidence)

        return ClassificationResult(
            doc_type=best_type,
            confidence=confidence,
            source=ClassificationSource.NATIVE,
            reasoning=reasoning,
            native_confidence=confidence,
        )

    def _compute_scores_and_evidence(
        self, doc: DocumentStructure
    ) -> tuple[dict[DocumentType, float], dict[DocumentType, list[str]]]:
        """Score every document type, returning raw scores and human evidence."""
        scores: dict[DocumentType, float] = {}
        evidence: dict[DocumentType, list[str]] = {}

        for doc_type, rule in self.rules.items():
            score = 0.0
            type_evidence: list[str] = []

            # Check title patterns (high weight)
            title_score, title_evidence = self._check_title_patterns(doc, rule)
            score += title_score * 2.0  # Title matches are strong indicators
            type_evidence.extend(title_evidence)

            # Check section patterns (medium weight)
            section_score, section_evidence = self._check_section_patterns(doc, rule)
            score += section_score * 1.5
            type_evidence.extend(section_evidence)

            # Check keywords (lower weight, additive)
            keyword_score, keyword_evidence = self._check_keywords(doc, rule)
            score += keyword_score
            type_evidence.extend(keyword_evidence)

            # Check structure indicators (bonus)
            structure_score = self._check_structure_indicators(doc, rule)
            score += structure_score * 0.5

            # Apply rule weight
            score *= rule.weight

            scores[doc_type] = score
            evidence[doc_type] = type_evidence

        return scores, evidence

    def _native_scores(self, doc: DocumentStructure) -> dict[str, float]:
        """Raw per-type native scores for ``result_data["all_scores"]``.

        ``ClassificationResult`` has no ``all_scores`` field (schema freeze), so
        callers persist this map manually.
        """
        scores, _ = self._compute_scores_and_evidence(doc)
        return {doc_type.value: score for doc_type, score in scores.items()}

    # ── Async routing (native / llm / hybrid) — Story 2.3 closure ──────────

    async def classify_async(
        self,
        doc_structure: DocumentStructure,
        engine_mode: str,
        tenant_id: Any = None,
    ) -> ClassificationResult:
        """Route classification by the global ``engine_mode``.

        - ``native`` → native rules.
        - ``llm``    → LLM gateway (non-fatal native fallback on any error).
        - ``hybrid`` → native today; merge is a follow-up (Story 2.3 OOS).
        """
        engine = (engine_mode or "").strip().lower()

        if engine == "llm":
            result = await self._classify_llm(doc_structure, tenant_id=tenant_id)
        elif engine == "hybrid":
            result = self._classify_native(doc_structure)
            result.reasoning = (result.reasoning or "") + (
                " | [Uwaga: tryb hybrydowy nie jest zaimplementowany — użyto natywnej]"
            )
            logger.warning("Hybrid classification not implemented; falling back to native (Story 2.3 closure)")
        else:  # "native" and any unknown value → native
            result = self._classify_native(doc_structure)

        return self._enforce_min_confidence(result)

    async def _classify_llm(
        self,
        doc_structure: DocumentStructure,
        tenant_id: Any = None,
    ) -> ClassificationResult:
        """LLM-based classification with non-fatal native fallback (AC3)."""
        try:
            settings = get_settings()
            provider = self._select_llm_provider(settings)

            text = self._flatten_to_text(doc_structure)
            prompt = build_classification_prompt(text)
            messages = [
                LLMMessage(
                    "system",
                    "Zwracasz TYLKO JSON w formacie "
                    '{"type": "...", "confidence": 0-100, "reasoning": "..."}. '
                    "Bez dodatkowego tekstu ani komentarzy.",
                ),
                LLMMessage("user", prompt),
            ]

            gateway = get_llm_gateway()
            resp = await gateway.complete(
                provider=provider,
                messages=messages,
                model=None,
                max_tokens=256,
                temperature=0.0,
                tenant_id=tenant_id,
                module="classification",
                task_type="document_classification",
            )

            parsed = self._parse_llm_json(resp.content)
            doc_type = self._map_doc_type(parsed.get("type"))
            confidence = max(0.0, min(100.0, float(parsed.get("confidence", 0) or 0)))
            reasoning = (parsed.get("reasoning") or "Klasyfikacja LLM").strip()

            native = self._classify_native(doc_structure)
            return ClassificationResult(
                doc_type=doc_type,
                confidence=confidence,
                source=ClassificationSource.LLM,
                reasoning=reasoning,
                native_confidence=native.confidence,
                llm_confidence=confidence,
            )
        except Exception as exc:
            logger.warning("LLM classification failed — fallback to native: %s", exc)
            return self._classify_native(doc_structure)

    def _select_llm_provider(self, settings: Any) -> str:
        """Pick an LLM provider from configured API keys.

        No ``llm_provider`` setting exists; the provider is derived from
        whichever API key is present (Anthropic preferred). ``model=None`` lets
        the gateway choose the provider's default model.
        """
        if settings.anthropic_api_key.get_secret_value():
            return "anthropic"
        if settings.openai_api_key.get_secret_value():
            return "openai"
        raise LLMError("Brak skonfigurowanego providera LLM (anthropic_api_key/openai_api_key)")

    # ── AC6 / LLM helpers ───────────────────────────────────────────────────

    def _enforce_min_confidence(self, result: ClassificationResult) -> ClassificationResult:
        """AC6: confidence < 50 → force ``INNY`` and note low confidence."""
        if result.confidence < 50:
            logger.warning(
                "Low classification confidence (%.1f) — forcing type 'inny'",
                result.confidence,
            )
            result.doc_type = DocumentType.INNY
            result.reasoning = (result.reasoning or "") + " | Niska pewność klasyfikacji"
        return result

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

    def _parse_llm_json(self, content: str | None) -> dict[str, Any]:
        """Parse the LLM response into a dict, tolerating ```json fences."""
        text = (content or "").strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Odpowiedź LLM nie jest obiektem JSON")
        return data

    def _map_doc_type(self, raw: str | None) -> DocumentType:
        """Map an LLM type string to ``DocumentType`` (accent/case tolerant)."""
        key = _normalize_type(raw)
        if key in _TYPE_LOOKUP:
            return _TYPE_LOOKUP[key]
        raise ValueError(f"Nieznany typ dokumentu z LLM: {raw!r}")

    def _check_title_patterns(self, doc: DocumentStructure, rule: ClassificationRule) -> tuple[float, list[str]]:
        """Check if document title matches expected patterns."""
        if not doc.sections:
            return 0.0, []

        score = 0.0
        evidence: list[str] = []

        # Check root section titles
        for section in doc.sections[:3]:  # Only check first few sections
            title = section.title.lower()
            for pattern in rule.title_patterns:
                if re.search(pattern.lower(), title, re.IGNORECASE):
                    score += 3.0
                    evidence.append(f"Tytuł pasuje do wzorca: '{section.title}'")
                    break

        return score, evidence

    def _check_section_patterns(self, doc: DocumentStructure, rule: ClassificationRule) -> tuple[float, list[str]]:
        """Check if document has expected section structure."""
        score = 0.0
        evidence: list[str] = []

        all_sections = self._flatten_sections(doc.sections)
        section_titles = [s.title.lower() for s in all_sections]

        for pattern in rule.section_patterns:
            for title in section_titles:
                if re.search(pattern.lower(), title, re.IGNORECASE):
                    score += 1.5
                    evidence.append(f"Sekcja pasuje do wzorca: '{title}'")
                    break

        return score, evidence

    def _check_keywords(self, doc: DocumentStructure, rule: ClassificationRule) -> tuple[float, list[str]]:
        """Check for keyword presence in document content."""
        if not rule.keywords:
            return 0.0, []

        score = 0.0
        evidence: list[str] = []
        found_keywords: set[str] = set()

        # Collect all text from sections
        all_text = " ".join(s.title + " " + s.content for s in self._flatten_sections(doc.sections)).lower()

        # Count keyword matches
        for keyword in rule.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in all_text:
                found_keywords.add(keyword)
                score += 0.3

        if found_keywords:
            top_keywords = list(found_keywords)[:5]
            evidence.append(
                f"Słowa kluczowe: {', '.join(top_keywords)}"
                + (f" (+{len(found_keywords) - 5} więcej)" if len(found_keywords) > 5 else "")
            )

        return score, evidence

    def _check_structure_indicators(self, doc: DocumentStructure, rule: ClassificationRule) -> float:
        """Check for structural indicators specific to document type."""
        if not rule.structure_indicators:
            return 0.0

        all_text = " ".join(s.title + " " + s.content for s in self._flatten_sections(doc.sections))

        matches = sum(1 for indicator in rule.structure_indicators if indicator.lower() in all_text.lower())

        return float(matches)

    def _flatten_sections(self, sections: list[SectionStructure]) -> list[SectionStructure]:
        """Flatten hierarchical section list."""
        result = []
        for section in sections:
            result.append(section)
            if section.children:
                result.extend(self._flatten_sections(section.children))
        return result

    def _build_reasoning(self, doc_type: DocumentType, evidence: list[str], confidence: float) -> str:
        """Build human-readable reasoning string."""
        if not evidence:
            return f"Dokument sklasyfikowany jako {doc_type.value} na podstawie ogólnej analizy"

        return f"Dokument pasuje do typu '{doc_type.value}'. " + "; ".join(evidence[:3])


def classify_document(doc_structure: DocumentStructure) -> ClassificationResult:
    """Convenience function to classify a document structure (sync, native).

    Args:
        doc_structure: Preprocessed document structure

    Returns:
        ClassificationResult with type and confidence
    """
    classifier = DocumentClassifier()
    return classifier.classify(doc_structure)


async def classify_document_async(
    doc_structure: DocumentStructure,
    engine_mode: str,
    tenant_id: Any = None,
) -> ClassificationResult:
    """Async convenience: route classification via the global ``engine_mode``.

    Args:
        doc_structure: Preprocessed document structure
        engine_mode: ``"native"`` | ``"llm"`` | ``"hybrid"`` (from ``Settings``)
        tenant_id: Tenant id for LLM cost tracking (optional)

    Returns:
        ClassificationResult with type, confidence, source, and reasoning
    """
    classifier = DocumentClassifier()
    return await classifier.classify_async(doc_structure, engine_mode, tenant_id=tenant_id)
