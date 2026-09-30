"""Golden regression tests for the UML parsers — Epic 3, Story 3.14.

Each ``*.puml`` sample is parsed through :class:`UMLParserOrchestrator` and the
resulting element / relationship / fragment / flow counts are compared against
the frozen ground truth. Per the story's tolerance rule (AC-2), counts may
under-report by < 10 % (missing elements) without failing; over-reporting is not
penalised because real parsers tend to be conservative on the golden samples.
"""

import pytest

from app.models.uml_diagram import UMLModelSource
from app.services.analysis.uml.orchestrator import UMLParserOrchestrator
from app.services.analysis.uml.visual_parser import VisualUMLParser
from tests.golden_data.conftest import (
    GoldenUMLSample,
    GoldenVisualUMLSample,
    discover_uml_samples,
    discover_uml_visual_samples,
)

pytestmark = pytest.mark.golden

_UML_SAMPLES = discover_uml_samples()
_TOLERANCE = 0.10  # missing elements may not exceed 10 % of the expected count.


def _missing_ratio(expected: int, actual: int) -> float:
    """Fraction of expected items the parser failed to produce (>= 0)."""
    if expected <= 0:
        return 0.0
    return max(0, expected - actual) / expected


def _orchestrator() -> UMLParserOrchestrator:
    return UMLParserOrchestrator()


def test_golden_uml_dataset_is_present():
    assert _UML_SAMPLES, "No golden UML samples discovered under tests/golden_data/uml."


@pytest.mark.parametrize("sample", _UML_SAMPLES, ids=[s.id for s in _UML_SAMPLES])
def test_diagram_type_detected(sample: GoldenUMLSample):
    detected = _orchestrator().detect_diagram_type(sample.content)
    assert detected.value == sample.diagram_type, (
        f"{sample.id}: detected {detected.value!r}, expected {sample.diagram_type!r}"
    )


@pytest.mark.parametrize("sample", _UML_SAMPLES, ids=[s.id for s in _UML_SAMPLES])
def test_parsed_counts_within_tolerance(sample: GoldenUMLSample):
    orch = _orchestrator()
    fmt = orch.detect_format(sample.content)
    model = orch._parse_content(sample.content, fmt)

    actual = {
        "participants": len(model.participants),
        "elements": len(model.elements),
        "relationships": len(model.relationships),
        "fragments": len(model.fragments),
        "flows": len(model.flows),
    }
    for key, count in actual.items():
        expected = sample.expected[f"expected_{key}_count"]
        ratio = _missing_ratio(expected, count)
        assert ratio <= _TOLERANCE, (
            f"{sample.id}: {key} missing ratio {ratio:.2f} exceeds tolerance "
            f"{_TOLERANCE:.2f} (expected {expected}, got {count})"
        )


# ── Visual (SVG) golden regression — Story 3.14 closure, AC2 ────────────────
#
# The Tier 2 visual path is routed through ``VisualUMLParser.parse_svg`` (the
# entry ``UMLParserOrchestrator._parse_visual`` delegates to for SVG), NOT
# ``_parse_content``. SVG is the highest-fidelity Tier 2 input (defusedxml,
# no CV/OCR binary) and is the always-on regression for the schema-adapter
# introduced in Story 3.1b. This section subsumes the standalone
# ``test_visual_golden.py`` so there is a single source of truth for the
# visual golden set. PDF/raster variants stay image-gated (separate suite).

_VISUAL_SAMPLES = discover_uml_visual_samples()
_VISUAL_ACCURACY_THRESHOLD = 0.70


def _visual_accuracy(model, expected_names: set[str], expected_rels: int) -> float:
    """Mean of element-name recall and relationship recall (Story 3.1b, AC4)."""
    detected_names = {e["name"] for e in model.elements}
    element_recall = len(detected_names & expected_names) / len(expected_names) if expected_names else 1.0
    detected_rels = len(model.relationships)
    rel_recall = min(detected_rels, expected_rels) / expected_rels if expected_rels else 1.0
    return (element_recall + rel_recall) / 2.0


def test_visual_golden_dataset_is_present():
    assert _VISUAL_SAMPLES, "No golden visual (SVG) samples discovered under tests/golden_data/uml/visual."


@pytest.mark.parametrize("sample", _VISUAL_SAMPLES, ids=[s.id for s in _VISUAL_SAMPLES])
def test_visual_diagram_type_detected(sample: GoldenVisualUMLSample):
    model = VisualUMLParser().parse_svg(sample.svg_content)
    assert model.diagram_type.value == sample.diagram_type, (
        f"{sample.id}: detected {model.diagram_type.value!r}, expected {sample.diagram_type!r}"
    )


@pytest.mark.parametrize("sample", _VISUAL_SAMPLES, ids=[s.id for s in _VISUAL_SAMPLES])
def test_visual_parsed_counts_within_tolerance(sample: GoldenVisualUMLSample):
    model = VisualUMLParser().parse_svg(sample.svg_content)
    actual = {
        "participants": len(model.participants),
        "elements": len(model.elements),
        "relationships": len(model.relationships),
        "fragments": len(model.fragments),
        "flows": len(model.flows),
    }
    for key, count in actual.items():
        expected = sample.expected[f"expected_{key}_count"]
        ratio = _missing_ratio(expected, count)
        assert ratio <= _TOLERANCE, (
            f"{sample.id}: {key} missing ratio {ratio:.2f} exceeds tolerance "
            f"{_TOLERANCE:.2f} (expected {expected}, got {count})"
        )


@pytest.mark.parametrize("sample", _VISUAL_SAMPLES, ids=[s.id for s in _VISUAL_SAMPLES])
def test_visual_source_is_ocr(sample: GoldenVisualUMLSample):
    """AC5: visual parsing always yields source = ocr (Tier 2 inference)."""
    model = VisualUMLParser().parse_svg(sample.svg_content)
    assert model.source == UMLModelSource.OCR


@pytest.mark.parametrize("sample", _VISUAL_SAMPLES, ids=[s.id for s in _VISUAL_SAMPLES])
def test_visual_confidence_reported(sample: GoldenVisualUMLSample):
    model = VisualUMLParser().parse_svg(sample.svg_content)
    assert model.confidence is not None
    assert 0.0 <= model.confidence <= 1.0


@pytest.mark.parametrize("sample", _VISUAL_SAMPLES, ids=[s.id for s in _VISUAL_SAMPLES])
def test_visual_accuracy_threshold(sample: GoldenVisualUMLSample):
    """Element-name + relationship recognition accuracy >= 70 % (Story 3.1b)."""
    model = VisualUMLParser().parse_svg(sample.svg_content)
    expected_names = set(sample.expected.get("expected_element_names", []))
    expected_rels = sample.expected["expected_relationships_count"]
    accuracy = _visual_accuracy(model, expected_names, expected_rels)
    assert accuracy >= _VISUAL_ACCURACY_THRESHOLD, (
        f"{sample.id}: accuracy {accuracy:.2f} < {_VISUAL_ACCURACY_THRESHOLD} "
        f"(elements={[e['name'] for e in model.elements]}, "
        f"relationships={len(model.relationships)})"
    )
