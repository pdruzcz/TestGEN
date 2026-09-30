"""Golden: zagregowana bramka jakościowa + regresja — Story 2.11 (AC3).

Jeden test uruchamia pełną analizę wszystkich próbek, agreguje metryki per
moduł (klasyfikacja accuracy, ekstrakcja wymagań recall/precision, detekcja
niespójności recall, glosariusz recall) i wywołuje ``check_regression``.
Pipeline CI fails, gdy jakakolwiek metryka spadnie poniżej progu
(``docs_thresholds.json``).
"""

from __future__ import annotations

import pytest

from tests.golden_data.doc_samples import (
    analyze_document_sample,
    detectable_inconsistencies,
    discover_doc_samples,
    normalize_doc_text,
)
from tests.golden_data.docs_regression_checker import check_regression

SAMPLES = discover_doc_samples()


def _compute_metrics() -> dict[str, dict[str, float]]:
    cls_ok = 0
    req_recall_sum = req_recall_n = 0
    req_prec_sum = req_prec_n = 0
    disc_found = disc_intent = 0
    glo_recall_sum = glo_recall_n = 0

    for sample in SAMPLES:
        analysis = analyze_document_sample(sample)
        gt = sample.ground_truth

        # klasyfikacja
        if analysis["classification"].doc_type.value == gt["expected_classification"]["doc_type"]:
            cls_ok += 1

        # wymagania
        exp_reqs = {normalize_doc_text(t) for t in gt["expected_requirements"]["expected_texts"]}
        if exp_reqs:
            found_reqs = {normalize_doc_text(r.text) for r in analysis["requirements"]}
            matched = len(found_reqs & exp_reqs)
            req_recall_sum += matched / len(exp_reqs)
            req_recall_n += 1
            if found_reqs:
                req_prec_sum += matched / len(found_reqs)
                req_prec_n += 1

        # niespójności (tylko próbki rozbieżne)
        if sample.has_intentional_discrepancies:
            disc_intent += len(gt["expected_inconsistencies"]["detectable_types"])
            disc_found += len(detectable_inconsistencies(analysis))

        # glosariusz
        exp_terms = {normalize_doc_text(t) for t in gt["expected_glossary"]["expected_terms"]}
        if exp_terms:
            found_terms = {normalize_doc_text(t.term) for t in analysis["glossary"]}
            glo_recall_sum += len(found_terms & exp_terms) / len(exp_terms)
            glo_recall_n += 1

    total = max(len(SAMPLES), 1)
    return {
        "classification": {"accuracy": cls_ok / total},
        "requirement_extraction": {
            "recall": req_recall_sum / req_recall_n if req_recall_n else 1.0,
            "precision": req_prec_sum / req_prec_n if req_prec_n else 1.0,
        },
        "discrepancy_detection": {"recall": disc_found / disc_intent if disc_intent else 1.0},
        "glossary_extraction": {"recall": glo_recall_sum / glo_recall_n if glo_recall_n else 1.0},
    }


@pytest.mark.golden
def test_quality_metrics_no_regression() -> None:
    metrics = _compute_metrics()
    alerts = check_regression(metrics)
    if alerts:
        report = "\n".join(f"  {a.render()}" for a in alerts)
        pytest.fail(f"Wykryto regresję metryk natywnej analizy dokumentacji:\n{report}\nMetryki: {metrics}")


@pytest.mark.golden
def test_metrics_reported_above_floor() -> None:
    """Sanity: wszystkie metryki > 0 (zbiór nie jest zdegradowany do zera)."""
    metrics = _compute_metrics()
    for module, values in metrics.items():
        for metric, value in values.items():
            assert value > 0.0, f"{module}/{metric} = 0 (moduł nie działa)"
