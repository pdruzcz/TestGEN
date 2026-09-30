"""Unit tests for CrossDiagramAnalyzer — Epic 3, Story 3.7.

The pure mapping / reconstruction logic is tested with synthetic
``DiagramBundle`` objects (no DB). The golden-data tests run real fixtures
through the parser orchestrator to exercise the full native pipeline.
"""

import json
import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.analysis.cross_diagram_analyzer import (
    CrossDiagramAnalyzer,
    build_integrated_model,
    reconstruct_flows,
)
from app.services.analysis.uml.integrated_model import DiagramBundle
from app.services.analysis.uml.orchestrator import UMLParserOrchestrator

GOLDEN = Path(__file__).resolve().parents[3] / "golden_data" / "uml" / "cross_diagram"


def _seq(diagram_id: str, name: str, participants: list[str], messages: list[dict] | None = None) -> DiagramBundle:
    return DiagramBundle(
        diagram_id=diagram_id,
        diagram_type="sequence",
        name=name,
        participants=[{"name": p, "participant_type": "participant"} for p in participants],
        relationships=messages or [],
    )


def _use_case(diagram_id: str, name: str, actors: list[str], use_cases: list[str]) -> DiagramBundle:
    return DiagramBundle(
        diagram_id=diagram_id,
        diagram_type="use_case",
        name=name,
        participants=[{"name": a, "participant_type": "actor"} for a in actors],
        elements=[{"name": uc} for uc in use_cases],
    )


def _class(diagram_id: str, name: str, classes: list[str]) -> DiagramBundle:
    return DiagramBundle(
        diagram_id=diagram_id,
        diagram_type="class",
        name=name,
        elements=[{"name": c, "element_kind": "class"} for c in classes],
    )


def _activity(diagram_id: str, name: str, nodes: list[dict], edges: list[dict]) -> DiagramBundle:
    return DiagramBundle(diagram_id=diagram_id, diagram_type="activity", name=name, elements=nodes, relationships=edges)


def _state(diagram_id: str, name: str, states: list[dict], transitions: list[dict]) -> DiagramBundle:
    return DiagramBundle(
        diagram_id=diagram_id,
        diagram_type="state_machine",
        name=name,
        elements=states,
        relationships=transitions,
    )


# --- AC1 use case ↔ sequences --------------------------------------------


class TestUseCaseToSequences:
    def test_match_by_actor(self):
        uc = _use_case("uc", "uc.puml", ["Użytkownik"], ["Logowanie"])
        seq = _seq("seq", "flow.puml", ["Użytkownik", "System"])
        integ = build_integrated_model([uc, seq])
        assert integ.use_case_to_sequences == {"uc::Logowanie": ["seq"]}

    def test_match_by_name(self):
        uc = _use_case("uc", "uc.puml", ["Actor"], ["Logowanie"])
        seq = _seq("seq", "Logowanie.puml", ["Inny"])
        integ = build_integrated_model([uc, seq])
        assert "uc::Logowanie" in integ.use_case_to_sequences

    def test_no_match(self):
        uc = _use_case("uc", "uc.puml", ["A"], ["Rejestracja"])
        seq = _seq("seq", "platnosc.puml", ["B"])
        integ = build_integrated_model([uc, seq])
        assert integ.use_case_to_sequences == {}


# --- AC2 participants ↔ classes ------------------------------------------


class TestParticipantsToClasses:
    def test_exact_match(self):
        seq = _seq("seq", "s.puml", ["User", "System"])
        cls = _class("cls", "c.puml", ["User", "System"])
        integ = build_integrated_model([seq, cls])
        assert integ.participant_to_class == {"User": "User", "System": "System"}

    def test_fuzzy_match(self):
        seq = _seq("seq", "s.puml", ["UserService"])
        cls = _class("cls", "c.puml", ["UserServices"])
        integ = build_integrated_model([seq, cls])
        assert integ.participant_to_class.get("UserService") == "UserServices"


# --- AC3 use case ↔ activity ---------------------------------------------


class TestUseCaseToActivity:
    def test_match_by_swimlane(self):
        uc = _use_case("uc", "uc.puml", ["Użytkownik"], ["Logowanie"])
        act = _activity(
            "act",
            "przeplyw.puml",
            [{"id": "n1", "name": "A", "node_type": "action", "swimlane": "Użytkownik"}],
            [],
        )
        act.fragments = [{"name": "Użytkownik", "node_ids": ["n1"]}]
        integ = build_integrated_model([uc, act])
        assert integ.use_case_to_activity == {"uc::Logowanie": "act"}


# --- AC4 class ↔ state machine -------------------------------------------


class TestClassToStateMachine:
    def test_match(self):
        cls = _class("cls", "c.puml", ["User"])
        st = _state("st", "user_state.puml", [{"id": "s1", "name": "Active", "is_initial": True}], [])
        integ = build_integrated_model([cls, st])
        assert integ.class_to_state_machine == {"User": "st"}


# --- AC5 integrated model + validation -----------------------------------


class TestIntegratedModel:
    def test_full_four_types(self):
        bundles = [
            _use_case("uc", "uc.puml", ["Użytkownik"], ["Logowanie"]),
            _seq("seq", "s.puml", ["Użytkownik", "User"]),
            _class("cls", "c.puml", ["User"]),
            _state("st", "user.puml", [{"id": "s1", "name": "Active", "is_initial": True}], []),
        ]
        integ = build_integrated_model(bundles)
        assert integ.use_case_to_sequences
        assert integ.participant_to_class
        assert integ.class_to_state_machine
        assert integ.coverage_report.coverage_percentage > 0

    def test_partial_sequence_and_class(self):
        bundles = [_seq("seq", "s.puml", ["User"]), _class("cls", "c.puml", ["User"])]
        integ = build_integrated_model(bundles)
        assert integ.participant_to_class == {"User": "User"}
        assert integ.use_case_to_sequences == {}

    def test_inconsistency_actor_not_in_use_case(self):
        uc = _use_case("uc", "uc.puml", ["Admin"], ["Zarządzanie"])
        seq = _seq("seq", "s.puml", [])
        seq.participants = [{"name": "Klient", "participant_type": "actor"}]
        integ = build_integrated_model([uc, seq])
        assert any("Klient" in w for w in integ.warnings)


# --- AC6 flow reconstruction ---------------------------------------------


class TestReconstruction:
    def test_simple_activity_flow(self):
        nodes = [
            {"id": "s", "name": "", "node_type": "start"},
            {"id": "a", "name": "Zaloguj", "node_type": "action", "swimlane": "User"},
            {"id": "e", "name": "", "node_type": "stop"},
        ]
        edges = [
            {"id": "e1", "source_id": "s", "target_id": "a"},
            {"id": "e2", "source_id": "a", "target_id": "e"},
        ]
        integ = build_integrated_model([_activity("act", "login.puml", nodes, edges)])
        flows, _ = reconstruct_flows(integ)
        assert len(flows) == 1
        assert [s["action"] for s in flows[0].steps] == ["Zaloguj"]
        assert flows[0].steps[0]["actor"] == "User"

    def test_alt_fragments_produce_alternatives(self):
        nodes = [
            {"id": "s", "node_type": "start"},
            {"id": "d", "node_type": "decision"},
            {"id": "a1", "name": "OK", "node_type": "action"},
            {"id": "a2", "name": "Błąd", "node_type": "action"},
            {"id": "e", "node_type": "stop"},
        ]
        edges = [
            {"source_id": "s", "target_id": "d"},
            {"source_id": "d", "target_id": "a1", "guard": "tak"},
            {"source_id": "d", "target_id": "a2", "guard": "nie"},
            {"source_id": "a1", "target_id": "e"},
            {"source_id": "a2", "target_id": "e"},
        ]
        integ = build_integrated_model([_activity("act", "dec.puml", nodes, edges)])
        flows, _ = reconstruct_flows(integ)
        assert len(flows) == 2
        actions = sorted(s["action"] for f in flows for s in f.steps)
        assert actions == ["Błąd", "OK"]

    def test_state_lifecycle(self):
        states = [
            {"id": "i", "is_initial": True, "name": "start"},
            {"id": "s1", "name": "Active", "is_final": False},
            {"id": "f", "is_final": True, "name": "end"},
        ]
        transitions = [
            {"source_id": "i", "target_id": "s1", "event": None},
            {"source_id": "s1", "target_id": "f", "event": "close"},
        ]
        integ = build_integrated_model([_state("st", "obj.puml", states, transitions)])
        flows, _ = reconstruct_flows(integ)
        assert len(flows) == 1
        assert flows[0].steps[-1]["target_element"] == "end"

    def test_loop_does_not_hang(self):
        nodes = [
            {"id": "s", "node_type": "start"},
            {"id": "a", "name": "Powtórz", "node_type": "action"},
            {"id": "e", "node_type": "stop"},
        ]
        edges = [
            {"source_id": "s", "target_id": "a"},
            {"source_id": "a", "target_id": "a"},  # self-loop
            {"source_id": "a", "target_id": "e"},
        ]
        integ = build_integrated_model([_activity("act", "loop.puml", nodes, edges)])
        flows, _ = reconstruct_flows(integ)
        assert len(flows) == 1
        assert "powtarzalny" in (flows[0].steps[-1].get("expected_result") or "")


# --- Golden data + performance (AC10) ------------------------------------


def _bundles_from_golden() -> list[DiagramBundle]:
    orch = UMLParserOrchestrator()
    files = [
        "login_usecase.puml",
        "login_sequence.puml",
        "user_class.puml",
        "login_activity.puml",
        "user_state.puml",
    ]
    bundles: list[DiagramBundle] = []
    for i, f in enumerate(files):
        content = (GOLDEN / f).read_text(encoding="utf-8")
        fmt = orch.detect_format(content)
        pm = orch._parse_content(content, fmt)
        bundles.append(
            DiagramBundle(
                diagram_id=str(i),
                diagram_type=pm.diagram_type.value,
                name=f,
                participants=pm.participants,
                elements=pm.elements,
                relationships=pm.relationships,
                fragments=pm.fragments,
                flows=pm.flows,
            )
        )
    return bundles


class TestGoldenData:
    def test_pipeline_mappings_and_flows(self):
        expected = json.loads((GOLDEN / "expected_flows.json").read_text(encoding="utf-8"))
        bundles = _bundles_from_golden()
        integ = build_integrated_model(bundles)
        assert integ.participant_to_class == expected["mappings"]["participant_to_class"]
        assert set(integ.class_to_state_machine) == set(expected["mappings"]["class_to_state_machine_keys"])
        assert len(integ.use_case_to_sequences) >= expected["use_case_to_sequences_min"]
        assert len(integ.use_case_to_activity) >= expected["use_case_to_activity_min"]
        assert integ.coverage_report.coverage_percentage == 100.0
        flows, _ = reconstruct_flows(integ)
        assert len(flows) >= expected["min_user_flows"]

    def test_performance_under_30s(self):
        bundles = _bundles_from_golden()
        start = time.perf_counter()
        integ = build_integrated_model(bundles)
        reconstruct_flows(integ)
        assert time.perf_counter() - start < 30.0


# --- Persistence + LLM path ----------------------------------------------


class TestPersistenceAndLLM:
    @pytest.mark.asyncio
    async def test_save_user_flows_adds_rows(self):
        db = AsyncMock()
        db.add = lambda obj: None
        analyzer = CrossDiagramAnalyzer(db)
        bundles = _bundles_from_golden()
        integ = build_integrated_model(bundles)
        drafts, _ = reconstruct_flows(integ)
        out = await analyzer._save_user_flows(drafts, uuid.uuid4(), uuid.uuid4())
        assert len(out) == len(drafts)
        assert all(o.steps for o in out)

    @pytest.mark.asyncio
    async def test_llm_enrichment_fallback_on_error(self):
        db = AsyncMock()
        gateway = AsyncMock()
        gateway.complete.side_effect = RuntimeError("gateway down")
        analyzer = CrossDiagramAnalyzer(db, llm_gateway=gateway, engine_mode="llm")
        integ = build_integrated_model(_bundles_from_golden())
        drafts, _ = reconstruct_flows(integ)
        result, warnings = await analyzer._llm_enrich_flows(drafts, integ, uuid.uuid4())
        assert result == drafts  # unchanged native flows
        assert warnings == []

    @pytest.mark.asyncio
    async def test_llm_enrichment_applies_names(self):
        db = AsyncMock()
        gateway = AsyncMock()
        response = AsyncMock()
        response.content = json.dumps(
            {"names": {"0": "Logowanie użytkownika"}, "inconsistencies": ["Brak stanu błędu"]}
        )
        gateway.complete.return_value = response
        analyzer = CrossDiagramAnalyzer(db, llm_gateway=gateway, engine_mode="hybrid")
        integ = build_integrated_model(_bundles_from_golden())
        drafts, _ = reconstruct_flows(integ)
        result, warnings = await analyzer._llm_enrich_flows(drafts, integ, uuid.uuid4())
        assert result[0].name == "Logowanie użytkownika"
        assert result[0].steps[0]["source"] == "llm"
        assert warnings == ["Brak stanu błędu"]


# --- Use-case flow reconstruction (Story 3-11-domknięcie, AC1) -------------


class TestUseCaseFlowReconstruction:
    def test_include_extend_propagated_to_step_metadata(self):
        uc = DiagramBundle(
            diagram_id="uc",
            diagram_type="use_case",
            name="order.puml",
            participants=[{"name": "User", "participant_type": "actor"}],
            elements=[{"name": "Zamówienie"}, {"name": "Autentykacja"}, {"name": "Rabat"}],
            relationships=[
                {"source": "Zamówienie", "target": "Autentykacja", "relationship_type": "include"},
                {"source": "Rabat", "target": "Zamówienie", "relationship_type": "extend", "label": "kupon aktywny"},
            ],
            flows=[
                {
                    "use_case_name": "Zamówienie",
                    "primary_actor": "User",
                    "scenario_type": "main",
                    "expected_result": "ok",
                    "preconditions": [],
                    "steps": [
                        {"sequence": 1, "action": "Wykonaj: Autentykacja", "actor": "User", "target": "Autentykacja"},
                        {"sequence": 2, "action": "Wykonaj: Zamówienie", "actor": "User", "target": "Zamówienie"},
                    ],
                },
                {
                    "use_case_name": "Rabat",
                    "primary_actor": "User",
                    "scenario_type": "alternative",
                    "expected_result": "rabat",
                    "preconditions": ["kupon aktywny"],
                    "steps": [
                        {"sequence": 1, "action": "Wykonaj: Zamówienie", "actor": "User", "target": "Zamówienie"},
                        {"sequence": 2, "action": "Rozszerzenie: Rabat", "actor": "User", "target": "Rabat"},
                    ],
                },
            ],
        )
        integ = build_integrated_model([uc])
        flows, _ = reconstruct_flows(integ)

        main = next(f for f in flows if "Zamówienie" in f.name and "rozszerzenie" not in f.name)
        inc = next(s for s in main.steps if (s.get("metadata") or {}).get("relation_type") == "include")
        assert inc["target_element"] == "Autentykacja"  # AC1: include tagged

        ext = next(f for f in flows if "rozszerzenie" in f.name)
        assert any((s.get("metadata") or {}).get("relation_type") == "extend" for s in ext.steps)  # AC1: extend tagged
        assert any((s.get("metadata") or {}).get("parameters") == ["kupon aktywny"] for s in ext.steps)  # AC3 source


class TestActivityBranchLift:
    def test_decision_guard_lifted_to_branch_label(self):
        nodes = [
            {"id": "s", "node_type": "start"},
            {"id": "d", "node_type": "decision"},
            {"id": "a", "name": "OK", "node_type": "action"},
            {"id": "e", "node_type": "stop"},
        ]
        edges = [
            {"source_id": "s", "target_id": "d"},
            {"source_id": "d", "target_id": "a", "guard": "tak"},
            {"source_id": "a", "target_id": "e"},
        ]
        integ = build_integrated_model([_activity("act", "d.puml", nodes, edges)])
        flows, _ = reconstruct_flows(integ)
        ok = next(s for f in flows for s in f.steps if s["action"] == "OK")
        assert (ok.get("metadata") or {}).get("branch_label") == "tak"  # AC1/AC4: guard lifted
        assert ok.get("expected_result") is None  # no longer flattened into "[guard]" text
