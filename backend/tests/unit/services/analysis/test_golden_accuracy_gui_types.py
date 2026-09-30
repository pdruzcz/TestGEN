"""Testy jednostkowe parsera per-typ raportu GUI w golden_accuracy (Story 3-14c, AC4).

``build_gui_type_report`` jest czystą funkcją — testujemy strukturę raportu
(11 typów + liczniki + ratio) bez uruchamiania artefakt generatora.
"""

from __future__ import annotations

from collections import Counter
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "golden_accuracy.py"


@pytest.fixture(scope="module")
def golden_accuracy():
    """Załaduj ``scripts/golden_accuracy.py`` jako moduł (nie jest pakietem)."""
    spec = spec_from_file_location("golden_accuracy", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gui_type_report_has_all_11_types_with_counts(golden_accuracy):
    """AC4: raport zawiera wszystkie 11 typów z licznikami GT i detekcji."""
    gt = Counter({t: 10 for t in golden_accuracy.GUI_TYPE_KEYS})
    detected = Counter({t: 8 for t in golden_accuracy.GUI_TYPE_KEYS})
    report = golden_accuracy.build_gui_type_report(gt, detected)

    assert [r["component_type"] for r in report] == list(golden_accuracy.GUI_TYPE_KEYS)
    assert len(report) == 11
    for row in report:
        assert row["gt_count"] == 10
        assert row["detected_count"] == 8
        assert row["ratio"] == pytest.approx(0.8)


def test_gui_type_report_zero_gt_yields_null_ratio(golden_accuracy):
    """Typ bez wystąpień GT → ratio None (nie ZeroDivisionError)."""
    report = golden_accuracy.build_gui_type_report(Counter(), Counter({"button": 3}))
    by_type = {r["component_type"]: r for r in report}
    assert by_type["button"]["ratio"] is None
    assert by_type["button"]["detected_count"] == 3
    assert by_type["modal"]["gt_count"] == 0


def test_gui_type_report_without_imaging_keeps_structure(golden_accuracy):
    """Bez imagingu (detected=None) raport trzyma 11 typów z samym GT."""
    gt = Counter({"button": 112, "modal": 10})
    report = golden_accuracy.build_gui_type_report(gt, None)
    assert len(report) == 11
    assert all(r["detected_count"] is None and r["ratio"] is None for r in report)
    assert {r["component_type"]: r["gt_count"] for r in report}["button"] == 112
