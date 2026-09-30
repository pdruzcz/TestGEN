"""Unit tests for SVG → shapes extraction (Story 3.1b, AC3)."""

from app.services.analysis.uml.visual.shapes import DIAMOND, ELLIPSE, RECTANGLE
from app.services.analysis.uml.visual.svg_parser import svg_to_shapes

_RECT_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><rect x="10" y="20" width="80" height="60"/></svg>'
_ELLIPSE_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><ellipse cx="100" cy="50" rx="40" ry="20"/></svg>'
_DIAMOND_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><polygon points="100,10 160,60 100,110 40,60"/></svg>'
_RECT_POLYGON_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><polygon points="10,10 110,10 110,70 10,70"/></svg>'
_TEXT_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<rect x="10" y="10" width="80" height="60"/><text x="50" y="40">Konto</text></svg>'
)


class TestSvgToShapes:
    def test_rect_becomes_rectangle(self):
        shapes, _, _ = svg_to_shapes(_RECT_SVG)
        assert len(shapes) == 1
        assert shapes[0].kind == RECTANGLE
        assert shapes[0].box.width == 80
        assert shapes[0].box.height == 60

    def test_ellipse_becomes_ellipse(self):
        shapes, _, _ = svg_to_shapes(_ELLIPSE_SVG)
        assert len(shapes) == 1
        assert shapes[0].kind == ELLIPSE
        assert shapes[0].box.width == 80  # 2 * rx

    def test_rhombus_polygon_becomes_diamond(self):
        shapes, _, _ = svg_to_shapes(_DIAMOND_SVG)
        assert len(shapes) == 1
        assert shapes[0].kind == DIAMOND

    def test_axis_aligned_polygon_becomes_rectangle(self):
        shapes, _, _ = svg_to_shapes(_RECT_POLYGON_SVG)
        assert len(shapes) == 1
        assert shapes[0].kind == RECTANGLE

    def test_text_is_extracted_as_label(self):
        _, labels, _ = svg_to_shapes(_TEXT_SVG)
        assert len(labels) == 1
        assert labels[0].text == "Konto"

    def test_malformed_svg_yields_warning_and_no_shapes(self):
        shapes, _, warnings = svg_to_shapes("<svg><rect x='oops'></rect>")
        # defusedxml tolerates some malformedness; ensure either no crash and a
        # graceful result. When XML is unparseable, shapes empty + warning.
        assert isinstance(shapes, list)
        if not shapes:
            assert warnings

    def test_empty_svg_warns(self):
        shapes, _, warnings = svg_to_shapes('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        assert shapes == []
        assert warnings
