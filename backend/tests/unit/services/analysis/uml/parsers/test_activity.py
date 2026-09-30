"""Unit tests for ActivityDiagramParser + ActivityPathAnalyzer (Story 3.5).

Covers PlantUML and XMI extraction, path coverage (linear / decision / fork /
nested), scenario generation, validation warnings, graceful degradation and a
performance bound on a 50-node diagram.
"""

import time
from pathlib import Path

import pytest
from defusedxml.ElementTree import fromstring

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.models import ActivityNodeType
from app.services.analysis.uml.orchestrator import UMLParserOrchestrator
from app.services.analysis.uml.parsers.activity import (
    ActivityDiagramParser,
    is_activity_diagram,
)
from app.services.analysis.uml.parsers.activity_path_analyzer import ActivityPathAnalyzer

FIXTURES = Path(__file__).resolve().parents[5] / "fixtures" / "uml" / "activity"

# Expected ACTION-node counts per golden fixture (accuracy baseline).
_GOLDEN_ACTIONS = {
    "login_flow": 6,
    "order_processing": 8,
    "user_registration": 6,
    "refund_process": 10,
    "multi_lane_approval": 9,
}


@pytest.fixture()
def parser() -> ActivityDiagramParser:
    return ActivityDiagramParser()


@pytest.fixture()
def orchestrator() -> UMLParserOrchestrator:
    return UMLParserOrchestrator()


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestPlantUMLNodes:
    def test_start_and_stop(self, parser):
        model = parser.build_activity_model("@startuml\nstart\n:Akcja;\nstop\n@enduml")
        types = [n.node_type for n in model.nodes]
        assert ActivityNodeType.START in types
        assert ActivityNodeType.STOP in types
        assert ActivityNodeType.ACTION in types

    def test_actions_extracted(self, parser):
        model = parser.build_activity_model(_read("login_flow.puml"))
        names = {n.name for n in model.nodes if n.node_type == ActivityNodeType.ACTION}
        assert "Utwórz sesję" in names
        assert "Pokaż komunikat błędu" in names

    def test_minimal_diagram(self, parser):
        model = parser.build_activity_model("@startuml\nstart\nstop\n@enduml")
        assert len(model.nodes) == 2
        assert model.edges  # start → stop

    def test_multiple_end_nodes(self, parser):
        text = (
            "@startuml\nstart\nif (x?) then (tak)\n:A;\nstop\nelse (nie)\n:B;\nstop\nendif\n@enduml"
        )
        model = parser.build_activity_model(text)
        stops = [n for n in model.nodes if n.node_type == ActivityNodeType.STOP]
        assert len(stops) == 2


class TestPlantUMLDecisions:
    def test_decision_with_guards(self, parser):
        model = parser.build_activity_model(_read("login_flow.puml"))
        decisions = [n for n in model.nodes if n.node_type == ActivityNodeType.DECISION]
        assert len(decisions) == 1
        guards = {e.guard for e in model.edges if e.guard}
        assert "tak" in guards
        assert "nie" in guards

    def test_nested_decisions(self, parser):
        model = parser.build_activity_model(_read("user_registration.puml"))
        decisions = [n for n in model.nodes if n.node_type == ActivityNodeType.DECISION]
        assert len(decisions) == 2


class TestPlantUMLForkJoin:
    def test_fork_and_join(self, parser):
        model = parser.build_activity_model(_read("refund_process.puml"))
        assert any(n.node_type == ActivityNodeType.FORK for n in model.nodes)
        assert any(n.node_type == ActivityNodeType.JOIN for n in model.nodes)


class TestPlantUMLSwimlanes:
    def test_swimlanes_extracted(self, parser):
        model = parser.build_activity_model(_read("order_processing.puml"))
        names = {s.name for s in model.swimlanes}
        assert {"Klient", "System", "Płatności"} <= names

    def test_nodes_assigned_to_lanes(self, parser):
        model = parser.build_activity_model(_read("multi_lane_approval.puml"))
        lane_of = {n.id: n.swimlane for n in model.nodes}
        assert any(v == "HR" for v in lane_of.values())


class TestPathCoverage:
    def test_linear_single_path(self):
        parser = ActivityDiagramParser()
        model = parser.build_activity_model("@startuml\nstart\n:A;\n:B;\nstop\n@enduml")
        paths = ActivityPathAnalyzer().find_all_paths(model)
        assert len(paths) == 1

    def test_single_decision_two_paths(self, parser):
        model = parser.build_activity_model(_read("login_flow.puml"))
        paths = ActivityPathAnalyzer().find_all_paths(model)
        assert len(paths) == 2

    def test_fork_paths(self, parser):
        model = parser.build_activity_model(_read("refund_process.puml"))
        paths = ActivityPathAnalyzer().find_all_paths(model)
        # 3 parallel branches times 2 decision outcomes.
        assert len(paths) >= 4

    def test_nested_decisions_paths(self, parser):
        model = parser.build_activity_model(_read("user_registration.puml"))
        paths = ActivityPathAnalyzer().find_all_paths(model)
        assert len(paths) >= 3


class TestScenarioGeneration:
    def test_positive_and_negative(self, parser):
        model = parser.build_activity_model(_read("login_flow.puml"))
        kinds = {s.scenario_type for s in model.scenarios}
        assert "main" in kinds
        assert "alternative" in kinds

    def test_steps_are_actions(self, parser):
        model = parser.build_activity_model(_read("login_flow.puml"))
        for scenario in model.scenarios:
            for step in scenario.steps:
                assert step.node_type == ActivityNodeType.ACTION


class TestValidation:
    def test_missing_end_node_warns(self, parser):
        model = parser.build_activity_model("@startuml\nstart\n:A;\n@enduml")
        assert any("stop" in w.lower() or "końc" in w.lower() for w in model.warnings)

    def test_missing_start_warns(self, parser):
        model = parser.build_activity_model("@startuml\n:A;\nstop\n@enduml")
        assert any("start" in w.lower() for w in model.warnings)

    def test_valid_diagram_no_warnings(self, parser):
        model = parser.build_activity_model(_read("login_flow.puml"))
        assert model.warnings == []


class TestGracefulDegradation:
    def test_garbled_input_returns_partial(self, parser):
        text = "@startuml\nstart\n:Akcja;\n???garbage###\nblah blah\nstop\n@enduml"
        model = parser.build_activity_model(text)
        assert any(n.node_type == ActivityNodeType.ACTION for n in model.nodes)
        assert any(n.node_type == ActivityNodeType.STOP for n in model.nodes)


class TestXMI:
    def test_xmi_nodes_and_edges(self, parser):
        model = parser.build_activity_model_from_xmi(fromstring(_read("login_flow.xmi")))
        assert any(n.node_type == ActivityNodeType.START for n in model.nodes)
        assert any(n.node_type == ActivityNodeType.DECISION for n in model.nodes)
        assert len(model.edges) == 9

    def test_xmi_swimlanes(self, parser):
        model = parser.build_activity_model_from_xmi(fromstring(_read("login_flow.xmi")))
        names = {s.name for s in model.swimlanes}
        assert {"Użytkownik", "System"} <= names

    def test_xmi_guards_and_paths(self, parser):
        model = parser.build_activity_model_from_xmi(fromstring(_read("login_flow.xmi")))
        guards = {e.guard for e in model.edges if e.guard}
        assert {"tak", "nie"} <= guards
        assert len(model.scenarios) == 2


class TestOrchestratorRouting:
    def test_is_activity_helper(self):
        assert is_activity_diagram(_read("login_flow.puml")) is True
        assert is_activity_diagram("@startuml\nAlice -> Bob: hi\n@enduml") is False

    @pytest.mark.parametrize("name", list(_GOLDEN_ACTIONS))
    def test_plantuml_routes_to_activity(self, orchestrator, name):
        assert orchestrator.detect_diagram_type(_read(f"{name}.puml")) == DiagramType.ACTIVITY

    def test_xmi_routes_to_activity(self, orchestrator):
        assert orchestrator.detect_diagram_type(_read("login_flow.xmi")) == DiagramType.ACTIVITY

    def test_parse_content_plantuml(self, orchestrator):
        from app.models.uml_diagram import UMLFormat

        parsed = orchestrator._parse_content(_read("login_flow.puml"), UMLFormat.PLANTUML)
        assert parsed.diagram_type == DiagramType.ACTIVITY
        assert parsed.elements
        assert parsed.flows

    def test_parse_content_xmi(self, orchestrator):
        from app.models.uml_diagram import UMLFormat

        parsed = orchestrator._parse_content(_read("login_flow.xmi"), UMLFormat.XMI)
        assert parsed.diagram_type == DiagramType.ACTIVITY


class TestAccuracyGoldenData:
    @pytest.mark.parametrize("name,expected", list(_GOLDEN_ACTIONS.items()))
    def test_action_accuracy(self, parser, name, expected):
        model = parser.build_activity_model(_read(f"{name}.puml"))
        found = sum(1 for n in model.nodes if n.node_type == ActivityNodeType.ACTION)
        accuracy = min(found, expected) / expected
        assert accuracy > 0.75, f"{name}: {found}/{expected}"


class TestPerformance:
    def test_50_node_diagram_under_5s(self, parser):
        lines = ["@startuml", "start"]
        for idx in range(50):
            lines.append(f":Akcja {idx};")
        lines += ["stop", "@enduml"]
        text = "\n".join(lines)
        began = time.perf_counter()
        model = parser.build_activity_model(text)
        elapsed = time.perf_counter() - began
        assert elapsed < 5.0
        assert len(model.nodes) >= 50
