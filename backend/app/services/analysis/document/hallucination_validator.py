"""Hallucination validation for LLM-extracted requirements — Story 2.5.

Lightweight, dependency-free checks that an LLM-extracted requirement is
grounded in the source document:

- **language consistency** — a Polish document should yield Polish-looking text
  (presence of Polish diacritics, or absence of strong English markers). No
  ``langdetect`` — a simple diacritic heuristic.
- **content grounding** — enough of the requirement's keywords appear in the
  source text (token overlap, reusing ``normalize_text`` from the extractor).

Rejected requirements are logged with a reason and dropped — they are never
persisted into ``AnalysisResult.result_data``.

This module deliberately imports only ``normalize_text`` from
``requirement_extractor``; the extractor imports the validator lazily inside
``extract_llm`` to avoid a circular import.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.services.analysis.document.requirement_extractor import normalize_text

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.services.analysis.document.requirement_extractor import ExtractedRequirement

logger = logging.getLogger(__name__)

# Polish diacritics — strong indicator the text is Polish.
_POLISH_CHARS = set("ąęśćźżółńĄĘŚĆŹŻÓŁŃ")

# English markers that, combined with the absence of Polish diacritics, flag a
# language mismatch. Surrounded by spaces to reduce false positives on substrings.
_EN_MARKERS = (" the ", " and the ", " must be ", " should be ", " shall ")


@dataclass
class ValidationResult:
    """Outcome of validating a single requirement."""

    is_valid: bool
    reasons: list[str] = field(default_factory=list)


class HallucinationValidator:
    """Validate LLM-extracted requirements against the source text."""

    def _check_language_consistency(self, text: str, document_language: str = "pl") -> bool:
        """Heuristically check that ``text`` matches ``document_language``.

        For Polish (the only supported doc language today), the text passes when
        it contains at least one Polish diacritic, OR when it has no Polish
        diacritics but also no strong English markers (lenient pass — many valid
        Polish sentences use no diacritics). It fails only when there are no
        Polish diacritics AND an English marker is present.
        """
        if document_language.lower() != "pl":
            return True

        if any(ch in _POLISH_CHARS for ch in text):
            return True

        lowered = f" {text.lower()} "
        return not any(marker in lowered for marker in _EN_MARKERS)

    def _check_content_grounding(self, text: str, source_text: str, threshold: float = 0.5) -> bool:
        """Check that enough of ``text``'s keywords appear in ``source_text``.

        Tokens of length >= 4 are treated as keywords; the requirement is
        grounded when at least ``threshold`` of its keywords occur in the source.
        """
        tokens = {t for t in normalize_text(text).split() if len(t) >= 4}
        if not tokens:
            return True

        source_tokens = set(normalize_text(source_text).split())
        if not source_tokens:
            return False

        overlap = sum(1 for token in tokens if token in source_tokens) / len(tokens)
        return overlap >= threshold

    def validate(
        self,
        req: ExtractedRequirement,
        source_text: str,
        document_language: str = "pl",
    ) -> ValidationResult:
        """Run all checks and collect failure reasons.

        Args:
            req: The LLM-extracted requirement to validate.
            source_text: The (flattened) document text the requirement must be
                grounded in.
            document_language: Expected document language (``"pl"`` by default).

        Returns:
            ``ValidationResult`` — ``is_valid`` is ``True`` only when all checks
            pass.
        """
        reasons: list[str] = []

        if not self._check_language_consistency(req.text, document_language):
            reasons.append("language_mismatch")

        if not self._check_content_grounding(req.text, source_text):
            reasons.append("content_not_grounded")

        return ValidationResult(is_valid=not reasons, reasons=reasons)
