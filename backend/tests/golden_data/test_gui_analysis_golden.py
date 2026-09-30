"""Golden regression tests for GUI ground-truth inventories — Story 3.14.

The GUI analyser depends on optional imaging libraries (``cv2`` / ``pytesseract``)
and on real PNG fixtures, neither of which is part of the curated golden set.
These tests therefore validate the *ground-truth* inventories themselves —
their schema, the component-type vocabulary and the per-category coverage — so
that the dataset remains a reliable contract for the analyser's expected output.

When the imaging stack and PNG fixtures are later added, the same
``GoldenGUISample`` objects can be fed straight into ``GUIAnalyzerOrchestrator``.
"""

import json

import pytest

from app.models.gui_screenshot import GUIComponentType
from tests.golden_data.conftest import GoldenGUISample, discover_gui_samples

pytestmark = pytest.mark.golden

_GUI_SAMPLES = discover_gui_samples()
_VALID_TYPES = {t.value for t in GUIComponentType}
_EXPECTED_CATEGORIES = {"forms", "dashboards", "tables", "navigation", "modals"}
_BBOX_KEYS = {"x", "y", "width", "height"}


def test_golden_gui_dataset_is_present():
    assert _GUI_SAMPLES, "No golden GUI samples discovered under tests/golden_data/gui."


def test_all_categories_covered():
    categories = {s.category for s in _GUI_SAMPLES}
    missing = _EXPECTED_CATEGORIES - categories
    assert not missing, f"Golden GUI dataset missing categories: {sorted(missing)}"


@pytest.mark.parametrize("sample", _GUI_SAMPLES, ids=[s.id for s in _GUI_SAMPLES])
def test_components_have_valid_schema(sample: GoldenGUISample):
    assert sample.expected_components, f"{sample.id}: no expected components"
    for comp in sample.expected_components:
        assert comp["component_type"] in _VALID_TYPES, (
            f"{sample.id}: unknown component_type {comp['component_type']!r}"
        )
        bbox = comp["bbox"]
        assert set(bbox) >= _BBOX_KEYS, f"{sample.id}: bbox missing keys {bbox}"
        assert bbox["width"] > 0 and bbox["height"] > 0, (
            f"{sample.id}: non-positive bbox dimensions {bbox}"
        )
        assert 0.0 <= comp["confidence"] <= 1.0, (
            f"{sample.id}: confidence out of range {comp['confidence']}"
        )


@pytest.mark.parametrize("sample", _GUI_SAMPLES, ids=[s.id for s in _GUI_SAMPLES])
def test_expected_count_matches_inventory(sample: GoldenGUISample):
    data = json.loads(sample.path.read_text(encoding="utf-8"))
    declared = data.get("expected_component_count")
    if declared is not None:
        assert declared == sample.expected_count, (
            f"{sample.id}: declared count {declared} != inventory {sample.expected_count}"
        )
