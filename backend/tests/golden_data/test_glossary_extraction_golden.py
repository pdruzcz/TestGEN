"""Golden: ekstrakcja glosariusza — Story 2.11 (AC1, AC2).

Per próbka: liczba terminów ≥ minimum, a recall (terminy z sekcji Glosariusz)
względem zamrożonego ground truth ≥ progu.
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
RECALL_FLOOR = 0.80


@pytest.mark.golden
@pytest.mark.parametrize("sample", SAMPLES, ids=SAMPLE_IDS)
def test_glossary_term_count_at_least_minimum(sample) -> None:
    expected = sample.ground_truth["expected_glossary"]
    result = analyze_document_sample(sample)
    assert len(result["glossary"]) >= expected["min_terms"]


@pytest.mark.golden
@pytest.mark.parametrize("sample", SAMPLES, ids=SAMPLE_IDS)
def test_glossary_recall(sample) -> None:
    expected = sample.ground_truth["expected_glossary"]
    result = analyze_document_sample(sample)
    expected_terms = {normalize_doc_text(t) for t in expected["expected_terms"]}
    if not expected_terms:
        pytest.skip("próbka bez oczekiwanych terminów")
    found_terms = {normalize_doc_text(t.term) for t in result["glossary"]}
    matched = len(found_terms & expected_terms)
    recall = matched / len(expected_terms)
    assert recall >= RECALL_FLOOR, f"recall glosariusza {recall:.2f} < {RECALL_FLOOR}"
