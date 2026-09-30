"""Unit tests for SequenceDiagramParser (Story 3.2) using golden fixtures."""

from pathlib import Path

import pytest
from defusedxml.ElementTree import fromstring

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.parsers.sequence import SequenceDiagramParser

FIXTURES = Path(__file__).resolve().parents[5] / "fixtures" / "uml" / "sequence"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture()
def parser() -> SequenceDiagramParser:
    return SequenceDiagramParser()


class TestPlantUMLParticipantsAndMessages:
    def test_parse_login_participants(self, parser):
        model = parser.build_sequence_model(_read("login_flow.puml"))
        aliases = {p.alias for p in model.participants}
        assert {"User", "UI", "Auth", "DB"} <= aliases
        user = next(p for p in model.participants if p.alias == "User")
        assert user.participant_type == "actor"
        assert user.name == "End User"

    def test_parse_login_messages_ordered(self, parser):
        model = parser.build_sequence_model(_read("login_flow.puml"))
        # First message is User -> UI: enter credentials (sync).
        assert model.messages[0].from_alias == "User"
        assert model.messages[0].to_alias == "UI"
        assert model.messages[0].message_type == "sync"
        # Sequence numbers are chronological.
        assert [m.sequence_number for m in model.messages] == list(
            range(len(model.messages))
        )

    def test_return_arrow_swaps_direction(self, parser):
        model = parser.build_sequence_model(_read("login_flow.puml"))
        # "DB --> Auth: user record" is an async/return-style reply.
        reply = next(m for m in model.messages if m.label == "user record")
        assert reply.from_alias == "DB"
        assert reply.to_alias == "Auth"


class TestPlantUMLFragments:
    def test_alt_fragment_two_branches(self, parser):
        model = parser.build_sequence_model(_read("login_flow.puml"))
        alts = [f for f in model.fragments if f.fragment_type == "alt"]
        assert len(alts) == 1
        assert len(alts[0].conditions) == 2
        labels = [c.label for c in alts[0].conditions]
        assert "valid credentials" in labels
        assert "invalid credentials" in labels

    def test_loop_fragment(self, parser):
        model = parser.build_sequence_model(_read("order_processing.puml"))
        loops = [f for f in model.fragments if f.fragment_type == "loop"]
        assert len(loops) == 1
        assert loops[0].message_indices  # contains the reserve-stock messages

    def test_opt_fragment(self, parser):
        model = parser.build_sequence_model(_read("user_registration.puml"))
        opts = [f for f in model.fragments if f.fragment_type == "opt"]
        assert len(opts) == 1
        assert opts[0].conditions[0].label == "email verification enabled"

    def test_nested_fragments(self, parser):
        model = parser.build_sequence_model(_read("complex_nested.puml"))
        types = {f.fragment_type for f in model.fragments}
        assert {"loop", "alt"} <= types


class TestReconstructTestPaths:
    def test_happy_path_excludes_second_alt_branch(self, parser):
        model = parser.build_sequence_model(_read("login_flow.puml"))
        happy = next(p for p in model.test_paths if p.path_type == "happy")
        labels = [s.label for s in happy.steps]
        assert "200 token" in labels
        assert "401 unauthorized" not in labels
        assert happy.initiating_actor == "User"

    def test_alternative_path_generated(self, parser):
        model = parser.build_sequence_model(_read("login_flow.puml"))
        alts = [p for p in model.test_paths if p.path_type == "alternative"]
        assert len(alts) == 1
        labels = [s.label for s in alts[0].steps]
        assert "401 unauthorized" in labels
        assert "200 token" not in labels
        assert alts[0].preconditions == ["invalid credentials"]

    def test_iterative_path_for_loop(self, parser):
        model = parser.build_sequence_model(_read("order_processing.puml"))
        iters = [p for p in model.test_paths if p.path_type == "iterative"]
        assert len(iters) == 1
        assert iters[0].steps


class TestXMI:
    def test_parse_xmi_lifelines(self, parser):
        model = parser.build_sequence_model_from_xmi(
            fromstring(_read("api_integration.xmi"))
        )
        names = {p.name for p in model.participants}
        assert {"Client", "Gateway", "Backend"} <= names

    def test_parse_xmi_messages_resolve_lifelines(self, parser):
        model = parser.build_sequence_model_from_xmi(
            fromstring(_read("api_integration.xmi"))
        )
        assert len(model.messages) == 4
        first = model.messages[0]
        # sendRequest: Client -> Gateway, resolved via occurrence → lifeline.
        assert first.from_alias == "ll_client"
        assert first.to_alias == "ll_gateway"
        assert first.label == "sendRequest"
        reply = next(m for m in model.messages if m.label == "okResponse")
        assert reply.message_type == "return"

    def test_parse_xmi_combined_fragment(self, parser):
        model = parser.build_sequence_model_from_xmi(
            fromstring(_read("api_integration.xmi"))
        )
        alts = [f for f in model.fragments if f.fragment_type == "alt"]
        assert len(alts) == 1
        labels = [c.label for c in alts[0].conditions]
        assert "backend available" in labels
        assert "backend error" in labels

    def test_parse_xmi_returns_sequence_type(self, parser):
        parsed = parser.parse_xmi(fromstring(_read("api_integration.xmi")))
        assert parsed.diagram_type == DiagramType.SEQUENCE


_GOLDEN_EXPECTED = {
    "login_flow.puml": {"participants": 4, "messages": 8},
    "order_processing.puml": {"participants": 4, "messages": 10},
    "user_registration.puml": {"participants": 4, "messages": 7},
    "complex_nested.puml": {"participants": 4, "messages": 6},
    "api_integration.xmi": {"participants": 3, "messages": 4},
}


class TestAccuracyGoldenData:
    """AC7: element identification accuracy > 75% across the 5 golden samples."""

    def test_accuracy_above_threshold(self, parser):
        total_expected = 0
        total_found = 0
        for name, expected in _GOLDEN_EXPECTED.items():
            if name.endswith(".xmi"):
                model = parser.build_sequence_model_from_xmi(fromstring(_read(name)))
            else:
                model = parser.build_sequence_model(_read(name))
            exp = expected["participants"] + expected["messages"]
            found = min(len(model.participants), expected["participants"]) + min(
                len(model.messages), expected["messages"]
            )
            total_expected += exp
            total_found += found
        accuracy = total_found / total_expected
        assert accuracy > 0.75, f"accuracy={accuracy:.2%}"
