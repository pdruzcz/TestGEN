"""Golden: ekstrakcja wymagań — Story 2.11 (AC1, AC2).

Per próbka: liczba wyekstrahowanych wymagań ≥ minimum, a recall/precision
(dopasowanie znormalizowanego tekstu do zamrożonego ground truth) ≥ progu.
Wykrywa regresje: utracone wymagania lub fałszywe dopasowania po zmianie wzorców.
"""

from __future__ import annotations

import pytest

from tests.golden_data.doc_samples import (
    analyze_document_sample,
    discover_doc_samples,
    normalize_doc_text,
)

SAMPLES = discover_doc_samples()
SAMPLE_IDS = [s.id for s in SAMPLES]
# Próg per próbka — margines poniżej zamrożonego baseline'u (=1.0).
RECALL_FLOOR = 0.80
PRECISION_FLOOR = 0.80


@pytest.mark.golden
@pytest.mark.parametrize("sample", SAMPLES, ids=SAMPLE_IDS)
def test_requirement_count_at_least_minimum(sample) -> None:
    expected = sample.ground_truth["expected_requirements"]
    result = analyze_document_sample(sample)
    assert len(result["requirements"]) >= expected["min_count"]


@pytest.mark.golden
@pytest.mark.parametrize("sample", SAMPLES, ids=SAMPLE_IDS)
def test_requirement_recall_precision(sample) -> None:
    expected = sample.ground_truth["expected_requirements"]
    result = analyze_document_sample(sample)
    expected_texts = {normalize_doc_text(t) for t in expected["expected_texts"]}
    if not expected_texts:
        pytest.skip("próbka bez wymagań (podręcznik/instrukcja)")
    found_texts = {normalize_doc_text(r.text) for r in result["requirements"]}
    matched = len(found_texts & expected_texts)
    recall = matched / len(expected_texts)
    precision = matched / len(found_texts) if found_texts else 1.0
    assert recall >= RECALL_FLOOR, f"recall {recall:.2f} < {RECALL_FLOOR}"
    assert precision >= PRECISION_FLOOR, f"precision {precision:.2f} < {PRECISION_FLOOR}"
