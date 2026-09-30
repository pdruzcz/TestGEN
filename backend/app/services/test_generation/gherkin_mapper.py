"""Deterministic UML/GUI -> Gherkin mapping — Epic 3, Story 3.11 (AC-2..5).

Pure-Python rules that turn reconstructed :class:`UserFlow` objects (with their
ordered ``FlowStep`` rows) into :class:`GherkinFeatureModel` structures:

- ``FlowStep.actor``           -> ``Given`` context (deduplicated, at scenario start)
- ``FlowStep.action``          -> ``When`` step
- ``FlowStep.target_element``  -> ``And w elemencie "..."`` (when present)
- ``FlowStep.expected_result`` -> ``Then`` step

Cross-scenario rules:

- ``include`` use-case relations (``FlowStep.meta.relation_type == "include"``)
  are lifted into a ``Background:`` from the *relation*, not from a heuristic
  common-Given prefix (AC-2). The legacy common-prefix extraction remains as a
  fallback for flows that carry no relation metadata.
- ``extend`` use-case relations (``FlowStep.meta.relation_type == "extend"``)
  render as a ``Scenario Outline`` whose ``Examples`` table is sourced from
  ``FlowStep.meta.parameters`` (the extend guard/preconditions) (AC-3).
- activity decision branches (``FlowStep.meta.branch_label``) split a single
  flow into separate ``Scenario`` blocks (AC-4); distinct flows remain distinct
  ``Scenario`` blocks regardless.

When a ``FlowStep`` carries no ``meta`` (or ``relation_type == "none"`` and no
``branch_label``) the mapper behaves exactly like the original happy-path /
heuristic implementation — every legacy test stays green.
"""

from types import SimpleNamespace

from app.services.test_generation.gherkin_models import (
    AND,
    GIVEN,
    THEN,
    WHEN,
    GherkinFeatureModel,
    GherkinScenario,
    GherkinStep,
)


def _clean(text: str | None) -> str:
    return (text or "").strip()


# --- FlowStep metadata helpers (Story 3-11-domknięcie, AC1) ----------------


def _meta(fs) -> dict:
    """Read UML relation/decision metadata from a step.

    Works with both the ORM ``FlowStep`` (``.meta`` column) and the API
    ``FlowStepOut`` (``.metadata``); steps without the attribute yield ``{}``.
    """
    raw = getattr(fs, "meta", None)
    if raw is None:
        raw = getattr(fs, "metadata", None)
    return raw or {}


def _relation_type(fs) -> str:
    return _meta(fs).get("relation_type") or "none"


def _parameters(fs) -> list[str]:
    return list(_meta(fs).get("parameters") or [])


def _branch_label(fs) -> str | None:
    label = _meta(fs).get("branch_label")
    return label or None


def _dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def flow_to_scenario(flow) -> GherkinScenario:
    """Map a single ``UserFlow`` to one happy-path :class:`GherkinScenario`."""
    steps: list[GherkinStep] = []
    seen_actors: set[str] = set()

    for fs in flow.flow_steps:
        actor = _clean(fs.actor)
        if actor and actor not in seen_actors:
            seen_actors.add(actor)
            steps.append(GherkinStep(GIVEN, f"{actor} rozpoczyna interakcję"))

        action = _clean(fs.action)
        if action:
            steps.append(GherkinStep(WHEN, action))

        target = _clean(fs.target_element)
        if target:
            steps.append(GherkinStep(AND, f'w elemencie "{target}"'))

        expected = _clean(fs.expected_result)
        if expected:
            steps.append(GherkinStep(THEN, expected))

    return GherkinScenario(name=_clean(flow.name) or "Scenariusz", steps=steps)


def flow_to_scenarios(flow) -> list[GherkinScenario]:
    """Map a flow to one or more scenarios (AC-3 extend outline, AC-4 branches).

    Decision branches (``metadata.branch_label``) split a single flow into
    separate ``Scenario`` blocks; an ``extend`` variant
    (``metadata.relation_type == "extend"``) is rendered as a ``Scenario
    Outline`` with an ``Examples`` table sourced from ``metadata.parameters``.

    A flow without any relation/branch metadata collapses to the legacy
    single happy-path scenario (:func:`flow_to_scenario`).
    """
    steps = list(getattr(flow, "flow_steps", []) or [])
    branch_labels = [_branch_label(fs) for fs in steps]

    if not any(branch_labels):
        scenarios = [flow_to_scenario(flow)]
    else:
        # Group consecutive steps by branch_label (None = shared/main path).
        groups: list[tuple[str | None, list]] = []
        for fs, bl in zip(steps, branch_labels, strict=True):
            if groups and groups[-1][0] == bl:
                groups[-1][1].append(fs)
            else:
                groups.append((bl, [fs]))
        scenarios = []
        for bl, group_steps in groups:
            sub_flow = SimpleNamespace(name=flow.name, flow_steps=group_steps)
            scenario = flow_to_scenario(sub_flow)
            if bl:
                scenario.name = f"{_clean(flow.name)} — {bl}" or scenario.name
            scenarios.append(scenario)

    # AC-3: extend variant -> Scenario Outline with Examples from parameters.
    extend_params: list[str] = []
    has_extend = False
    for fs in steps:
        if _relation_type(fs) == "extend":
            has_extend = True
            extend_params.extend(_parameters(fs))
    if has_extend:
        rows = [[p] for p in _dedup(extend_params)] if extend_params else [["(rozszerzenie)"]]
        for scenario in scenarios:
            scenario.examples_headers = ["warunek"]
            scenario.examples_rows = rows
    return scenarios


def _leading_given(scenario: GherkinScenario) -> list[GherkinStep]:
    leading: list[GherkinStep] = []
    for step in scenario.steps:
        if step.keyword == GIVEN:
            leading.append(step)
        else:
            break
    return leading


def extract_background(scenarios: list[GherkinScenario]) -> list[GherkinStep]:
    """Return the ``Given`` steps shared (as a common prefix) by every scenario.

    The shared steps are removed from each scenario in place so they can be
    rendered once in a ``Background:`` block. This is the legacy heuristic
    fallback (AC-2) used when no ``include`` relation metadata is present.
    """
    if len(scenarios) < 2:
        return []

    prefixes = [_leading_given(s) for s in scenarios]
    common: list[GherkinStep] = []
    for tuple_of_steps in zip(*prefixes, strict=False):
        first = tuple_of_steps[0]
        if all(s.text == first.text for s in tuple_of_steps):
            common.append(first)
        else:
            break

    if not common:
        return []

    count = len(common)
    for scenario in scenarios:
        scenario.steps = scenario.steps[count:]
    return common


def _extract_include_background(flows: list) -> tuple[list[GherkinStep], list]:
    """Pull ``include``-relation steps out of every flow as Background Given (AC-2).

    Returns the deduplicated Background steps plus a copy of ``flows`` with the
    include steps removed (so they are not repeated inside each scenario). When
    no ``include`` relation is present this is a no-op — empty Background and
    the original ``flows`` returned untouched, so the legacy heuristic applies.
    """
    background: list[GherkinStep] = []
    seen: set[str] = set()
    cleaned: list = []
    any_include = False
    for flow in flows:
        kept: list = []
        for fs in getattr(flow, "flow_steps", []) or []:
            if _relation_type(fs) == "include":
                any_include = True
                text = _clean(getattr(fs, "action", None)) or _clean(getattr(fs, "actor", None))
                if text and text not in seen:
                    seen.add(text)
                    background.append(GherkinStep(GIVEN, text))
            else:
                kept.append(fs)
        cleaned.append(SimpleNamespace(name=getattr(flow, "name", ""), flow_steps=kept))
    if not any_include:
        return [], flows
    return background, cleaned


def map_flows_to_feature(flows: list, feature_name: str | None = None) -> GherkinFeatureModel:
    """Map one or more flows into a single feature (AC-2, AC-3, AC-4, AC-5)."""
    # AC-2: relation-based Background (include) takes precedence over the legacy
    # heuristic common-Given-prefix whenever include metadata is present.
    include_background, mapped_flows = _extract_include_background(flows)

    scenarios: list[GherkinScenario] = []
    for flow in mapped_flows:
        scenarios.extend(flow_to_scenarios(flow))

    # AC-2: relation-based Background (include) wins; the legacy common-Given
    # prefix heuristic applies only when no include metadata is present.
    background = include_background or extract_background(scenarios)

    name = _clean(feature_name)
    if not name:
        name = _clean(flows[0].name) if flows else "Funkcjonalność"

    return GherkinFeatureModel(
        feature_name=name,
        feature_description="Scenariusze wygenerowane z przepływów użytkownika (UML/GUI).",
        background_steps=background,
        scenarios=scenarios,
    )
