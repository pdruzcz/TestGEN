"""Golden: detekcja niespójności — Story 2.11 (AC1, AC2).

Wykrywalne typy niespójności (``duplicate``, ``missing_reference``) występują
WYŁĄCZNIE w próbkach z celowo wprowadzonymi rozbieżnościami. W spójnych
próbkach detektor nie znajduje żadnego z tych typów. Terminologia jest pomijana
(szum: "System"/"Użytkownik" w 3+ wymaganiach).
"""

from __future__ import annotations

import pytest

from tests.golden_data.doc_samples import (
    analyze_document_sample,
    detectable_inconsistencies,
    discover_doc_samples,
)

SAMPLES = discover_doc_samples()
SAMPLE_IDS = [s.id for s in SAMPLES]


@pytest.mark.golden
@pytest.mark.parametrize("sample", SAMPLES, ids=SAMPLE_IDS)
def test_detectable_types_match_intent(sample) -> None:
    """Wykrywalne typy = zamrożone oczekiwane (zbiór dokładny)."""
    expected = sample.ground_truth["expected_inconsistencies"]
    result = analyze_document_sample(sample)
    found = detectable_inconsistencies(result)
    found_types = {i.type for i in found}
    expected_types = set(expected["detectable_types"])
    assert found_types == expected_types, f"znalezione={found_types} oczekiwane={expected_types}"


@pytest.mark.golden
@pytest.mark.parametrize("sample", SAMPLES, ids=SAMPLE_IDS)
def test_detectable_count_at_least_minimum(sample) -> None:
    expected = sample.ground_truth["expected_inconsistencies"]
    result = analyze_document_sample(sample)
    found = detectable_inconsistencies(result)
    assert len(found) >= expected["min_detectable_count"]


@pytest.mark.golden
@pytest.mark.parametrize("sample", SAMPLES, ids=SAMPLE_IDS)
def test_clean_samples_have_no_detectable_discrepancies(sample) -> None:
    """Spójne próbki (bez intencji) nie generują wykrywalnych niespójności."""
    if sample.has_intentional_discrepancies:
        pytest.skip("próbka z celowymi niespójnościami")
    result = analyze_document_sample(sample)
    assert detectable_inconsistencies(result) == []
