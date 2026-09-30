"""Unit tests for UseCaseParser (Story 3.3) using golden fixtures."""

from pathlib import Path

import pytest
from defusedxml.ElementTree import fromstring

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.parsers.use_case import UseCaseParser

FIXTURES = Path(__file__).resolve().parents[5] / "fixtures" / "uml" / "usecase"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def parser() -> UseCaseParser:
    return UseCaseParser()


class TestPlantUMLActorsAndUseCases:
    def test_parse_actors(self, parser):
        model = parser.build_use_case_model(_read("ecommerce_checkout.puml"))
        aliases = {a.alias for a in model.actors}
        assert "Customer" in aliases
        customer = next(a for a in model.actors if a.alias == "Customer")
        assert customer.name == "Klient"
        assert customer.actor_type == "primary"

    def test_parse_use_cases(self, parser):
        model = parser.build_use_case_model(_read("ecommerce_checkout.puml"))
        names = {uc.name for uc in model.use_cases}
        assert {"Przeglądaj produkty", "Płatność", "Walidacja karty"} <= names
        assert len(model.use_cases) == 5

    def test_parse_two_actors(self, parser):
        model = parser.build_use_case_model(_read("user_management.puml"))
        assert len(model.actors) == 2


class TestPlantUMLRelationships:
    def test_association(self, parser):
        model = parser.build_use_case_model(_read("ecommerce_checkout.puml"))
        assocs = [r for r in model.relationships if r.relationship_type == "association"]
        assert len(assocs) == 3
        assert all(r.source == "Customer" for r in assocs)

    def test_include(self, parser):
        model = parser.build_use_case_model(_read("ecommerce_checkout.puml"))
        incs = [r for r in model.relationships if r.relationship_type == "include"]
        assert len(incs) == 1
        assert incs[0].source == "UC3"
        assert incs[0].target == "UC4"

    def test_extend(self, parser):
        model = parser.build_use_case_model(_read("ecommerce_checkout.puml"))
        exts = [r for r in model.relationships if r.relationship_type == "extend"]
        assert len(exts) == 1
        assert exts[0].source == "UC5"
        assert exts[0].target == "UC3"

    def test_generalization(self, parser):
        model = parser.build_use_case_model(_read("user_management.puml"))
        gens = [r for r in model.relationships if r.relationship_type == "generalization"]
        assert len(gens) == 1
        assert gens[0].source == "Admin"
        assert gens[0].target == "User"

    def test_complex_relationship_mix(self, parser):
        model = parser.build_use_case_model(_read("complex_relationships.puml"))
        types = {r.relationship_type for r in model.relationships}
        assert {"generalization", "include", "extend"} <= types
        gens = [r for r in model.relationships if r.relationship_type == "generalization"]
        assert len(gens) == 2


class TestSystemBoundary:
    def test_boundary_collects_use_cases(self, parser):
        model = parser.build_use_case_model(_read("banking_system.puml"))
        assert model.system_boundary is not None
        assert model.system_boundary.name == "System bankowy"
        assert len(model.system_boundary.use_case_names) == 4

    def test_no_boundary(self, parser):
        model = parser.build_use_case_model(_read("user_management.puml"))
        assert model.system_boundary is None


class TestScenarioGeneration:
    def test_main_scenario_per_use_case(self, parser):
        model = parser.build_use_case_model(_read("ecommerce_checkout.puml"))
        mains = [s for s in model.scenarios if s.scenario_type == "main"]
        assert len(mains) == len(model.use_cases)
        payment = next(s for s in mains if s.use_case_name == "Płatność")
        assert payment.primary_actor == "Customer"

    def test_include_injects_step(self, parser):
        model = parser.build_use_case_model(_read("ecommerce_checkout.puml"))
        payment = next(
            s
            for s in model.scenarios
            if s.scenario_type == "main" and s.use_case_name == "Płatność"
        )
        targets = [step.target for step in payment.steps]
        # Included "Walidacja karty" step injected before the main payment step.
        assert "Walidacja karty" in targets
        assert targets[-1] == "Płatność"

    def test_extend_creates_alternative(self, parser):
        model = parser.build_use_case_model(_read("ecommerce_checkout.puml"))
        alts = [s for s in model.scenarios if s.scenario_type == "alternative"]
        assert len(alts) == 1
        assert alts[0].use_case_name == "Dostawa ekspresowa"


class TestXMI:
    def test_parse_xmi_actors(self, parser):
        model = parser.build_use_case_model_from_xmi(
            fromstring(_read("library_system.xmi"))
        )
        names = {a.name for a in model.actors}
        assert {"Reader", "Librarian"} <= names

    def test_parse_xmi_use_cases(self, parser):
        model = parser.build_use_case_model_from_xmi(
            fromstring(_read("library_system.xmi"))
        )
        names = {uc.name for uc in model.use_cases}
        assert {"SearchCatalog", "BorrowBook", "Authenticate"} <= names

    def test_parse_xmi_include(self, parser):
        model = parser.build_use_case_model_from_xmi(
            fromstring(_read("library_system.xmi"))
        )
        incs = [r for r in model.relationships if r.relationship_type == "include"]
        assert len(incs) == 1
        assert incs[0].source == "BorrowBook"
        assert incs[0].target == "Authenticate"

    def test_parse_xmi_associations(self, parser):
        model = parser.build_use_case_model_from_xmi(
            fromstring(_read("library_system.xmi"))
        )
        assocs = [r for r in model.relationships if r.relationship_type == "association"]
        assert len(assocs) == 2

    def test_parse_xmi_returns_use_case_type(self, parser):
        parsed = parser.parse_xmi(fromstring(_read("library_system.xmi")))
        assert parsed.diagram_type == DiagramType.USE_CASE


_GOLDEN_EXPECTED = {
    "ecommerce_checkout.puml": {"actors": 1, "use_cases": 5},
    "user_management.puml": {"actors": 2, "use_cases": 3},
    "banking_system.puml": {"actors": 2, "use_cases": 4},
    "complex_relationships.puml": {"actors": 3, "use_cases": 6},
    "library_system.xmi": {"actors": 2, "use_cases": 4},
}


class TestAccuracyGoldenData:
    """AC8: element identification accuracy > 75% across the 5 golden samples."""

    def test_accuracy_above_threshold(self, parser):
        total_expected = 0
        total_found = 0
        for name, expected in _GOLDEN_EXPECTED.items():
            if name.endswith(".xmi"):
                model = parser.build_use_case_model_from_xmi(fromstring(_read(name)))
            else:
                model = parser.build_use_case_model(_read(name))
            exp = expected["actors"] + expected["use_cases"]
            found = min(len(model.actors), expected["actors"]) + min(
                len(model.use_cases), expected["use_cases"]
            )
            total_expected += exp
            total_found += found
        accuracy = total_found / total_expected
        assert accuracy > 0.75, f"accuracy={accuracy:.2%}"
