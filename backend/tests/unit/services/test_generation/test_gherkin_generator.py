"""Unit tests for the Gherkin/BDD generator — Epic 3, Story 3.11.

Covers the deterministic mapper (flow -> scenario, Background extraction),
the native generator (render + validation warnings), the template rendering and
the LLM enrichment graceful-degradation path. All exercises are pure-Python; the
LLM Gateway is mocked.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services.test_generation.gherkin_generator import (
    enrich_with_llm,
    generate_native,
    render_feature,
    validate_gherkin,
)
from app.services.test_generation.gherkin_mapper import (
    extract_background,
    flow_to_scenario,
    flow_to_scenarios,
    map_flows_to_feature,
)
from app.services.test_generation.gherkin_models import (
    GIVEN,
    THEN,
    WHEN,
    GherkinScenario,
    GherkinStep,
)


def _step(action="kliknij", actor="Użytkownik", target="Przycisk", expected="widzi wynik"):
    return SimpleNamespace(
        action=action,
        actor=actor,
        target_element=target,
        expected_result=expected,
    )


def _mstep(action="kliknij", actor="Użytkownik", target="Przycisk", expected="widzi wynik", meta=None):
    """A flow step carrying UML relation/decision metadata (Story 3-11-domknięcie)."""
    return SimpleNamespace(
        action=action,
        actor=actor,
        target_element=target,
        expected_result=expected,
        meta=meta,
    )


def _flow(name="Logowanie", steps=None):
    return SimpleNamespace(name=name, flow_steps=steps if steps is not None else [_step()])


class TestFlowToScenario:
    def test_maps_actor_action_target_expected(self):
        scenario = flow_to_scenario(_flow())
        keywords = [s.keyword for s in scenario.steps]
        assert GIVEN in keywords
        assert WHEN in keywords
        assert THEN in keywords
        assert scenario.name == "Logowanie"

    def test_actor_deduplicated(self):
        flow = _flow(steps=[_step(action="a"), _step(action="b")])
        scenario = flow_to_scenario(flow)
        givens = [s for s in scenario.steps if s.keyword == GIVEN]
        assert len(givens) == 1

    def test_empty_fields_skipped(self):
        flow = _flow(steps=[_step(actor="", target="", expected="")])
        scenario = flow_to_scenario(flow)
        assert all(s.keyword == WHEN for s in scenario.steps)


class TestBackground:
    def test_common_given_lifted(self):
        s1 = GherkinScenario(name="A", steps=[GherkinStep(GIVEN, "ctx"), GherkinStep(WHEN, "x")])
        s2 = GherkinScenario(name="B", steps=[GherkinStep(GIVEN, "ctx"), GherkinStep(WHEN, "y")])
        background = extract_background([s1, s2])
        assert len(background) == 1
        assert background[0].text == "ctx"
        assert s1.steps[0].keyword == WHEN
        assert s2.steps[0].keyword == WHEN

    def test_no_common_given_returns_empty(self):
        s1 = GherkinScenario(name="A", steps=[GherkinStep(GIVEN, "a")])
        s2 = GherkinScenario(name="B", steps=[GherkinStep(GIVEN, "b")])
        assert extract_background([s1, s2]) == []

    def test_single_scenario_no_background(self):
        s1 = GherkinScenario(name="A", steps=[GherkinStep(GIVEN, "a")])
        assert extract_background([s1]) == []


class TestNativeGeneration:
    def test_generate_native_returns_model_raw_warnings(self):
        feature, raw, warnings = generate_native([_flow()], "Funkcja logowania")
        assert feature.feature_name == "Funkcja logowania"
        assert "Feature:" in raw
        assert "Scenario:" in raw
        assert warnings == []

    def test_default_feature_name_from_first_flow(self):
        feature, _, _ = generate_native([_flow(name="Rejestracja")])
        assert feature.feature_name == "Rejestracja"

    def test_render_collapses_blank_lines(self):
        feature = map_flows_to_feature([_flow()], "X")
        raw = render_feature(feature)
        assert "\n\n\n" not in raw
        assert raw.endswith("\n")


class TestValidation:
    def test_missing_feature_header_warned(self):
        feature = map_flows_to_feature([_flow()], "X")
        warnings = validate_gherkin("brak naglowka", feature)
        assert any("Feature" in w for w in warnings)

    def test_scenario_without_then_warned(self):
        scenario = GherkinScenario(name="S", steps=[GherkinStep(WHEN, "x")])
        feature = map_flows_to_feature([_flow()], "X")
        feature.scenarios = [scenario]
        warnings = validate_gherkin("Feature: X", feature)
        assert any("Then" in w for w in warnings)

    def test_clean_feature_no_warnings(self):
        feature, raw, _ = generate_native([_flow()], "X")
        assert validate_gherkin(raw, feature) == []

    def test_outline_missing_examples_warned(self):
        scenario = GherkinScenario(
            name="Outline",
            steps=[GherkinStep(WHEN, "wpisz <login>"), GherkinStep(THEN, "ok")],
            examples_headers=["login"],
            examples_rows=[],
        )
        feature = map_flows_to_feature([_flow()], "X")
        feature.scenarios = [scenario]
        warnings = validate_gherkin("Feature: X", feature)
        assert any("Examples" in w for w in warnings)


class TestLLMEnrichment:
    async def test_enrich_success_returns_llm_text(self):
        feature, raw, _ = generate_native([_flow()], "X")
        gateway = AsyncMock()
        gateway.complete = AsyncMock(
            return_value=SimpleNamespace(content="Feature: Wzbogacona\n  Scenario: S\n    Given a\n")
        )
        enriched, warnings = await enrich_with_llm(feature, raw, gateway)
        assert "Wzbogacona" in enriched
        assert warnings == []

    async def test_enrich_failure_degrades_to_native(self):
        feature, raw, _ = generate_native([_flow()], "X")
        gateway = AsyncMock()
        gateway.complete = AsyncMock(side_effect=RuntimeError("boom"))
        enriched, warnings = await enrich_with_llm(feature, raw, gateway)
        assert enriched == raw
        assert len(warnings) == 1

    async def test_enrich_invalid_response_degrades(self):
        feature, raw, _ = generate_native([_flow()], "X")
        gateway = AsyncMock()
        gateway.complete = AsyncMock(return_value=SimpleNamespace(content="brak feature"))
        enriched, warnings = await enrich_with_llm(feature, raw, gateway)
        assert enriched == raw
        assert len(warnings) == 1


class TestRelationMapping:
    """AC-2/3/4 (Story 3-11-domknięcie): include->Background, extend->Outline, decisions->Scenarios."""

    def test_include_relation_lifted_to_background(self):
        inc = _mstep(
            action="Wykonaj: Autentykacja",
            actor="User",
            target="Autentykacja",
            meta={"relation_type": "include", "parameters": []},
        )
        main = _mstep(action="Wykonaj: Zamówienie", actor="User", target="Zamówienie", expected="ok")
        feature = map_flows_to_feature([_flow("Zamówienie", [inc, main])], "Zamówienia")
        # Background sourced from the include relation (AC-2), not the heuristic prefix.
        assert feature.background_steps
        assert any("Autentykacja" in s.text for s in feature.background_steps)
        # The include step is not repeated inside the scenario.
        assert not any("Autentykacja" in s.text for sc in feature.scenarios for s in sc.steps)

    def test_extend_relation_becomes_scenario_outline(self):
        base = _mstep(action="Wykonaj: Zamówienie", actor="User", target="Zamówienie")
        ext = _mstep(
            action="Rozszerzenie: Rabat",
            actor="User",
            target="Rabat",
            expected="rabat",
            meta={"relation_type": "extend", "parameters": ["kupon aktywny"]},
        )
        feature = map_flows_to_feature([_flow("Zamówienie (rozszerzenie)", [base, ext])], "Zamówienia")
        sc = feature.scenarios[0]
        assert sc.is_outline  # AC-3
        assert sc.examples_headers == ["warunek"]
        assert ["kupon aktywny"] in sc.examples_rows

    def test_decision_branches_split_into_scenarios(self):
        ok = _mstep(action="OK", actor="User", expected="sukces", meta={"branch_label": "tak"})
        bad = _mstep(action="Błąd", actor="User", expected="błąd", meta={"branch_label": "nie"})
        feature = map_flows_to_feature([_flow("Logowanie", [ok, bad])], "Logowanie")
        names = " ".join(sc.name for sc in feature.scenarios)
        assert "tak" in names and "nie" in names  # AC-4
        assert len(feature.scenarios) == 2

    def test_metadata_attr_metadata_alias_works(self):
        # FlowStepOut exposes `.metadata` instead of ORM `.meta` — both must resolve.
        ext = SimpleNamespace(
            action="Rozszerzenie: X",
            actor="U",
            target_element="X",
            expected_result="ok",
            metadata={"relation_type": "extend", "parameters": ["g"]},
        )
        sc = flow_to_scenarios(_flow("X", [ext]))[0]
        assert sc.is_outline and sc.examples_headers == ["warunek"]

    def test_no_metadata_falls_back_to_legacy(self):
        # Steps without metadata map exactly like the original happy-path mapper.
        feature = map_flows_to_feature([_flow()], "X")
        assert len(feature.scenarios) == 1
        assert feature.scenarios[0].is_outline is False
