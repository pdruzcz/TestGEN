"""Unit tests for DiagramCodeComparator (Story 3.4)."""

from uuid import uuid4

from app.services.analysis.uml.class_code_comparator import (
    CodeAttribute,
    CodeClass,
    CodeMethod,
    DiagramCodeComparator,
    StubCodeStructureProvider,
)
from app.services.analysis.uml.models import (
    AttributeDef,
    ClassDef,
    ClassModel,
    MethodDef,
    Visibility,
)


class _FakeProvider:
    def __init__(self, classes):
        self._classes = classes

    def get_classes(self, project_id):
        return self._classes

    def get_interfaces(self, project_id):
        return []


def _diagram(classes):
    return ClassModel(classes=classes)


def test_compare_matching_classes():
    diagram = _diagram(
        [
            ClassDef(
                name="User",
                attributes=[AttributeDef(name="email", type="String")],
                methods=[MethodDef(name="login")],
            )
        ]
    )
    provider = _FakeProvider(
        [
            CodeClass(
                name="User",
                attributes=[CodeAttribute(name="email", type="String")],
                methods=[CodeMethod(name="login")],
            )
        ]
    )
    result = DiagramCodeComparator().compare(diagram, provider, uuid4())
    assert len(result.matching_classes) == 1
    match = result.matching_classes[0]
    assert match.attribute_match_pct == 1.0
    assert match.method_match_pct == 1.0
    assert result.diagram_only_classes == []
    assert result.code_only_classes == []
    assert result.discrepancies == []


def test_compare_missing_in_code():
    diagram = _diagram([ClassDef(name="Ghost")])
    result = DiagramCodeComparator().compare(diagram, _FakeProvider([]), uuid4())
    assert result.diagram_only_classes == ["Ghost"]
    assert result.discrepancies[0].type == "missing_in_code"
    assert result.discrepancies[0].severity == "error"


def test_compare_missing_on_diagram():
    result = DiagramCodeComparator().compare(
        _diagram([]), _FakeProvider([CodeClass(name="Orphan")]), uuid4()
    )
    assert result.code_only_classes == ["Orphan"]
    extra = [d for d in result.discrepancies if d.type == "extra_in_code"]
    assert extra and extra[0].severity == "info"


def test_compare_attribute_discrepancies():
    diagram = _diagram(
        [
            ClassDef(
                name="User",
                attributes=[
                    AttributeDef(name="email", type="String", visibility=Visibility.PRIVATE),
                    AttributeDef(name="age", type="int"),
                ],
            )
        ]
    )
    provider = _FakeProvider(
        [CodeClass(name="User", attributes=[CodeAttribute(name="email", type="Integer")])]
    )
    result = DiagramCodeComparator().compare(diagram, provider, uuid4())
    kinds = {d.type for d in result.discrepancies}
    assert "missing_attribute" in kinds  # age absent in code
    assert "type_mismatch" in kinds  # email String vs Integer


def test_compare_method_discrepancies():
    diagram = _diagram(
        [ClassDef(name="Svc", methods=[MethodDef(name="run"), MethodDef(name="stop")])]
    )
    provider = _FakeProvider([CodeClass(name="Svc", methods=[CodeMethod(name="run")])])
    result = DiagramCodeComparator().compare(diagram, provider, uuid4())
    missing = [d for d in result.discrepancies if d.type == "missing_method"]
    assert len(missing) == 1
    assert "stop" in missing[0].details
    match = result.matching_classes[0]
    assert match.method_match_pct == 0.5


def test_stub_provider_returns_empty():
    provider = StubCodeStructureProvider()
    assert provider.get_classes(uuid4()) == []
    assert provider.get_interfaces(uuid4()) == []
