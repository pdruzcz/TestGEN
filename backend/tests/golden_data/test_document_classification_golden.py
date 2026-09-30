"""Golden: klasyfikacja typu dokumentu — Story 2.11 (AC1, AC2).

Per próbka: typ dokumentu zgodny z intencją (specyfikacja/podręcznik/instrukcja)
oraz pewność ≥ konserwatywnego progu. Regresja: zmiana reguł klasyfikatora,
która psuje typ lub drastycznie obniża pewność, zostanie wychwycona.
"""

from __future__ import annotations

import pytest

from tests.golden_data.doc_samples import analyze_document_sample, discover_doc_samples

SAMPLES = discover_doc_samples()
SAMPLE_IDS = [s.id for s in SAMPLES]


@pytest.mark.golden
@pytest.mark.parametrize("sample", SAMPLES, ids=SAMPLE_IDS)
def test_doc_type_matches_intent(sample) -> None:
    expected = sample.ground_truth["expected_classification"]
    result = analyze_document_sample(sample)
    assert result["classification"].doc_type.value == expected["doc_type"]


@pytest.mark.golden
@pytest.mark.parametrize("sample", SAMPLES, ids=SAMPLE_IDS)
def test_doc_confidence_above_floor(sample) -> None:
    expected = sample.ground_truth["expected_classification"]
    result = analyze_document_sample(sample)
    assert result["classification"].confidence >= expected["min_confidence"]
