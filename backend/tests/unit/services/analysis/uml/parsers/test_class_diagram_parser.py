"""Unit tests for ClassDiagramParser (Story 3.4) using golden fixtures."""

from pathlib import Path
from uuid import uuid4

import pytest
from defusedxml.ElementTree import fromstring

from app.services.analysis.uml.class_code_comparator import (
    DiagramCodeComparator,
    StubCodeStructureProvider,
)
from app.services.analysis.uml.models import Visibility
from app.services.analysis.uml.parsers.class_diagram import ClassDiagramParser

FIXTURES = Path(__file__).resolve().parents[5] / "fixtures" / "uml" / "class"

# Expected element counts per golden sample (classes + interfaces + enums).
_GOLDEN_EXPECTED = {
    "simple_domain.puml": 3,
    "design_patterns.puml": 6,
    "ecommerce_full.puml": 7,
    "complex_hierarchy.puml": 7,
    "java_spring.xmi": 6,
}


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def parser() -> ClassDiagramParser:
    return ClassDiagramParser()


class TestPlantUMLClasses:
    def test_parse_plantuml_classes(self, parser):
        model = parser.build_class_model(_read("simple_domain.puml"))
        names = {c.name for c in model.classes}
        assert names == {"User", "Order", "Product"}
        user = next(c for c in model.classes if c.name == "User")
        attr_names = {a.name for a in user.attributes}
        assert {"id", "username", "passwordHash"} <= attr_names
        method_names = {m.name for m in user.methods}
        assert {"login", "logout"} <= method_names
        login = next(m for m in user.methods if m.name == "login")
        assert login.return_type == "bool"
        assert login.parameters[0].name == "password"
        assert login.parameters[0].type == "String"

    def test_parse_plantuml_visibility(self, parser):
        model = parser.build_class_model(_read("simple_domain.puml"))
        user = next(c for c in model.classes if c.name == "User")
        vis = {a.name: a.visibility for a in user.attributes}
        assert vis["id"] == Visibility.PUBLIC
        assert vis["passwordHash"] == Visibility.PRIVATE

    def test_parse_plantuml_protected_and_abstract(self, parser):
        model = parser.build_class_model(_read("complex_hierarchy.puml"))
        animal = next(c for c in model.classes if c.name == "Animal")
        assert animal.is_abstract is True
        name_attr = next(a for a in animal.attributes if a.name == "name")
        assert name_attr.visibility == Visibility.PROTECTED
        make_sound = next(m for m in animal.methods if m.name == "makeSound")
        assert make_sound.is_abstract is True


class TestPlantUMLInterfacesAndEnums:
    def test_parse_plantuml_interfaces(self, parser):
        model = parser.build_class_model(_read("design_patterns.puml"))
        assert {i.name for i in model.interfaces} == {"PaymentStrategy"}
        iface = model.interfaces[0]
        assert iface.methods[0].name == "pay"

    def test_parse_plantuml_enumerations(self, parser):
        model = parser.build_class_model(_read("ecommerce_full.puml"))
        assert len(model.enumerations) == 1
        status = model.enumerations[0]
        assert status.name == "OrderStatus"
        assert status.values == ["PENDING", "PAID", "SHIPPED", "DELIVERED", "CANCELLED"]


class TestPlantUMLRelationships:
    def test_parse_plantuml_inheritance(self, parser):
        model = parser.build_class_model(_read("complex_hierarchy.puml"))
        inh = {(r.source, r.target) for r in model.relationships if r.relationship_type == "inheritance"}
        assert ("Mammal", "Animal") in inh
        assert ("Puppy", "Dog") in inh

    def test_parse_plantuml_implementation(self, parser):
        model = parser.build_class_model(_read("design_patterns.puml"))
        impl = {(r.source, r.target) for r in model.relationships if r.relationship_type == "implementation"}
        assert ("CreditCardStrategy", "PaymentStrategy") in impl
        assert ("PayPalStrategy", "PaymentStrategy") in impl

    def test_parse_plantuml_composition_and_aggregation(self, parser):
        model = parser.build_class_model(_read("ecommerce_full.puml"))
        types = {(r.source, r.target): r.relationship_type for r in model.relationships}
        assert types[("Order", "OrderItem")] == "composition"
        assert types[("ShoppingCart", "Product")] == "aggregation"

    def test_parse_plantuml_multiplicity(self, parser):
        model = parser.build_class_model(_read("simple_domain.puml"))
        rel = next(r for r in model.relationships if (r.source, r.target) == ("User", "Order"))
        assert rel.multiplicity is not None
        assert rel.multiplicity.source_end == "1"
        assert rel.multiplicity.target_end == "0..*"


class TestPlantUMLPackages:
    def test_parse_plantuml_packages(self, parser):
        text = """@startuml
package domain {
  class Customer {
    +id: int
  }
  class Invoice {
    +number: String
  }
}
Customer --> Invoice
@enduml
"""
        model = parser.build_class_model(text)
        assert len(model.packages) == 1
        pkg = model.packages[0]
        assert pkg.name == "domain"
        assert set(pkg.class_names) == {"Customer", "Invoice"}
        customer = next(c for c in model.classes if c.name == "Customer")
        assert customer.package == "domain"


class TestXMI:
    def test_parse_xmi_classes(self, parser):
        root = fromstring(_read("java_spring.xmi"))
        model = parser.build_class_model_from_xmi(root)
        names = {c.name for c in model.classes}
        assert {"BaseEntity", "User", "UserService", "JpaUserRepository"} <= names
        user = next(c for c in model.classes if c.name == "User")
        name_attr = next(a for a in user.attributes if a.name == "name")
        assert name_attr.type == "String"
        assert name_attr.visibility == Visibility.PRIVATE
        get_name = next(m for m in user.methods if m.name == "getName")
        assert get_name.return_type == "String"

    def test_parse_xmi_interfaces(self, parser):
        root = fromstring(_read("java_spring.xmi"))
        model = parser.build_class_model_from_xmi(root)
        assert {i.name for i in model.interfaces} == {"UserRepository"}
        find = model.interfaces[0].methods[0]
        assert find.name == "findById"
        assert find.return_type == "User"
        assert find.parameters[0].type == "Long"

    def test_parse_xmi_enumerations(self, parser):
        root = fromstring(_read("java_spring.xmi"))
        model = parser.build_class_model_from_xmi(root)
        assert model.enumerations[0].values == ["ADMIN", "USER"]

    def test_parse_xmi_generalization_and_realization(self, parser):
        root = fromstring(_read("java_spring.xmi"))
        model = parser.build_class_model_from_xmi(root)
        rels = {(r.source, r.target): r.relationship_type for r in model.relationships}
        assert rels[("User", "BaseEntity")] == "inheritance"
        assert rels[("JpaUserRepository", "UserRepository")] == "implementation"

    def test_parse_xmi_associations_with_multiplicity(self, parser):
        root = fromstring(_read("java_spring.xmi"))
        model = parser.build_class_model_from_xmi(root)
        assoc = next(r for r in model.relationships if (r.source, r.target) == ("UserService", "UserRepository"))
        assert assoc.relationship_type == "aggregation"
        assert assoc.multiplicity.source_end == "1"
        assert assoc.multiplicity.target_end == "0..*"


class TestComparatorStub:
    def test_class_code_comparator_stub(self, parser):
        model = parser.build_class_model(_read("simple_domain.puml"))
        comparison = DiagramCodeComparator().compare(model, StubCodeStructureProvider(), uuid4())
        assert set(comparison.diagram_only_classes) == {"User", "Order", "Product"}
        assert comparison.code_only_classes == []
        assert all(d.severity == "error" for d in comparison.discrepancies)


class TestAccuracyGoldenData:
    def test_accuracy_golden_data(self, parser):
        for name, expected in _GOLDEN_EXPECTED.items():
            content = _read(name)
            if name.endswith(".xmi"):
                model = parser.build_class_model_from_xmi(fromstring(content))
            else:
                model = parser.build_class_model(content)
            found = len(model.classes) + len(model.interfaces) + len(model.enumerations)
            accuracy = min(found, expected) / expected
            assert accuracy > 0.75, f"{name}: accuracy {accuracy:.2f} (found {found}, expected {expected})"
