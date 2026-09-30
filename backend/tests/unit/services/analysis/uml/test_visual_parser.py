"""Unit tests for VisualUMLParser (Story 3.1b).

Covers the SVG path end-to-end and the raster/PDF graceful-degradation path
(heavy CV/OCR binaries are optional; garbage input must yield an empty
``source = ocr`` model with warnings rather than raising).
"""

from app.models.uml_diagram import UMLFormat, UMLModelSource
from app.services.analysis.uml.visual_parser import VisualUMLParser

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg">'
    '<rect x="10" y="10" width="80" height="60"/><text x="50" y="40">Konto</text>'
    '<rect x="200" y="10" width="80" height="60"/><text x="240" y="40">Zamowienie</text>'
    '<line x1="90" y1="40" x2="200" y2="40" marker-end="url(#a)"/>'
    "</svg>"
)


class TestParseSvg:
    def test_returns_ocr_sourced_model(self):
        model = VisualUMLParser().parse_svg(_SVG)
        assert model.source == UMLModelSource.OCR
        assert model.confidence is not None

    def test_extracts_class_elements(self):
        model = VisualUMLParser().parse_svg(_SVG)
        names = {e["name"] for e in model.elements}
        assert {"Konto", "Zamowienie"} <= names

    def test_reconstructs_relationship(self):
        model = VisualUMLParser().parse_svg(_SVG)
        assert len(model.relationships) == 1
        rel = model.relationships[0]
        assert {rel["source"], rel["target"]} == {"Konto", "Zamowienie"}

    def test_empty_svg_does_not_raise(self):
        model = VisualUMLParser().parse_svg('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        assert model.elements == []
        assert model.warnings  # graceful notice surfaced


class TestGracefulDegrade:
    def test_raster_garbage_degrades_to_empty_ocr_model(self):
        model = VisualUMLParser().parse_raster(b"not an image")
        assert model.source == UMLModelSource.OCR
        assert model.elements == []
        assert model.confidence == 0.0
        assert model.warnings  # decode/detection unavailable notice

    def test_pdf_without_rasteriser_degrades(self):
        model = VisualUMLParser().parse_pdf(b"%PDF-1.4 garbage")
        assert model.source == UMLModelSource.OCR
        assert model.elements == []
        assert model.warnings

    def test_parse_bytes_dispatches_pdf(self):
        model = VisualUMLParser().parse_bytes(b"%PDF-1.4 garbage", UMLFormat.PDF)
        assert model.source == UMLModelSource.OCR
        assert model.elements == []

    def test_parse_bytes_dispatches_raster(self):
        model = VisualUMLParser().parse_bytes(b"garbage", UMLFormat.RASTER)
        assert model.source == UMLModelSource.OCR
        assert model.elements == []
