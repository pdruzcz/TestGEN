"""Cross-diagram UML analysis — Epic 3, Story 3.7.

``CrossDiagramAnalyzer`` consolidates the parsed models of every UML diagram in a
project into an :class:`IntegratedUMLModel`, maps related diagrams onto each
other (use case ↔ sequence, participant ↔ class, use case ↔ activity, class ↔
state machine) and reconstructs end-to-end ``UserFlow`` records via a bounded
graph walk (algorithm KROK 1-5). The deterministic ("native") path is pure
Python; an optional LLM path enriches flow names and surfaces inconsistencies.

The pure mapping / reconstruction logic lives in module-level functions so it
can be unit-tested without a database. The class only adds the DB collection,
persistence and optional LLM enrichment around them.
"""

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_flow import FlowSourceType, FlowStatus, FlowStep, UserFlow
from app.schemas.user_flow import CrossAnalysisResponse, FlowStepOut, UserFlowOut
from app.services.analysis.uml.integrated_model import (
    CoverageReport,
    DiagramBundle,
    IntegratedUMLModel,
)

logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 0.7
_MAX_FLOWS = 200
_MAX_DEPTH = 60


def _as_uuid(value: str | None) -> uuid.UUID | None:
    """Best-effort UUID parse; non-UUID identifiers map to None."""
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _norm(value: str | None) -> str:
    """Lower-case and strip non-alphanumeric chars for fuzzy comparison."""
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _stem(filename: str) -> str:
    """Filename without its extension."""
    idx = filename.rfind(".")
    return filename[:idx] if idx != -1 else filename


def _fuzzy(a: str | None, b: str | None) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb or na in nb or nb in na:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


# --- Cross-diagram mapping (AC1-AC5) -------------------------------------


def _use_case_id(diagram_id: str, name: str) -> str:
    return f"{diagram_id}::{name}"


def _actors_of_use_case(bundle: DiagramBundle) -> set[str]:
    """Actor names declared in a use-case diagram (participants)."""
    return {str(a.get("name", "")) for a in bundle.participants if a.get("name")}


def _map_use_case_to_sequences(integrated: IntegratedUMLModel) -> dict[str, list[str]]:
    sequences = integrated.bundles_of_type("sequence")
    result: dict[str, list[str]] = {}
    for uc_bundle in integrated.bundles_of_type("use_case"):
        actors = _actors_of_use_case(uc_bundle)
        for uc in uc_bundle.elements:
            uc_name = str(uc.get("name", ""))
            if not uc_name:
                continue
            uc_id = _use_case_id(uc_bundle.diagram_id, uc_name)
            matched: list[str] = []
            for seq in sequences:
                by_name = _fuzzy(uc_name, _stem(seq.name)) >= _FUZZY_THRESHOLD
                seq_participants = {str(p.get("name", "")) for p in seq.participants}
                by_actor = bool(actors & seq_participants)
                by_message = any(
                    _fuzzy(uc_name, str(m.get("label", ""))) >= _FUZZY_THRESHOLD for m in seq.relationships
                )
                if by_name or by_actor or by_message:
                    matched.append(seq.diagram_id)
            if matched:
                result[uc_id] = matched
    return result


def _class_names(integrated: IntegratedUMLModel) -> list[str]:
    names: list[str] = []
    for cls in integrated.bundles_of_type("class"):
        for el in cls.elements:
            if el.get("element_kind") in ("class", "interface") and el.get("name"):
                names.append(str(el["name"]))
    return names


def _map_participants_to_classes(integrated: IntegratedUMLModel) -> dict[str, str]:
    class_names = _class_names(integrated)
    result: dict[str, str] = {}
    for seq in integrated.bundles_of_type("sequence"):
        for participant in seq.participants:
            pname = str(participant.get("name", ""))
            if not pname:
                continue
            best_name, best_score = "", 0.0
            for cname in class_names:
                score = _fuzzy(pname, cname)
                if score > best_score:
                    best_name, best_score = cname, score
            if best_score >= _FUZZY_THRESHOLD:
                result[pname] = best_name
    return result


def _map_use_case_to_activity(integrated: IntegratedUMLModel) -> dict[str, str]:
    activities = integrated.bundles_of_type("activity")
    result: dict[str, str] = {}
    for uc_bundle in integrated.bundles_of_type("use_case"):
        actors = {_norm(a) for a in _actors_of_use_case(uc_bundle)}
        for uc in uc_bundle.elements:
            uc_name = str(uc.get("name", ""))
            if not uc_name:
                continue
            uc_id = _use_case_id(uc_bundle.diagram_id, uc_name)
            best_id, best_score = "", 0.0
            for act in activities:
                score = _fuzzy(uc_name, _stem(act.name))
                swimlanes = {_norm(str(f.get("name", ""))) for f in act.fragments if f.get("name")}
                if actors & swimlanes:
                    score = max(score, _FUZZY_THRESHOLD)
                if score > best_score:
                    best_id, best_score = act.diagram_id, score
            if best_score >= _FUZZY_THRESHOLD:
                result[uc_id] = best_id
    return result


def _map_class_to_state_machine(integrated: IntegratedUMLModel) -> dict[str, str]:
    class_names = _class_names(integrated)
    result: dict[str, str] = {}
    for state in integrated.bundles_of_type("state_machine"):
        machine_name = _stem(state.name)
        best_name, best_score = "", 0.0
        for cname in class_names:
            score = _fuzzy(machine_name, cname)
            if score > best_score:
                best_name, best_score = cname, score
        if best_score >= _FUZZY_THRESHOLD:
            result[best_name] = state.diagram_id
    return result


def _validate_mappings(integrated: IntegratedUMLModel) -> list[str]:
    """Detect inconsistencies across diagrams (AC5)."""
    warnings: list[str] = []
    use_case_actors: set[str] = set()
    for uc_bundle in integrated.bundles_of_type("use_case"):
        use_case_actors |= {_norm(a) for a in _actors_of_use_case(uc_bundle)}

    if use_case_actors:
        for seq in integrated.bundles_of_type("sequence"):
            for participant in seq.participants:
                if participant.get("participant_type") != "actor":
                    continue
                pname = str(participant.get("name", ""))
                if pname and _norm(pname) not in use_case_actors:
                    warnings.append(
                        f"Aktor '{pname}' z diagramu sekwencji '{seq.name}' nie występuje w żadnym diagramie use case."
                    )
    return warnings


def build_integrated_model(bundles: list[DiagramBundle]) -> IntegratedUMLModel:
    """KROK 1-2: consolidate parsed models and compute cross-diagram mappings."""
    integrated = IntegratedUMLModel(all_models={b.diagram_id: b for b in bundles})
    integrated.use_case_to_sequences = _map_use_case_to_sequences(integrated)
    integrated.participant_to_class = _map_participants_to_classes(integrated)
    integrated.use_case_to_activity = _map_use_case_to_activity(integrated)
    integrated.class_to_state_machine = _map_class_to_state_machine(integrated)
    integrated.warnings = _validate_mappings(integrated)

    mapped_ids: set[str] = set()
    for seq_ids in integrated.use_case_to_sequences.values():
        mapped_ids.update(seq_ids)
    mapped_ids.update(integrated.use_case_to_activity.values())
    mapped_ids.update(integrated.class_to_state_machine.values())
    # Use-case diagrams that produced at least one mapping count as mapped.
    for uc_bundle in integrated.bundles_of_type("use_case"):
        for uc_id in integrated.use_case_to_sequences:
            if uc_id.startswith(uc_bundle.diagram_id):
                mapped_ids.add(uc_bundle.diagram_id)
        for uc_id in integrated.use_case_to_activity:
            if uc_id.startswith(uc_bundle.diagram_id):
                mapped_ids.add(uc_bundle.diagram_id)
    # Class diagrams referenced by a participant/state mapping count as mapped.
    for cls in integrated.bundles_of_type("class"):
        cls_names = {_norm(n) for n in _class_names(integrated)}
        mapped_class_names = {_norm(v) for v in integrated.participant_to_class.values()}
        mapped_class_names |= {_norm(k) for k in integrated.class_to_state_machine}
        if cls_names & mapped_class_names:
            mapped_ids.add(cls.diagram_id)

    total = len(bundles)
    mapped = len([b for b in bundles if b.diagram_id in mapped_ids])
    integrated.coverage_report = CoverageReport(
        mapped_diagrams=mapped,
        unmapped_diagrams=total - mapped,
        coverage_percentage=round(100.0 * mapped / total, 1) if total else 0.0,
        warnings=integrated.warnings,
    )
    return integrated


# --- Flow reconstruction (AC6) -------------------------------------------


@dataclass
class _FlowDraft:
    name: str
    source_ids: list[str]
    steps: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class StartPoint:
    diagram_id: str
    node_id: str
    label: str
    kind: str  # "activity" | "state"


def _adjacency(edges: list[dict]) -> dict[str, list[dict]]:
    graph: dict[str, list[dict]] = {}
    for e in edges:
        graph.setdefault(str(e.get("source_id")), []).append(e)
    return graph


def _identify_start_points(integrated: IntegratedUMLModel) -> list[StartPoint]:
    """KROK 2: start nodes (activity), initial states (state machine)."""
    points: list[StartPoint] = []
    for act in integrated.bundles_of_type("activity"):
        for node in act.elements:
            if node.get("node_type") == "start":
                points.append(StartPoint(act.diagram_id, str(node.get("id")), "start", "activity"))
    for state in integrated.bundles_of_type("state_machine"):
        for node in state.elements:
            if node.get("is_initial"):
                points.append(StartPoint(state.diagram_id, str(node.get("id")), node.get("name", "start"), "state"))
    return points


def _reconstruct_activity(bundle: DiagramBundle, integrated: IntegratedUMLModel) -> list[_FlowDraft]:
    nodes = {str(n.get("id")): n for n in bundle.elements}
    graph = _adjacency(bundle.relationships)
    starts = [nid for nid, n in nodes.items() if n.get("node_type") == "start"]
    drafts: list[_FlowDraft] = []

    def is_end(node: dict) -> bool:
        return node.get("node_type") == "stop"

    def walk(node_id: str, visited: set[str], steps: list[dict], pending_guard: str | None) -> None:
        if len(drafts) >= _MAX_FLOWS or len(steps) > _MAX_DEPTH:
            return
        node = nodes.get(node_id)
        if node is None:
            return
        ntype = node.get("node_type")
        if ntype == "action":
            step: dict = {
                "sequence": len(steps) + 1,
                "action": str(node.get("name", "")),
                "actor": node.get("swimlane"),
                "target_element": None,
                "expected_result": None,
                "source_diagram_id": bundle.diagram_id,
                "source": "native",
            }
            if pending_guard:
                # Decision branch lifted to metadata (Story 3-11-domknięcie, AC4)
                # instead of being flattened into the next step's expected_result.
                step["metadata"] = {"branch_label": pending_guard}
            steps = [*steps, step]
            pending_guard = None
        if is_end(node):
            if steps:
                idx = len(drafts) + 1
                drafts.append(
                    _FlowDraft(
                        name=f"{_stem(bundle.name)} — ścieżka {idx}",
                        source_ids=[bundle.diagram_id],
                        steps=steps,
                    )
                )
            return
        out_edges = graph.get(node_id, [])
        for edge in out_edges:
            target = str(edge.get("target_id"))
            if target in visited or target == node_id:
                # LOOP detected (incl. self-loop): record a repeatable marker, do not recurse.
                if steps:
                    steps[-1]["expected_result"] = (
                        (steps[-1].get("expected_result") or "") + " (krok powtarzalny / pętla)"
                    ).strip()
                continue
            walk(target, visited | {node_id}, steps, edge.get("guard"))

    for start in starts:
        walk(start, set(), [], None)
    return drafts


def _reconstruct_state(bundle: DiagramBundle, integrated: IntegratedUMLModel) -> list[_FlowDraft]:
    states = {str(s.get("id")): s for s in bundle.elements}
    graph = _adjacency(bundle.relationships)
    initials = [sid for sid, s in states.items() if s.get("is_initial")]
    # Which class does this state machine describe?
    actor = None
    for cname, sid in integrated.class_to_state_machine.items():
        if sid == bundle.diagram_id:
            actor = cname
            break
    drafts: list[_FlowDraft] = []

    def name_of(sid: str) -> str:
        s = states.get(sid)
        return str(s.get("name", sid)) if s else sid

    def walk(state_id: str, visited: set[str], steps: list[dict]) -> None:
        if len(drafts) >= _MAX_FLOWS or len(steps) > _MAX_DEPTH:
            return
        state = states.get(state_id)
        if state is None:
            return
        if state.get("is_final"):
            if steps:
                idx = len(drafts) + 1
                drafts.append(
                    _FlowDraft(
                        name=f"{_stem(bundle.name)} — cykl życia {idx}",
                        source_ids=[bundle.diagram_id],
                        steps=steps,
                    )
                )
            return
        out_edges = graph.get(state_id, [])
        if not out_edges and steps:
            idx = len(drafts) + 1
            drafts.append(
                _FlowDraft(
                    name=f"{_stem(bundle.name)} — cykl życia {idx}",
                    source_ids=[bundle.diagram_id],
                    steps=steps,
                )
            )
            return
        for edge in out_edges:
            target = str(edge.get("target_id"))
            if target in visited:
                continue
            event = edge.get("event") or "przejście"
            guard = f" [{edge['guard']}]" if edge.get("guard") else ""
            step = {
                "sequence": len(steps) + 1,
                "action": f"{event}{guard}",
                "actor": actor,
                "target_element": name_of(target),
                "expected_result": f"stan: {name_of(target)}",
                "source_diagram_id": bundle.diagram_id,
                "source": "native",
            }
            walk(target, visited | {state_id}, [*steps, step])

    for start in initials:
        walk(start, set(), [])
    return drafts


def _reconstruct_use_case(bundle: DiagramBundle, integrated: IntegratedUMLModel) -> list[_FlowDraft]:
    """Reconstruct flows from a use-case diagram (Story 3-11-domknięcie, AC1).

    Use-case ``include``/``extend`` relationships are parsed into ``UCScenario``
    rows by the 3.3 parser (``use_case.generate_scenarios``) and stored on
    ``bundle.flows``. This lifts them into ``_FlowDraft`` steps carrying UML
    relation metadata so the Gherkin mapper can turn them into a real
    ``Background`` (``include``) and ``Scenario Outline`` (``extend``):

    - a ``main`` scenario's include-injected leading steps (matched against the
      declared ``include`` relationships in ``bundle.relationships``) are tagged
      ``relation_type="include"`` — the shared/common steps that become
      ``Background``,
    - an ``alternative`` scenario (one per ``extend``) is tagged
      ``relation_type="extend"`` with ``parameters`` drawn from its
      preconditions/guard — the source of the ``Scenario Outline`` ``Examples``.
    """
    # Declared include relationships (UCRelationship dicts): source UC includes target UC.
    includes: dict[str, set[str]] = {}
    for rel in bundle.relationships:
        if rel.get("relationship_type") == "include":
            includes.setdefault(str(rel.get("source")), set()).add(str(rel.get("target")))

    drafts: list[_FlowDraft] = []
    for scenario in bundle.flows:
        if not isinstance(scenario, dict):
            continue
        uc_name = str(scenario.get("use_case_name", ""))
        scenario_type = scenario.get("scenario_type", "main")
        inc_names = includes.get(uc_name, set())
        preconditions = list(scenario.get("preconditions") or [])

        uc_steps = [s for s in (scenario.get("steps") or []) if isinstance(s, dict)]
        last_idx = len(uc_steps) - 1
        steps: list[dict] = []
        for i, s in enumerate(uc_steps):
            target = str(s.get("target") or "")
            step: dict = {
                "sequence": s.get("sequence", i + 1),
                "action": str(s.get("action", "")),
                "actor": scenario.get("primary_actor") or s.get("actor"),
                "target_element": target or None,
                "expected_result": scenario.get("expected_result") if i == last_idx else None,
                "source_diagram_id": bundle.diagram_id,
                "source": "native",
            }
            # Relation metadata (AC1) consumed by the deterministic Gherkin mapper.
            if scenario_type == "alternative":
                # extend variant — Examples sourced from the extend guard/preconditions.
                step["metadata"] = {"relation_type": "extend", "parameters": preconditions}
            elif target and target in inc_names:
                # include-injected shared step (Background material).
                step["metadata"] = {"relation_type": "include", "parameters": []}
            steps.append(step)

        if not steps:
            continue
        name = f"{_stem(bundle.name)} — {uc_name or 'przypadek użycia'}"
        if scenario_type == "alternative":
            name += " (rozszerzenie)"
        drafts.append(_FlowDraft(name=name, source_ids=[bundle.diagram_id], steps=steps))
    return drafts


def _validate_flow_consistency(drafts: list[_FlowDraft]) -> list[str]:
    """KROK 4: every flow must have a start and an end (≥1 step)."""
    warnings: list[str] = []
    for draft in drafts:
        if not draft.steps:
            warnings.append(f"Flow '{draft.name}' nie ma żadnych kroków (pominięto).")
    return warnings


def reconstruct_flows(integrated: IntegratedUMLModel) -> tuple[list[_FlowDraft], list[str]]:
    """KROK 3-5: build transition graphs and emit UserFlow drafts."""
    start_points = _identify_start_points(integrated)  # KROK 2
    logger.debug("Identified %d start points", len(start_points))
    drafts: list[_FlowDraft] = []
    for uc in integrated.bundles_of_type("use_case"):
        if len(drafts) >= _MAX_FLOWS:
            break
        drafts.extend(_reconstruct_use_case(uc, integrated))
    for act in integrated.bundles_of_type("activity"):
        if len(drafts) >= _MAX_FLOWS:
            break
        drafts.extend(_reconstruct_activity(act, integrated))
    for state in integrated.bundles_of_type("state_machine"):
        if len(drafts) >= _MAX_FLOWS:
            break
        drafts.extend(_reconstruct_state(state, integrated))

    consistency = _validate_flow_consistency(drafts)
    drafts = [d for d in drafts if d.steps][:_MAX_FLOWS]
    return drafts, consistency


# --- Orchestrator (DB + LLM) ---------------------------------------------


class CrossDiagramAnalyzer:
    def __init__(
        self,
        db: AsyncSession,
        llm_gateway=None,
        engine_mode: str = "native",
        diagram_ids: list[uuid.UUID] | None = None,
    ):
        self._db = db
        self._llm = llm_gateway
        self._engine_mode = engine_mode
        self._diagram_ids = diagram_ids

    async def analyze(self, project_id: uuid.UUID, tenant_id: uuid.UUID) -> CrossAnalysisResponse:
        t0 = time.perf_counter()
        bundles = await self._collect_models(project_id)
        logger.info("KROK 1 collect_models: %d diagrams in %.3fs", len(bundles), time.perf_counter() - t0)

        t1 = time.perf_counter()
        integrated = build_integrated_model(bundles)
        logger.info(
            "KROK 2 build_integrated_model: coverage=%.1f%% in %.3fs",
            integrated.coverage_report.coverage_percentage,
            time.perf_counter() - t1,
        )

        t2 = time.perf_counter()
        drafts, consistency = reconstruct_flows(integrated)
        logger.info("KROK 3-5 reconstruct_flows: %d flows in %.3fs", len(drafts), time.perf_counter() - t2)

        warnings = [*integrated.warnings, *consistency]

        if self._engine_mode in ("llm", "hybrid") and self._llm is not None:
            t3 = time.perf_counter()
            drafts, llm_warnings = await self._llm_enrich_flows(drafts, integrated, tenant_id)
            warnings.extend(llm_warnings)
            logger.info("AC8 llm_enrich_flows in %.3fs", time.perf_counter() - t3)

        saved = await self._save_user_flows(drafts, project_id, tenant_id)
        return CrossAnalysisResponse(user_flows=saved, coverage_warnings=warnings)

    async def _collect_models(self, project_id: uuid.UUID) -> list[DiagramBundle]:
        from app.models.uml_diagram import ParsedUMLModel, UMLDiagram

        stmt = select(UMLDiagram).where(UMLDiagram.project_id == project_id)
        if self._diagram_ids:
            stmt = stmt.where(UMLDiagram.id.in_(self._diagram_ids))
        diagrams = (await self._db.execute(stmt)).scalars().all()

        bundles: list[DiagramBundle] = []
        for d in diagrams:
            parsed = (
                await self._db.execute(
                    select(ParsedUMLModel)
                    .where(ParsedUMLModel.diagram_id == d.id)
                    .order_by(ParsedUMLModel.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if parsed is None:
                continue
            bundles.append(
                DiagramBundle(
                    diagram_id=str(d.id),
                    diagram_type=parsed.model_type.value,
                    name=d.filename,
                    participants=parsed.participants or [],
                    elements=parsed.elements or [],
                    relationships=parsed.relationships or [],
                    fragments=parsed.fragments or [],
                    flows=parsed.flows or [],
                )
            )
        return bundles

    async def _llm_enrich_flows(
        self, drafts: list[_FlowDraft], integrated: IntegratedUMLModel, tenant_id: uuid.UUID
    ) -> tuple[list[_FlowDraft], list[str]]:
        """AC8: enrich flow names and surface inconsistencies via the LLM Gateway.

        On any failure (gateway unavailable, malformed output) the native drafts
        are returned unchanged (graceful degradation).
        """
        if not drafts:
            return drafts, []
        try:
            import json

            from app.services.analysis.llm_gateway import LLMMessage

            summary = [
                {"index": i, "name": d.name, "steps": [s["action"] for s in d.steps]} for i, d in enumerate(drafts)
            ]
            prompt = (
                "Przeanalizuj poniższe user flows zrekonstruowane z diagramów UML. "
                'Zwróć JSON: {"names": {"<index>": "opisowa nazwa po polsku"}, '
                '"inconsistencies": ["..."]}. Flows:\n' + json.dumps(summary, ensure_ascii=False)
            )
            response = await self._llm.complete(
                provider="anthropic",
                messages=[LLMMessage(role="user", content=prompt)],
                module="uml_analysis",
                task_type="cross_diagram_flow_analysis",
                tenant_id=None,
            )
            data = json.loads(response.content)
            names = data.get("names", {})
            for i, draft in enumerate(drafts):
                new_name = names.get(str(i))
                if new_name:
                    draft.name = str(new_name)
                    for step in draft.steps:
                        step["source"] = "llm"
            return drafts, [str(w) for w in data.get("inconsistencies", [])]
        except Exception as exc:  # graceful degradation — keep native flows
            logger.warning("LLM enrichment failed, falling back to native flows: %s", exc)
            return drafts, []

    async def _save_user_flows(
        self, drafts: list[_FlowDraft], project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[UserFlowOut]:
        out: list[UserFlowOut] = []
        for draft in drafts:
            flow = UserFlow(
                project_id=project_id,
                tenant_id=tenant_id,
                source_type=FlowSourceType.UML,
                source_ids=draft.source_ids,
                name=draft.name,
                steps=draft.steps,
                status=FlowStatus.DRAFT,
                warnings=draft.warnings or None,
            )
            self._db.add(flow)
            await self._db.flush()
            step_outs: list[FlowStepOut] = []
            for step in draft.steps:
                fs = FlowStep(
                    flow_id=flow.id,
                    sequence=step.get("sequence", 0),
                    action=step.get("action", ""),
                    actor=step.get("actor"),
                    target_element=step.get("target_element"),
                    expected_result=step.get("expected_result"),
                    source_diagram_id=_as_uuid(step.get("source_diagram_id")),
                    source=step.get("source", "native"),
                    meta=step.get("metadata"),
                )
                self._db.add(fs)
                step_outs.append(
                    FlowStepOut(
                        sequence=fs.sequence,
                        action=fs.action,
                        actor=fs.actor,
                        target_element=fs.target_element,
                        expected_result=fs.expected_result,
                        source_diagram_id=fs.source_diagram_id,
                        source=fs.source,
                        metadata=fs.meta,
                    )
                )
            out.append(
                UserFlowOut(
                    id=flow.id,
                    name=flow.name,
                    source_type=flow.source_type,
                    source_ids=draft.source_ids,
                    steps=step_outs,
                    status=flow.status,
                    warnings=draft.warnings or None,
                )
            )
        await self._db.flush()
        return out
