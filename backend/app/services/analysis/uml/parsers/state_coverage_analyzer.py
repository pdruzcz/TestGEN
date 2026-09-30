"""StateCoverageAnalyzer — FSM coverage scenarios for state diagrams (Story 3.6).

Given a parsed :class:`StateModel`, produces test scenarios for:

* **transition coverage** — one scenario per transition (AC4),
* **state coverage** — one scenario per state, reached via shortest path (AC5),
* **paths** — sequences from the initial pseudostate to a final one (AC5),
* **negative transitions** — per state, events that trigger no transition (AC6).

Graph traversal is bounded (``_MAX_DEPTH`` / ``_MAX_PATHS`` / ``_MAX_NEGATIVE``)
so cyclic FSMs cannot produce unbounded output.
"""

from collections import deque

from app.services.analysis.uml.models import (
    StateModel,
    StateNode,
    StateScenario,
    Transition,
)

_MAX_DEPTH = 20
_MAX_PATHS = 100
_MAX_NEGATIVE = 200


class StateCoverageAnalyzer:
    """Generates FSM coverage scenarios from a :class:`StateModel`."""

    def analyze(self, model: StateModel) -> list[StateScenario]:
        scenarios: list[StateScenario] = []
        scenarios.extend(self.transition_coverage(model))
        scenarios.extend(self.state_coverage(model))
        scenarios.extend(self.path_scenarios(model))
        scenarios.extend(self.negative_transitions(model))
        return scenarios

    # --- helpers ---------------------------------------------------------

    def _name(self, model: StateModel, state_id: str) -> str:
        for state in model.states:
            if state.id == state_id:
                return state.name or state.id
        return state_id

    def _real_states(self, model: StateModel) -> list[StateNode]:
        return [s for s in model.states if not s.is_initial and not s.is_final]

    def _adjacency(self, model: StateModel) -> dict[str, list[Transition]]:
        graph: dict[str, list[Transition]] = {}
        for t in model.transitions:
            graph.setdefault(t.source_id, []).append(t)
        return graph

    def _label(self, t: Transition, model: StateModel) -> str:
        src = self._name(model, t.source_id)
        tgt = self._name(model, t.target_id)
        event = t.event or "—"
        guard = f" [{t.guard}]" if t.guard else ""
        return f"{src} --{event}{guard}--> {tgt}"

    # --- AC4: transition coverage ----------------------------------------

    def transition_coverage(self, model: StateModel) -> list[StateScenario]:
        scenarios: list[StateScenario] = []
        for i, t in enumerate(model.transitions):
            src = self._name(model, t.source_id)
            tgt = self._name(model, t.target_id)
            scenarios.append(
                StateScenario(
                    scenario_id=f"tc_{i + 1}",
                    scenario_type="transition",
                    title=f"Przejście {src} → {tgt}",
                    steps=[self._label(t, model)],
                    source_state=src,
                    event=t.event,
                    guard=t.guard,
                    action=t.action,
                    target_state=tgt,
                    expected_result=f"System przechodzi do stanu {tgt}",
                )
            )
        return scenarios

    # --- AC5: state coverage ---------------------------------------------

    def _shortest_path(
        self, model: StateModel, target_id: str
    ) -> list[Transition] | None:
        start = model.initial_state_id
        if start is None:
            return None
        if start == target_id:
            return []
        graph = self._adjacency(model)
        queue: deque[tuple[str, list[Transition]]] = deque([(start, [])])
        visited = {start}
        while queue:
            current, path = queue.popleft()
            if len(path) >= _MAX_DEPTH:
                continue
            for t in graph.get(current, []):
                if t.target_id == target_id:
                    return [*path, t]
                if t.target_id not in visited:
                    visited.add(t.target_id)
                    queue.append((t.target_id, [*path, t]))
        return None

    def state_coverage(self, model: StateModel) -> list[StateScenario]:
        scenarios: list[StateScenario] = []
        for i, state in enumerate(self._real_states(model)):
            path = self._shortest_path(model, state.id)
            steps = [self._label(t, model) for t in path] if path else []
            scenarios.append(
                StateScenario(
                    scenario_id=f"sc_{i + 1}",
                    scenario_type="state",
                    title=f"Pokrycie stanu {state.name or state.id}",
                    steps=steps,
                    target_state=state.name or state.id,
                    expected_result=f"System znajduje się w stanie {state.name or state.id}",
                )
            )
        return scenarios

    # --- AC5: initial → final paths --------------------------------------

    def path_scenarios(self, model: StateModel) -> list[StateScenario]:
        start = model.initial_state_id
        if start is None or not model.final_state_ids:
            return []
        finals = set(model.final_state_ids)
        graph = self._adjacency(model)
        paths: list[list[Transition]] = []

        def dfs(node: str, path: list[Transition], visited_edges: set[str]) -> None:
            if len(paths) >= _MAX_PATHS or len(path) >= _MAX_DEPTH:
                return
            if node in finals and path:
                paths.append(list(path))
                return
            for t in graph.get(node, []):
                if t.id in visited_edges:
                    continue
                dfs(t.target_id, [*path, t], visited_edges | {t.id})

        dfs(start, [], set())
        scenarios: list[StateScenario] = []
        for i, path in enumerate(paths):
            scenarios.append(
                StateScenario(
                    scenario_id=f"path_{i + 1}",
                    scenario_type="path",
                    title=f"Ścieżka {i + 1} (start → koniec)",
                    steps=[self._label(t, model) for t in path],
                    expected_result="Maszyna stanów osiąga stan końcowy",
                )
            )
        return scenarios

    # --- AC6: negative transitions ---------------------------------------

    def negative_transitions(self, model: StateModel) -> list[StateScenario]:
        all_events = {t.event for t in model.transitions if t.event}
        if not all_events:
            return []
        scenarios: list[StateScenario] = []
        count = 0
        for state in self._real_states(model):
            valid = {
                t.event
                for t in model.transitions
                if t.source_id == state.id and t.event
            }
            for event in sorted(all_events - valid):
                if count >= _MAX_NEGATIVE:
                    return scenarios
                count += 1
                scenarios.append(
                    StateScenario(
                        scenario_id=f"neg_{count}",
                        scenario_type="negative",
                        title=f"Niedozwolone zdarzenie {event} w stanie {state.name or state.id}",
                        steps=[
                            f"System jest w stanie {state.name or state.id}",
                            f"Wystąpienie zdarzenia {event}",
                        ],
                        source_state=state.name or state.id,
                        event=event,
                        expected_result="Brak przejścia — zdarzenie zignorowane (invalid transition)",
                        is_negative=True,
                    )
                )
        return scenarios
