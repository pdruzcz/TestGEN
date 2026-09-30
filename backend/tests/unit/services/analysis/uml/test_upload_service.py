"""Unit tests for the UML upload service (Story 3.1).

Covers extension validation and format detection (extension-first with content
sniffing fallback for ambiguous ``.xml``).
"""

from app.models.uml_diagram import UMLFormat
from app.services.analysis.uml.upload_service import (
    UML_ALLOWED_EXTENSIONS,
    detect_format,
    detect_format_from_content,
    is_uml_extension,
)


class TestIsUmlExtension:
    def test_accepts_all_allowed_extensions(self):
        for ext in UML_ALLOWED_EXTENSIONS:
            assert is_uml_extension(f"diagram{ext}") is True

    def test_is_case_insensitive(self):
        assert is_uml_extension("Diagram.XMI") is True
        assert is_uml_extension("model.PlantUML") is True

    def test_rejects_unsupported_extension(self):
        assert is_uml_extension("notes.txt") is False
        assert is_uml_extension("archive.zip") is False

    def test_rejects_filename_without_extension(self):
        assert is_uml_extension("README") is False


class TestDetectFormatFromContent:
    def test_plantuml_marker_wins(self):
        assert detect_format_from_content(b"@startuml\nA -> B\n@enduml") == UMLFormat.PLANTUML

    def test_plantuml_marker_with_leading_whitespace(self):
        assert detect_format_from_content(b"\n   @startuml\n@enduml") == UMLFormat.PLANTUML

    def test_xml_declaration_detected_as_xmi(self):
        assert detect_format_from_content(b'<?xml version="1.0"?><xmi:XMI/>') == UMLFormat.XMI

    def test_xmi_tag_without_declaration(self):
        assert detect_format_from_content(b"<xmi:XMI xmi:version='2.1'></xmi:XMI>") == UMLFormat.XMI

    def test_angle_bracket_defaults_to_xmi(self):
        assert detect_format_from_content(b"<root></root>") == UMLFormat.XMI

    def test_non_xml_non_plantuml_defaults_to_plantuml(self):
        assert detect_format_from_content(b"actor User") == UMLFormat.PLANTUML


class TestDetectFormat:
    def test_puml_extension_forces_plantuml(self):
        # Even XML-looking content keeps PlantUML when extension is explicit.
        assert detect_format("a.puml", b"<?xml ?>") == UMLFormat.PLANTUML

    def test_plantuml_extension_forces_plantuml(self):
        assert detect_format("a.plantuml", b"") == UMLFormat.PLANTUML

    def test_xmi_extension_forces_xmi(self):
        assert detect_format("a.xmi", b"@startuml") == UMLFormat.XMI

    def test_xml_extension_sniffs_plantuml_content(self):
        assert detect_format("a.xml", b"@startuml\n@enduml") == UMLFormat.PLANTUML

    def test_xml_extension_sniffs_xmi_content(self):
        assert detect_format("a.xml", b'<?xml version="1.0"?>') == UMLFormat.XMI


class TestVisualExtensions:
    def test_visual_extensions_accepted(self):
        for ext in (".svg", ".pdf", ".png", ".jpeg", ".jpg"):
            assert ext in UML_ALLOWED_EXTENSIONS
            assert is_uml_extension(f"diagram{ext}") is True

    def test_visual_extensions_case_insensitive(self):
        assert is_uml_extension("Diagram.SVG") is True
        assert is_uml_extension("scan.PDF") is True
        assert is_uml_extension("photo.JPEG") is True


class TestDetectVisualFromContent:
    def test_svg_marker_detected(self):
        assert detect_format_from_content(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>') == UMLFormat.SVG

    def test_pdf_magic_detected(self):
        assert detect_format_from_content(b"%PDF-1.4\n%binary") == UMLFormat.PDF

    def test_png_magic_detected(self):
        assert detect_format_from_content(b"\x89PNG\r\n\x1a\n") == UMLFormat.RASTER

    def test_jpeg_magic_detected(self):
        assert detect_format_from_content(b"\xff\xd8\xff\xe0") == UMLFormat.RASTER


class TestDetectVisualByExtension:
    def test_svg_extension(self):
        assert detect_format("a.svg", b"") == UMLFormat.SVG

    def test_pdf_extension(self):
        assert detect_format("a.pdf", b"") == UMLFormat.PDF

    def test_raster_extensions(self):
        for ext in (".png", ".jpeg", ".jpg"):
            assert detect_format(f"photo{ext}", b"") == UMLFormat.RASTER
