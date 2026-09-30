"""Unit tests for UMLParserOrchestrator (Story 3.1).

Exercises format detection, diagram-type classification, validation, and
end-to-end content parsing against the golden fixtures.
"""

from pathlib import Path

import pytest

from app.models.uml_diagram import DiagramType, UMLFormat
from app.services.analysis.uml.orchestrator import UMLParserOrchestrator

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "uml"


@pytest.fixture(scope="module")
def sequence_puml() -> str:
    return (FIXTURES / "sample_sequence.puml").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def class_xmi() -> str:
    return (FIXTURES / "sample_class.xmi").read_text(encoding="utf-8")


@pytest.fixture()
def orchestrator() -> UMLParserOrchestrator:
    return UMLParserOrchestrator()


class TestDetectFormat:
    def test_plantuml_content(self, orchestrator, sequence_puml):
        assert orchestrator.detect_format(sequence_puml) == UMLFormat.PLANTUML

    def test_xmi_content(self, orchestrator, class_xmi):
        assert orchestrator.detect_format(class_xmi) == UMLFormat.XMI

    def test_plantuml_wins_over_xml_markers(self, orchestrator):
        assert orchestrator.detect_format("<?xml?>\n@startuml\n@enduml") == UMLFormat.PLANTUML

    def test_plain_text_defaults_to_plantuml(self, orchestrator):
        assert orchestrator.detect_format("just some text") == UMLFormat.PLANTUML


class TestDetectDiagramType:
    def test_sequence_diagram(self, orchestrator, sequence_puml):
        assert orchestrator.detect_diagram_type(sequence_puml) == DiagramType.SEQUENCE

    def test_empty_content_falls_back_to_sequence(self, orchestrator):
        assert orchestrator.detect_diagram_type("") == DiagramType.SEQUENCE


class TestValidate:
    def test_valid_plantuml(self, orchestrator, sequence_puml):
        result = orchestrator.validate(sequence_puml, UMLFormat.PLANTUML)
        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_plantuml_missing_markers(self, orchestrator):
        result = orchestrator.validate("actor User", UMLFormat.PLANTUML)
        assert result.is_valid is False
        assert len(result.errors) == 2

    def test_valid_xmi(self, orchestrator, class_xmi):
        result = orchestrator.validate(class_xmi, UMLFormat.XMI)
        assert result.is_valid is True

    def test_invalid_xmi_malformed(self, orchestrator):
        result = orchestrator.validate("<root><unclosed></root>", UMLFormat.XMI)
        assert result.is_valid is False
        assert result.errors


class TestParseContent:
    def test_parse_plantuml_sequence(self, orchestrator, sequence_puml):
        model = orchestrator._parse_content(sequence_puml, UMLFormat.PLANTUML)
        assert model.diagram_type == DiagramType.SEQUENCE
        names = {p["name"] for p in model.participants}
        assert "User" in names

    def test_parse_xmi_class(self, orchestrator, class_xmi):
        model = orchestrator._parse_content(class_xmi, UMLFormat.XMI)
        assert model.diagram_type == DiagramType.CLASS
        names = {e["name"] for e in model.elements}
        assert {"Account", "SavingsAccount", "Payable"} <= names

    def test_xmi_extracts_attributes(self, orchestrator, class_xmi):
        model = orchestrator._parse_content(class_xmi, UMLFormat.XMI)
        account = next(e for e in model.elements if e["name"] == "Account")
        attr_names = {a["name"] for a in account["attributes"]}
        assert {"balance", "owner"} <= attr_names

    def test_xmi_extracts_generalization(self, orchestrator, class_xmi):
        model = orchestrator._parse_content(class_xmi, UMLFormat.XMI)
        gens = [r for r in model.relationships if r["relationship_type"] == "inheritance"]
        assert any(r["source"] == "SavingsAccount" and r["target"] == "Account" for r in gens)
