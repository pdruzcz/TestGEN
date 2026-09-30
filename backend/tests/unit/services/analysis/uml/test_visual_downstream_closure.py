"""Regression for the visual → downstream seam (Story 3-1b closure, AC1-AC4).

Before this closure, ``build_visual_model`` emitted only visual fields
(``element_type``, ``bbox``, name-based ``source``/``target``), so every
downstream consumer written against the structural schema (cross-diagram 3.7,
compare-code 3.4) silently saw empty results from OCR/visual diagrams while the
pipeline still reported ``status``/``confidence`` as if nothing was wrong.

These tests pin the fix: visual models now carry the structural discriminators
(``element_kind`` / ``id`` / ``node_type`` / ``is_initial`` / ``is_final`` /
``source_id`` / ``target_id``), so the same diagrams feed downstream and
compare-code no longer reports a vacuous 100 % match on empty member lists.
"""

from pathlib import Path
from uuid import uuid4

from app.models.uml_diagram import DiagramType, UMLModelSource
from app.services.analysis.cross_diagram_analyzer import (
    _class_names,
    build_integrated_model,
    reconstruct_flows,
)
from app.services.analysis.uml.class_code_comparator import (
    CodeClass,
    DiagramCodeComparator,
    class_model_from_columns,
)
from app.services.analysis.uml.integrated_model import DiagramBundle
from app.services.analysis.uml.visual.shapes import (
    RECTANGLE,
    Box,
    Shape,
    build_visual_model,
)
from app.services.analysis.uml.visual_parser import VisualUMLParser

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "uml" / "visual"


def _bundle_from_parsed(model, diagram_id: str, name: str) -> DiagramBundle:
    return DiagramBundle(
        diagram_id=diagram_id,
        diagram_type=model.diagram_type.value,
        name=name,
        participants=model.participants,
        elements=model.elements,
        relationships=model.relationships,
        fragments=model.fragments,
        flows=model.flows,
    )


def _parse(filename: str):
    svg = (FIXTURES / filename).read_text(encoding="utf-8")
    return VisualUMLParser().parse_svg(svg)


# --- AC1: visual emits the structural schema ------------------------------


class TestAdapterEmitsStructuralFields:
    def test_class_elements_carry_element_kind(self):
        model = _parse("class_diagram.svg")
        assert model.diagram_type == DiagramType.CLASS
        kinds = {e.get("element_kind") for e in model.elements}
        # Every class-diagram rectangle is tagged so compare-code / cross-diagram
        # can discriminate it (interface/enum detection is an inherent OCR limit).
        assert kinds == {"class"}
        assert all("id" in e for e in model.elements)

    def test_activity_nodes_carry_id_and_node_type(self):
        model = _parse("regression_activity.svg")
        assert model.diagram_type == DiagramType.ACTIVITY
        types = {e.get("node_type") for e in model.elements}
        # Topology + labels yield a start, an action, a decision and a stop.
        assert "start" in types
        assert "action" in types
        assert "decision" in types
        assert "stop" in types

    def test_relationships_carry_resolved_ids(self):
        model = _parse("class_diagram.svg")
        assert model.relationships
        for rel in model.relationships:
            assert rel.get("source_id") is not None
            assert rel.get("target_id") is not None

    def test_state_nodes_carry_initial_final_flags(self):
        # The shape classifier cannot detect state machines (it never returns
        # STATE_MACHINE), so force the type to exercise the state-field emitter
        # and the downstream _reconstruct_state path directly.
        shapes = [
            Shape(RECTANGLE, Box(10, 10, 80, 60), label="Draft"),
            Shape(RECTANGLE, Box(200, 10, 80, 60), label="Active"),
            Shape(RECTANGLE, Box(400, 10, 80, 60), label="Closed"),
            Shape("arrow", Box(90, 38, 110, 4), start=(90, 40), end=(200, 40)),
            Shape("arrow", Box(280, 38, 120, 4), start=(280, 40), end=(400, 40)),
        ]
        model = build_visual_model(shapes, diagram_type=DiagramType.STATE_MACHINE)
        assert model.diagram_type == DiagramType.STATE_MACHINE
        flags = {(e.get("is_initial"), e.get("is_final")) for e in model.elements}
        # Root (Draft) is initial, sink (Closed) is final, middle (Active) neither.
        assert (True, False) in flags
        assert (False, True) in flags
        assert (False, False) in flags


# --- AC2: cross-diagram (3.7) sees OCR diagrams ---------------------------


class TestCrossDiagramSeesOcr:
    def test_class_names_non_empty_from_ocr(self):
        # Before the closure, _class_names filtered on element_kind and got [].
        bundle = _bundle_from_parsed(_parse("class_diagram.svg"), "cls", "class.svg")
        integrated = build_integrated_model([bundle])
        names = _class_names(integrated)
        assert {"Account", "Order", "Customer"} <= set(names)

    def test_activity_flows_non_empty_from_ocr(self):
        bundle = _bundle_from_parsed(_parse("regression_activity.svg"), "act", "regression_activity.svg")
        integrated = build_integrated_model([bundle])
        flows, _ = reconstruct_flows(integrated)
        # Before the closure, _reconstruct_activity found no start node and no
        # source_id edges, so it produced zero flows.
        assert flows
        assert all(flow.steps for flow in flows)

    def test_state_flows_non_empty_from_ocr(self):
        shapes = [
            Shape(RECTANGLE, Box(10, 10, 80, 60), label="Draft"),
            Shape(RECTANGLE, Box(200, 10, 80, 60), label="Active"),
            Shape(RECTANGLE, Box(400, 10, 80, 60), label="Closed"),
            Shape("arrow", Box(90, 38, 110, 4), start=(90, 40), end=(200, 40)),
            Shape("arrow", Box(280, 38, 120, 4), start=(280, 40), end=(400, 40)),
        ]
        model = build_visual_model(shapes, diagram_type=DiagramType.STATE_MACHINE)
        bundle = _bundle_from_parsed(model, "st", "state.svg")
        integrated = build_integrated_model([bundle])
        flows, _ = reconstruct_flows(integrated)
        # Before the closure, _reconstruct_state found no is_initial state and no
        # source_id transitions, so it produced zero flows.
        assert flows
        assert all(flow.steps for flow in flows)

    def test_ocr_source_and_confidence_preserved(self):
        # OCR must not be conflated with full structural extraction. ``source``
        # is the honest discriminator; confidence measures shape/label detection
        # quality (a perfectly labelled SVG can be 1.0) — NOT member completeness,
        # which is why compare-code needs the explicit None marker (AC3).
        model = _parse("class_diagram.svg")
        assert model.source == UMLModelSource.OCR
        assert model.confidence is not None
        assert 0.0 <= model.confidence <= 1.0


# --- AC3: compare-code (3.4) is honest about OCR --------------------------


class _CodeProvider:
    def __init__(self, classes):
        self._classes = classes

    def get_classes(self, project_id):
        return self._classes

    def get_interfaces(self, project_id):
        return []


class TestCompareCodeHonestOnOcr:
    def test_empty_member_lists_yield_null_not_vacuous_100(self):
        model = _parse("class_diagram.svg")
        class_model = class_model_from_columns(model.elements, model.relationships, model.fragments)
        # Code side declares the same class with real members; the diagram side
        # (OCR) extracted none. A vacuous 100 % match would be a lie.
        provider = _CodeProvider([CodeClass(name="Account")])
        result = DiagramCodeComparator().compare(class_model, provider, uuid4())
        match = next(m for m in result.matching_classes if m.diagram_class == "Account")
        assert match.attribute_match_pct is None
        assert match.method_match_pct is None
