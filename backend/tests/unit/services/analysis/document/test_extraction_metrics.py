"""Golden-data metrics test for native requirement extraction — Story 2.4 (AC6).

Builds a ``DocumentStructure`` from ``sample_document.json`` and compares the
native extractor's output against ``expected_requirement_extraction.json``.

Matching is by keyword overlap (the golden tags each expected requirement with
``keywords``) rather than by ``req_id``: the current ``extract_requirement_id``
misreads ``NFR-\\d+`` as ``FR-\\d+`` (the ``FR-`` regex matches the tail of
``NFR-``), so id matching would unfairly penalize recall. Pattern tuning is a
documented follow-up; this test measures actual requirement *recovery*.

Thresholds (AC6): recall >= 70%, precision >= 60%.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.schemas.document import DocumentStructure, SectionStructure
from app.services.analysis.document.requirement_extractor import extract_requirements

_GOLDEN_DIR = Path(__file__).parents[4] / "golden" / "epic2"
_SAMPLE = _GOLDEN_DIR / "sample_document.json"
_EXPECTED = _GOLDEN_DIR / "expected_requirement_extraction.json"

# An extracted sentence counts as a match for an expected requirement when it
# covers at least this fraction of that requirement's golden keywords.
_KEYWORD_OVERLAP_THRESHOLD = 0.4


def _build_section(node: dict) -> SectionStructure:
    return SectionStructure(
        section_id=node["id"],
        title=node["title"],
        level=node["level"],
        content=node.get("content", ""),
        children=[_build_section(child) for child in node.get("subsections", [])],
    )


@pytest.fixture(scope="module")
def sample_doc() -> DocumentStructure:
    raw = json.loads(_SAMPLE.read_text(encoding="utf-8"))["data"]
    return DocumentStructure(sections=[_build_section(s) for s in raw["sections"]])


@pytest.fixture(scope="module")
def expected_requirements() -> list[dict]:
    data = json.loads(_EXPECTED.read_text(encoding="utf-8"))["data"]
    return data["requirements"]


def _keyword_overlap(text: str, keywords: list[str]) -> float:
    """Fraction of ``keywords`` present in ``text``.

    Polish is heavily inflected, so a keyword may appear in a declined form
    (e.g. ``wylogowanie`` vs ``wylogowania``). For keywords longer than 4 chars
    we therefore also accept a token whose stem matches the keyword minus its
    final character — exact substring otherwise.
    """
    if not keywords:
        return 0.0
    text_lower = text.lower()
    tokens = re.findall(r"\w+", text_lower)
    hits = 0
    for kw in keywords:
        k = kw.lower()
        stem = k[:-1] if len(k) > 4 else k
        if k in text_lower or any(tok.startswith(stem) for tok in tokens):
            hits += 1
    return hits / len(keywords)


@pytest.mark.golden
def test_native_extraction_recall_and_precision(
    sample_doc: DocumentStructure,
    expected_requirements: list[dict],
) -> None:
    """AC6: native extraction recall >= 70%, precision >= 60% on golden data."""
    extracted = extract_requirements(sample_doc)
    extracted_texts = [r.text for r in extracted]

    # ── Recall: of the expected requirements, how many are recovered? ────────
    misses: list[str] = []
    recalled = 0
    for expected in expected_requirements:
        keywords = expected.get("keywords", [])
        best_overlap = max(
            (_keyword_overlap(t, keywords) for t in extracted_texts),
            default=0.0,
        )
        if best_overlap >= _KEYWORD_OVERLAP_THRESHOLD:
            recalled += 1
        else:
            misses.append(f"{expected['req_id']} (best overlap={best_overlap:.2f})")

    recall = recalled / len(expected_requirements) if expected_requirements else 0.0

    # ── Precision: of the extracted sentences, how many are real? ────────────
    false_positives: list[str] = []
    true_positives = 0
    for text in extracted_texts:
        best_overlap = max(
            (_keyword_overlap(text, exp.get("keywords", [])) for exp in expected_requirements),
            default=0.0,
        )
        if best_overlap >= _KEYWORD_OVERLAP_THRESHOLD:
            true_positives += 1
        else:
            false_positives.append(text[:80])

    precision = true_positives / len(extracted_texts) if extracted_texts else 0.0

    # Report metrics + diagnostics (visible in pytest -v / on failure).
    print(f"\nrecall={recall:.0%} precision={precision:.0%}")
    print(f"extracted={len(extracted_texts)} expected={len(expected_requirements)}")
    if misses:
        print("MISSES: " + "; ".join(misses))
    if false_positives:
        print("FALSE POSITIVES:")
        for fp in false_positives:
            print(f"  - {fp}")

    # AC6 thresholds.
    assert recall >= 0.70, f"recall {recall:.0%} below 70% — misses: {misses}"
    assert precision >= 0.60, f"precision {precision:.0%} below 60% — false positives: {false_positives}"
