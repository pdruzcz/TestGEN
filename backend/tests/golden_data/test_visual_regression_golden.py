"""Golden regression tests for the visual-regression engine — Story 3.14.

Each pair feeds its baseline/comparison component lists through the pure-Python
semantic-diff path (:func:`compute_component_delta` + :func:`classify_status`),
which requires no imaging dependencies, and asserts the engine reproduces the
frozen :class:`ComparisonStatus` verdict and the expected change types.
"""

import pytest

from app.models.gui_screenshot import GUIComponentType
from app.services.analysis.gui.models import BBox, DetectedComponent
from app.services.analysis.gui.visual_regression import (
    _DEFAULT_PIXEL_THRESHOLD,
    classify_status,
    compute_component_delta,
)
from tests.golden_data.conftest import GoldenVisualPair, discover_visual_pairs

pytestmark = pytest.mark.golden

_VISUAL_PAIRS = discover_visual_pairs()


def _to_components(raw: list[dict]) -> list[DetectedComponent]:
    return [
        DetectedComponent(
            component_type=GUIComponentType(c["component_type"]),
            bbox=BBox(**c["bbox"]),
            confidence=float(c.get("confidence", 0.0)),
            label=c.get("label"),
        )
        for c in raw
    ]


def test_golden_visual_dataset_is_present():
    assert _VISUAL_PAIRS, "No golden visual-regression pairs discovered."


@pytest.mark.parametrize("pair", _VISUAL_PAIRS, ids=[p.name for p in _VISUAL_PAIRS])
def test_status_and_change_types_match(pair: GoldenVisualPair):
    baseline = _to_components(pair.baseline_components)
    comparison = _to_components(pair.comparison_components)

    deltas = compute_component_delta(baseline, comparison, pair.pixel_pct)
    status = classify_status(pair.pixel_pct, deltas, _DEFAULT_PIXEL_THRESHOLD)

    assert status.value == pair.expected_status, (
        f"{pair.name}: status {status.value!r}, expected {pair.expected_status!r}"
    )

    actual_change_types = {d.change_type for d in deltas}
    expected_change_types = set(pair.expected_change_types)
    assert expected_change_types <= actual_change_types, (
        f"{pair.name}: expected change types {expected_change_types} "
        f"not all present in {actual_change_types}"
    )
    if not expected_change_types:
        assert not deltas, f"{pair.name}: expected no deltas, got {actual_change_types}"
