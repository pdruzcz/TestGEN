"""ActivityPathAnalyzer — path coverage over an ActivityModel (Story 3.5).

Walks the directed activity graph from START to STOP nodes (DFS) and enumerates
every reachable path. Loops are bounded (each edge may be traversed at most
``_MAX_EDGE_VISITS`` times) so cyclic diagrams terminate, and the total number of
paths is capped (``_MAX_PATHS``) for performance on dense fork/decision graphs.

Each path is mapped onto an :class:`ActivityScenario`: ACTION nodes become steps,
decision guards become preconditions, and a path that follows any negative guard
(``else`` / ``no`` / ``not ...``) is classified as ``alternative``.
"""

from app.services.analysis.uml.models import (
    ActivityEdge,
    ActivityModel,
    ActivityNode,
    ActivityNodeType,
    ActivityPathStep,
    ActivityScenario,
)

_MAX_EDGE_VISITS = 2
_MAX_PATHS = 200

_NEGATIVE_TOKENS = ("else", "no", "not ", "false", "nie")


def _is_negative_guard(guard: str | None) -> bool:
    if not guard:
        return False
    low = guard.strip().lower()
    return any(tok in low for tok in _NEGATIVE_TOKENS)


class ActivityPathAnalyzer:
    """Enumerates start→stop paths and converts them into test scenarios."""

    def find_all_paths(self, model: ActivityModel) -> list[list[ActivityPathStep]]:
        nodes: dict[str, ActivityNode] = {n.id: n for n in model.nodes}
        out_edges: dict[str, list[ActivityEdge]] = {}
        for edge in model.edges:
            out_edges.setdefault(edge.source_id, []).append(edge)

        starts = [n.id for n in model.nodes if n.node_type == ActivityNodeType.START]
        if not starts:
            # No explicit start: fall back to nodes without inbound edges.
            targets = {e.target_id for e in model.edges}
            starts = [n.id for n in model.nodes if n.id not in targets]

        paths: list[list[ActivityPathStep]] = []

        def walk(
            node_id: str,
            guard: str | None,
            current: list[ActivityPathStep],
            edge_visits: dict[str, int],
        ) -> None:
            if len(paths) >= _MAX_PATHS:
                return
            node = nodes.get(node_id)
            if node is None:
                return
            step = ActivityPathStep(
                node_id=node.id,
                name=node.name,
                node_type=node.node_type,
                swimlane=node.swimlane,
                guard=guard,
            )
            current = [*current, step]
            successors = out_edges.get(node_id, [])
            if node.node_type == ActivityNodeType.STOP or not successors:
                paths.append(current)
                return
            for edge in successors:
                key = edge.id
                if edge_visits.get(key, 0) >= _MAX_EDGE_VISITS:
                    continue
                walk(
                    edge.target_id,
                    edge.guard,
                    current,
                    {**edge_visits, key: edge_visits.get(key, 0) + 1},
                )

        for start_id in starts:
            walk(start_id, None, [], {})
        return paths

    def generate_scenarios(self, model: ActivityModel) -> list[ActivityScenario]:
        scenarios: list[ActivityScenario] = []
        for index, path in enumerate(self.find_all_paths(model)):
            guards = [s.guard for s in path if s.guard]
            is_alternative = any(_is_negative_guard(g) for g in guards)
            steps = [s for s in path if s.node_type == ActivityNodeType.ACTION]
            last_action = steps[-1].name if steps else ""
            scenarios.append(
                ActivityScenario(
                    path_id=f"path_{index + 1}",
                    scenario_type="alternative" if is_alternative else "main",
                    steps=steps,
                    preconditions=guards,
                    expected_result=(
                        f"{last_action} zakończone powodzeniem"
                        if last_action
                        else "Proces zakończony"
                    ),
                )
            )
        return scenarios
