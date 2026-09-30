"""Unit tests for the pure-Python layout analysis — Story 3.8, AC5."""

from app.models.gui_screenshot import GUIComponentType
from app.services.analysis.gui.layout_analyzer import LayoutAnalyzer
from app.services.analysis.gui.models import BBox, DetectedComponent, TextBlock


def _comp(ctype, bbox, label=None):
    return DetectedComponent(component_type=ctype, bbox=bbox, confidence=0.9, label=label)


class TestLayoutAnalyzer:
    def test_nesting_by_containment(self):
        form = _comp(GUIComponentType.FORM, BBox(0, 0, 400, 400))
        button = _comp(GUIComponentType.BUTTON, BBox(20, 350, 100, 40), label="OK")
        tree, warnings = LayoutAnalyzer().analyze([button, form], image_size=(800, 600))

        assert tree.type == "screen"
        assert len(tree.children) == 1
        form_node = tree.children[0]
        assert form_node.type == "form"
        assert any(c.type == "button" for c in form_node.children)
        assert warnings == []

    def test_label_assigned_to_input(self):
        inp = _comp(GUIComponentType.INPUT, BBox(120, 100, 200, 36))
        labels = [TextBlock(text="Email", bbox=BBox(60, 105, 50, 20))]
        tree, _ = LayoutAnalyzer().analyze([inp], labels, image_size=(800, 600))

        input_node = tree.children[0]
        assert input_node.label == "Email"

    def test_empty_components_warns(self):
        tree, warnings = LayoutAnalyzer().analyze([], [], image_size=(100, 100))
        assert tree.type == "screen"
        assert tree.children == []
        assert warnings

    def test_relations_button_in_form(self):
        form = _comp(GUIComponentType.FORM, BBox(0, 0, 400, 400), label="Logowanie")
        button = _comp(GUIComponentType.BUTTON, BBox(20, 350, 100, 40), label="Zaloguj")
        relations = LayoutAnalyzer().detect_relations([form, button])
        assert {"type": "button-form", "button": "Zaloguj", "form": "Logowanie"} in relations

    def test_to_dict_roundtrip(self):
        comp = _comp(GUIComponentType.BUTTON, BBox(1, 2, 3, 4), label="OK")
        tree, _ = LayoutAnalyzer().analyze([comp], image_size=(10, 10))
        d = tree.to_dict()
        assert d["type"] == "screen"
        assert d["children"][0]["bbox"] == {"x": 1, "y": 2, "width": 3, "height": 4}
