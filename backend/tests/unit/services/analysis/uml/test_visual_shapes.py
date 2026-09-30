"""Unit tests for the pure-Python visual shape → UML mapping (Story 3.1b).

No CV/OCR dependency — exercises geometry, classification, relationship
reconstruction, confidence and source tagging on synthetic shapes.
"""

from app.models.uml_diagram import DiagramType, UMLModelSource
from app.services.analysis.uml.visual.shapes import (
    ARROW,
    DIAMOND,
    ELLIPSE,
    RECTANGLE,
    Box,
    Shape,
    TextLabel,
    build_relationships,
    build_visual_model,
    classify_visual_diagram_type,
)


def _node(kind: str, x: float, y: float, w: float = 100, h: float = 60, label: str | None = None) -> Shape:
    return Shape(kind=kind, box=Box(x, y, w, h), label=label)


class TestClassifyVisualDiagramType:
    def test_ovals_yield_use_case(self):
        shapes = [_node(ELLIPSE, 10, 10), _node(ELLIPSE, 200, 10), _node(RECTANGLE, 100, 200)]
        assert classify_visual_diagram_type(shapes) == DiagramType.USE_CASE

    def test_rectangles_yield_class(self):
        shapes = [_node(RECTANGLE, 10, 10), _node(RECTANGLE, 200, 10), _node(RECTANGLE, 100, 200)]
        assert classify_visual_diagram_type(shapes) == DiagramType.CLASS

    def test_diamonds_yield_activity(self):
        shapes = [_node(DIAMOND, 10, 10), _node(RECTANGLE, 200, 10), Shape(ARROW, Box(50, 50, 50, 5))]
        assert classify_visual_diagram_type(shapes) == DiagramType.ACTIVITY

    def test_empty_falls_back_to_sequence(self):
        assert classify_visual_diagram_type([]) == DiagramType.SEQUENCE


class TestBuildRelationships:
    def test_arrow_links_two_rectangles_by_proximity(self):
        left = _node(RECTANGLE, 10, 10, 80, 60, label="A")
        right = _node(RECTANGLE, 300, 10, 80, 60, label="B")
        arrow = Shape(ARROW, Box(90, 38, 210, 4), start=(90, 40), end=(300, 40))
        rels = build_relationships([left, right, arrow], labels=[])
        assert len(rels) == 1
        assert rels[0]["source"] == "A"
        assert rels[0]["target"] == "B"
        assert rels[0]["relationship_type"] == "association"

    def test_self_loop_with_identical_endpoints_is_dropped(self):
        node = _node(RECTANGLE, 10, 10, label="A")
        loop = Shape(ARROW, Box(20, 20, 0, 0), start=(50, 40), end=(50, 40))
        assert build_relationships([node, loop], labels=[]) == []


class TestBuildVisualModel:
    def test_source_is_ocr_and_confidence_bounded(self):
        shapes = [
            _node(RECTANGLE, 10, 10, label="A"),
            _node(RECTANGLE, 200, 10, label="B"),
        ]
        model = build_visual_model(shapes)
        assert model.source == UMLModelSource.OCR
        assert model.confidence is not None
        assert 0.0 <= model.confidence <= 1.0

    def test_unlabelled_nodes_get_anonymous_names_and_low_confidence(self):
        model = build_visual_model([_node(RECTANGLE, 10, 10)])
        assert model.elements[0]["name"].startswith("Rectangle")
        assert model.confidence is not None
        assert model.confidence <= 0.35  # shape-only inference capped low

    def test_ellipse_element_type_is_use_case(self):
        model = build_visual_model([_node(ELLIPSE, 10, 10, label="Login")])
        assert model.elements[0]["element_type"] == "use_case"

    def test_class_diagram_elements_carry_empty_attributes(self):
        model = build_visual_model([_node(RECTANGLE, 10, 10, label="Account")])
        assert model.diagram_type == DiagramType.CLASS
        assert model.elements[0]["element_type"] == "class"
        assert model.elements[0]["attributes"] == []

    def test_activity_diamonds_surface_as_decision_fragment(self):
        model = build_visual_model([_node(DIAMOND, 10, 10), _node(RECTANGLE, 200, 10)])
        assert model.diagram_type == DiagramType.ACTIVITY
        assert any(f["type"] == "decision" for f in model.fragments)


class TestAttachLabels:
    def test_label_binds_to_nearest_node(self):
        from app.services.analysis.uml.visual.shapes import attach_labels

        shapes = [_node(RECTANGLE, 10, 10, 80, 60), _node(RECTANGLE, 300, 10, 80, 60)]
        attach_labels(shapes, [TextLabel(text="Konto", x=50, y=40)])
        assert shapes[0].label == "Konto"
        assert shapes[1].label is None
