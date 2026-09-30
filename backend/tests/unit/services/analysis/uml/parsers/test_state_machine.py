"""Unit tests for StateMachineParser + StateCoverageAnalyzer (Story 3.6).

Covers PlantUML and XMI extraction, composite states, transition/state/path
coverage, negative transitions, validation warnings, graceful degradation and a
performance bound on a 30-state diagram.
"""

import time
from pathlib import Path

import pytest
from defusedxml.ElementTree import fromstring

from app.models.uml_diagram import DiagramType, UMLFormat
from app.services.analysis.uml.orchestrator import UMLParserOrchestrator
from app.services.analysis.uml.parsers.state_coverage_analyzer import (
    StateCoverageAnalyzer,
)
from app.services.analysis.uml.parsers.state_machine import (
    StateMachineParser,
    is_state_diagram,
)

FIXTURES = Path(__file__).resolve().parents[5] / "fixtures" / "uml" / "state_machine"

# Expected real-state counts per golden fixture (accuracy baseline).
_GOLDEN_STATES = {
    "order_lifecycle": 5,
    "user_account_states": 4,
    "payment_processing": 5,
    "document_workflow": 5,
    "composite_state_example": 5,
}


@pytest.fixture()
def parser() -> StateMachineParser:
    return StateMachineParser()


@pytest.fixture()
def orchestrator() -> UMLParserOrchestrator:
    return UMLParserOrchestrator()


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _real_states(model):
    return [s for s in model.states if not s.is_initial and not s.is_final]


class TestPlantUMLStates:
    def test_initial_and_final(self, parser):
        model = parser.build_state_model(_read("order_lifecycle.puml"))
        assert model.initial_state_id is not None
        assert model.final_state_ids
        assert any(s.is_initial for s in model.states)
        assert any(s.is_final for s in model.states)

    def test_states_extracted(self, parser):
        model = parser.build_state_model(_read("order_lifecycle.puml"))
        names = {s.name for s in _real_states(model)}
        assert {"Nowe", "Oplacone", "Wyslane", "Dostarczone", "Anulowane"} <= names

    def test_entry_do_exit_actions(self, parser):
        model = parser.build_state_model(_read("user_account_states.puml"))
        by_name = {s.name: s for s in model.states}
        assert by_name["Niezweryfikowane"].entry_action == "wyslij_email"
        assert by_name["Aktywne"].do_action == "monitoruj_sesje"
        assert by_name["Usuniete"].entry_action == "wyczysc_dane"

    def test_minimal_machine(self, parser):
        model = parser.build_state_model("@startuml\n[*] --> A\nA --> [*]\n@enduml")
        assert len(_real_states(model)) == 1
        assert model.transitions


class TestPlantUMLTransitions:
    def test_event_guard_action(self, parser):
        model = parser.build_state_model(_read("order_lifecycle.puml"))
        t = next(
            t
            for t in model.transitions
            if t.event == "oplac"
        )
        assert t.guard == "srodki_dostepne"
        assert t.action == "zarezerwuj"

    def test_guards_extracted(self, parser):
        model = parser.build_state_model(_read("payment_processing.puml"))
        guards = {t.guard for t in model.transitions if t.guard}
        assert {"limit_ok", "brak_srodkow"} <= guards


class TestCompositeStates:
    def test_composite_with_substates(self, parser):
        model = parser.build_state_model(_read("composite_state_example.puml"))
        assert len(model.composite_states) == 1
        composite = model.composite_states[0]
        assert composite.name == "Polaczony"
        child_names = {
            s.name for s in model.states if s.parent_state_id == composite.id
        }
        assert {"Bezczynny", "Przetwarzanie", "Blad"} <= child_names

    def test_internal_transitions(self, parser):
        model = parser.build_state_model(_read("composite_state_example.puml"))
        composite = model.composite_states[0]
        assert composite.internal_transition_ids


class TestTransitionCoverage:
    def test_each_transition_has_scenario(self, parser):
        model = parser.build_state_model(_read("document_workflow.puml"))
        tc = [s for s in model.scenarios if s.scenario_type == "transition"]
        assert len(tc) == len(model.transitions)

    def test_scenario_has_full_tuple(self, parser):
        model = parser.build_state_model(_read("order_lifecycle.puml"))
        scenario = next(
            s for s in model.scenarios if s.scenario_type == "transition" and s.event == "oplac"
        )
        assert scenario.source_state == "Nowe"
        assert scenario.target_state == "Oplacone"
        assert scenario.guard == "srodki_dostepne"
        assert scenario.action == "zarezerwuj"


class TestStateCoverage:
    def test_each_state_has_scenario(self, parser):
        model = parser.build_state_model(_read("order_lifecycle.puml"))
        sc = [s for s in model.scenarios if s.scenario_type == "state"]
        assert len(sc) == len(_real_states(model))

    def test_state_scenario_has_path(self, parser):
        model = parser.build_state_model(_read("order_lifecycle.puml"))
        scenario = next(
            s for s in model.scenarios if s.scenario_type == "state" and s.target_state == "Wyslane"
        )
        assert scenario.steps  # reachable via a path from initial


class TestPathScenarios:
    def test_simple_machine_single_path(self, parser):
        model = parser.build_state_model(
            "@startuml\n[*] --> A\nA --> B : go\nB --> [*]\n@enduml"
        )
        paths = [s for s in model.scenarios if s.scenario_type == "path"]
        assert len(paths) == 1

    def test_branching_multiple_paths(self, parser):
        model = parser.build_state_model(_read("order_lifecycle.puml"))
        paths = [s for s in model.scenarios if s.scenario_type == "path"]
        assert len(paths) >= 2


class TestNegativeTransitions:
    def test_negative_scenarios_generated(self, parser):
        model = parser.build_state_model(_read("document_workflow.puml"))
        negatives = [s for s in model.scenarios if s.is_negative]
        assert negatives
        assert all(s.scenario_type == "negative" for s in negatives)

    def test_negative_event_not_valid_in_state(self, parser):
        analyzer = StateCoverageAnalyzer()
        model = parser.build_state_model(_read("order_lifecycle.puml"))
        negatives = analyzer.negative_transitions(model)
        # "wyslij" is only valid from Oplacone — invalid from Nowe.
        assert any(
            s.source_state == "Nowe" and s.event == "wyslij" for s in negatives
        )


class TestValidation:
    def test_missing_initial_warns(self, parser):
        model = parser.build_state_model("@startuml\nA --> B : go\nB --> [*]\n@enduml")
        assert any("początkow" in w.lower() for w in model.warnings)

    def test_missing_final_warns(self, parser):
        model = parser.build_state_model("@startuml\n[*] --> A\nA --> B : go\n@enduml")
        assert any("końc" in w.lower() for w in model.warnings)

    def test_unreachable_state_warns(self, parser):
        text = "@startuml\n[*] --> A\nA --> [*]\nB --> C : x\n@enduml"
        model = parser.build_state_model(text)
        assert any("nieosiągaln" in w.lower() for w in model.warnings)

    def test_valid_diagram_no_warnings(self, parser):
        model = parser.build_state_model(_read("order_lifecycle.puml"))
        assert model.warnings == []


class TestGracefulDegradation:
    def test_garbled_input_returns_partial(self, parser):
        text = "@startuml\n[*] --> A\n???garbage###\nA --> [*]\n@enduml"
        model = parser.build_state_model(text)
        assert _real_states(model)
        assert model.transitions


class TestXMI:
    def test_xmi_states_and_transitions(self, parser):
        model = parser.build_state_model_from_xmi(fromstring(_read("order_lifecycle.xmi")))
        names = {s.name for s in _real_states(model)}
        assert {"Nowe", "Oplacone", "Wyslane"} <= names
        assert len(model.transitions) == 8

    def test_xmi_initial_final(self, parser):
        model = parser.build_state_model_from_xmi(fromstring(_read("order_lifecycle.xmi")))
        assert model.initial_state_id is not None
        assert model.final_state_ids

    def test_xmi_trigger_guard_effect(self, parser):
        model = parser.build_state_model_from_xmi(fromstring(_read("order_lifecycle.xmi")))
        t = next(t for t in model.transitions if t.event == "oplac")
        assert t.guard == "srodki_dostepne"
        assert t.action == "zarezerwuj"


class TestOrchestratorRouting:
    def test_is_state_helper(self):
        assert is_state_diagram(_read("order_lifecycle.puml")) is True
        assert is_state_diagram("@startuml\nAlice -> Bob: hi\n@enduml") is False

    @pytest.mark.parametrize("name", list(_GOLDEN_STATES))
    def test_plantuml_routes_to_state(self, orchestrator, name):
        assert (
            orchestrator.detect_diagram_type(_read(f"{name}.puml"))
            == DiagramType.STATE_MACHINE
        )

    def test_xmi_routes_to_state(self, orchestrator):
        assert (
            orchestrator.detect_diagram_type(_read("order_lifecycle.xmi"))
            == DiagramType.STATE_MACHINE
        )

    def test_parse_content_plantuml(self, orchestrator):
        parsed = orchestrator._parse_content(
            _read("order_lifecycle.puml"), UMLFormat.PLANTUML
        )
        assert parsed.diagram_type == DiagramType.STATE_MACHINE
        assert parsed.elements
        assert parsed.relationships
        assert parsed.flows

    def test_parse_content_xmi(self, orchestrator):
        parsed = orchestrator._parse_content(
            _read("order_lifecycle.xmi"), UMLFormat.XMI
        )
        assert parsed.diagram_type == DiagramType.STATE_MACHINE


class TestAccuracyGoldenData:
    @pytest.mark.parametrize("name,expected", list(_GOLDEN_STATES.items()))
    def test_state_accuracy(self, parser, name, expected):
        model = parser.build_state_model(_read(f"{name}.puml"))
        found = len(_real_states(model))
        accuracy = min(found, expected) / expected
        assert accuracy > 0.75, f"{name}: {found}/{expected}"


class TestPerformance:
    def test_30_state_diagram_under_5s(self, parser):
        lines = ["@startuml", "[*] --> S0"]
        for idx in range(29):
            lines.append(f"S{idx} --> S{idx + 1} : ev{idx}")
        lines += ["S29 --> [*]", "@enduml"]
        text = "\n".join(lines)
        began = time.perf_counter()
        model = parser.build_state_model(text)
        elapsed = time.perf_counter() - began
        assert elapsed < 5.0
        assert len(_real_states(model)) >= 30
