"""StateMachineParser — PlantUML and XMI state diagrams (Story 3.6).

Builds a :class:`StateModel` (a finite state machine of ``states`` and
``transitions``, with composite-state hierarchy) from PlantUML state syntax or
XMI ``uml:StateMachine`` elements, then delegates to
:class:`StateCoverageAnalyzer` for transition/state/path/negative coverage.

PlantUML constructs handled:
``[*] --> State`` (initial), ``State --> [*]`` (final),
``A --> B : event [guard] / action`` (transitions),
``state "Name" as alias { ... }`` (composite states, nested) and
``State : entry/do/exit / action`` (state actions).
"""

import re
from xml.etree.ElementTree import Element

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.models import (
    CompositeState,
    StateModel,
    StateNode,
    Transition,
)
from app.services.analysis.uml.parsers.base import ParsedModel, ValidationResult
from app.services.analysis.uml.parsers.state_coverage_analyzer import (
    StateCoverageAnalyzer,
)

_COMMENT_RE = re.compile(r"^\s*'.*$", re.MULTILINE)

# Decisive state-diagram markers used to short-circuit keyword scoring:
# the ``[*]`` pseudostate and ``state`` declarations (PlantUML) plus
# ``uml:StateMachine`` / ``Pseudostate`` (XMI) do not appear in sequence /
# use-case / class / activity diagrams.
_STATE_MARKER_RE = re.compile(
    r"(?m)^\s*\[\*\]\s*-+\w*->|-+\w*->\s*\[\*\]\s*$|^\s*state\s+[\"\w]"
    r"|uml:StateMachine|:StateMachine\b|Pseudostate",
)

# ``A --> B : label`` — arrows may carry a direction (``-up->``) and length.
_TRANSITION_RE = re.compile(
    r'^\s*(\[\*\]|"[^"]+"|[\w.]+)\s*-+(?:up|down|left|right)?-*>\s*'
    r'(\[\*\]|"[^"]+"|[\w.]+)\s*(?::\s*(.*))?$',
    re.IGNORECASE,
)
# ``state "Name" as alias`` / ``state Name`` with optional trailing remainder.
_STATE_DECL_RE = re.compile(
    r'^\s*state\s+(?:"([^"]+)"|([\w.]+))(?:\s+as\s+(\w+))?(.*)$', re.IGNORECASE
)
# ``StateName : entry / action`` (no arrow → state action line).
_ACTION_LINE_RE = re.compile(r'^\s*(?:"([^"]+)"|([\w.]+))\s*:\s*(.*)$')
_STATE_ACTION_RE = re.compile(r"^\s*(entry|do|exit)\s*/\s*(.*)$", re.IGNORECASE)

_SKIP_PREFIXES = (
    "@startuml",
    "@enduml",
    "skinparam",
    "hide",
    "scale",
    "title",
    "left to right",
    "top to bottom",
    "!",
)


def is_state_diagram(text: str) -> bool:
    return bool(_STATE_MARKER_RE.search(text))


def _parse_label(label: str) -> tuple[str | None, str | None, str | None]:
    """Split a transition label into ``(event, guard, action)``."""
    guard: str | None = None
    m = re.search(r"\[(.*?)\]", label)
    if m:
        guard = m.group(1).strip() or None
        label = label[: m.start()] + label[m.end() :]
    action: str | None = None
    if "/" in label:
        event_part, action_part = label.split("/", 1)
        action = action_part.strip() or None
        label = event_part
    event = label.strip() or None
    return event, guard, action


class StateMachineParser:
    """Sub-parser for state-machine diagrams (PlantUML + XMI)."""

    def supported_type(self) -> DiagramType:
        return DiagramType.STATE_MACHINE

    # --- IPlantUMLSubParser protocol -------------------------------------

    def parse_plantuml(self, text: str) -> ParsedModel:
        return self.build_state_model(text).to_parsed_model()

    def parse_xmi(self, root: Element) -> ParsedModel:
        return self.build_state_model_from_xmi(root).to_parsed_model()

    # --- PlantUML --------------------------------------------------------

    def build_state_model(self, text: str) -> StateModel:
        body = self._preprocess(text)
        builder = _StateBuilder()
        for raw in body.splitlines():
            line = raw.strip()
            low = line.lower()
            if not line or any(low.startswith(p) for p in _SKIP_PREFIXES):
                continue
            if line == "}":
                builder.close_composite()
                continue

            tm = _TRANSITION_RE.match(line)
            if tm:
                event, guard, action = _parse_label(tm.group(3) or "")
                builder.add_transition(
                    tm.group(1), tm.group(2), event, guard, action
                )
                continue

            if low.startswith("state "):
                dm = _STATE_DECL_RE.match(line)
                if dm:
                    builder.declare_state(
                        dm.group(1) or dm.group(2),
                        dm.group(3),
                        dm.group(4) or "",
                    )
                    continue

            am = _ACTION_LINE_RE.match(line)
            if am:
                builder.add_action_line(am.group(1) or am.group(2), am.group(3))
                continue
            # Unknown line — ignore (graceful degradation).

        model = builder.finish()
        model.scenarios = StateCoverageAnalyzer().analyze(model)
        return model

    def _preprocess(self, text: str) -> str:
        without_comments = _COMMENT_RE.sub("", text)
        lines = [line.rstrip() for line in without_comments.splitlines()]
        return "\n".join(line for line in lines if line.strip())

    # --- XMI -------------------------------------------------------------

    def build_state_model_from_xmi(self, root: Element) -> StateModel:
        states: list[StateNode] = []
        transitions: list[Transition] = []
        composites: list[CompositeState] = []
        id_to_state: dict[str, StateNode] = {}
        initial_id: str | None = None
        final_ids: list[str] = []

        parent_of: dict[str, str | None] = {}
        for parent in root.iter():
            for child in parent:
                cid = self._xmi_attr(child, "id")
                if cid:
                    parent_of[cid] = self._xmi_attr(parent, "id") or None

        for node in root.iter():
            xtype = self._xmi_type(node)
            xid = self._xmi_attr(node, "id")
            if not xid:
                continue
            if xtype.endswith("Pseudostate"):
                kind = self._xmi_attr(node, "kind") or "initial"
                state = StateNode(
                    id=xid,
                    name=node.attrib.get("name", "") or kind,
                    is_initial=kind == "initial",
                    is_final=False,
                    parent_state_id=parent_of.get(xid),
                )
                if state.is_initial and initial_id is None:
                    initial_id = xid
                states.append(state)
                id_to_state[xid] = state
            elif xtype.endswith("FinalState"):
                state = StateNode(
                    id=xid,
                    name=node.attrib.get("name", "") or "final",
                    is_final=True,
                    parent_state_id=parent_of.get(xid),
                )
                final_ids.append(xid)
                states.append(state)
                id_to_state[xid] = state
            elif xtype.endswith("State"):
                children = [
                    self._xmi_attr(c, "id")
                    for c in node
                    if self._xmi_local(c.tag) in ("subvertex", "region")
                ]
                state = StateNode(
                    id=xid,
                    name=node.attrib.get("name", "") or xid,
                    entry_action=self._xmi_behavior(node, "entry"),
                    do_action=self._xmi_behavior(node, "doActivity"),
                    exit_action=self._xmi_behavior(node, "exit"),
                    parent_state_id=parent_of.get(xid),
                )
                states.append(state)
                id_to_state[xid] = state
                if any(self._xmi_local(c.tag) == "subvertex" for c in node):
                    composites.append(
                        CompositeState(
                            id=xid,
                            name=state.name,
                            child_ids=[c for c in children if c],
                        )
                    )

        for node in root.iter():
            if self._xmi_type(node).endswith("Transition"):
                src = self._xmi_attr(node, "source")
                tgt = self._xmi_attr(node, "target")
                if src in id_to_state and tgt in id_to_state:
                    transitions.append(
                        Transition(
                            id=self._xmi_attr(node, "id") or f"{src}_{tgt}",
                            source_id=src,
                            target_id=tgt,
                            event=self._xmi_trigger(node),
                            guard=self._xmi_guard(node),
                            action=self._xmi_effect(node),
                        )
                    )

        model = StateModel(
            states=states,
            transitions=transitions,
            composite_states=composites,
            initial_state_id=initial_id,
            final_state_ids=final_ids,
        )
        model.warnings = _validate(model)
        model.scenarios = StateCoverageAnalyzer().analyze(model)
        return model

    def _xmi_local(self, tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    def _xmi_attr(self, node: Element, name: str) -> str:
        for key, value in node.attrib.items():
            if self._xmi_local(key) == name:
                return value
        return ""

    def _xmi_type(self, node: Element) -> str:
        return self._xmi_attr(node, "type") or self._xmi_local(node.tag)

    def _xmi_behavior(self, node: Element, kind: str) -> str | None:
        for child in node:
            if self._xmi_local(child.tag) == kind:
                return child.attrib.get("name") or self._xmi_attr(child, "body") or None
        return None

    def _xmi_trigger(self, node: Element) -> str | None:
        trigger = self._xmi_attr(node, "trigger")
        if trigger:
            return trigger
        for child in node:
            if self._xmi_local(child.tag) == "trigger":
                return child.attrib.get("name") or self._xmi_attr(child, "event") or None
        return None

    def _xmi_guard(self, node: Element) -> str | None:
        for child in node:
            if self._xmi_local(child.tag) == "guard":
                body = child.attrib.get("name")
                if body:
                    return body
                for spec in child:
                    val = spec.attrib.get("value") or spec.attrib.get("body")
                    if val:
                        return val
        return None

    def _xmi_effect(self, node: Element) -> str | None:
        for child in node:
            if self._xmi_local(child.tag) == "effect":
                return child.attrib.get("name") or self._xmi_attr(child, "body") or None
        return None

    # --- validation ------------------------------------------------------

    def validate(self, content: str) -> ValidationResult:
        errors: list[str] = []
        if "@startuml" not in content and "StateMachine" not in content:
            errors.append("Brak znacznika diagramu stanów")
        return ValidationResult(is_valid=not errors, errors=errors)


def _validate(model: StateModel) -> list[str]:
    warnings: list[str] = []
    if model.initial_state_id is None:
        warnings.append("Brak stanu początkowego")
    if not model.final_state_ids:
        warnings.append("Brak stanu końcowego")
    state_ids = {s.id for s in model.states}
    for t in model.transitions:
        if t.source_id not in state_ids or t.target_id not in state_ids:
            warnings.append(f"Niespójne przejście {t.source_id}→{t.target_id}")
    # Reachability from the initial state. Entering a composite state activates
    # its internal initial pseudostate, so those children count as reachable too.
    if model.initial_state_id is not None:
        graph: dict[str, list[str]] = {}
        for t in model.transitions:
            graph.setdefault(t.source_id, []).append(t.target_id)
        init_children: dict[str, list[str]] = {}
        for state in model.states:
            if state.is_initial and state.parent_state_id is not None:
                init_children.setdefault(state.parent_state_id, []).append(state.id)
        reachable = {model.initial_state_id}
        frontier = [model.initial_state_id]
        while frontier:
            current = frontier.pop()
            successors = [*graph.get(current, []), *init_children.get(current, [])]
            for nxt in successors:
                if nxt not in reachable:
                    reachable.add(nxt)
                    frontier.append(nxt)
        for state in model.states:
            if state.id not in reachable and not state.is_initial:
                warnings.append(f"Nieosiągalny stan {state.name or state.id}")
    return warnings


class _StateBuilder:
    """Line-by-line builder of a :class:`StateModel` from PlantUML."""

    def __init__(self) -> None:
        self.states: dict[str, StateNode] = {}
        self.transitions: list[Transition] = []
        self.composites: dict[str, CompositeState] = {}
        self.alias_map: dict[str, str] = {}
        self._stack: list[str] = []
        self._pseudo_counter = 0
        self._edge_counter = 0
        self.initial_state_id: str | None = None
        self.final_state_ids: list[str] = []

    @property
    def _parent(self) -> str | None:
        return self._stack[-1] if self._stack else None

    def _register_child(self, state_id: str) -> None:
        parent = self._parent
        if (
            parent is not None
            and parent in self.composites
            and state_id not in self.composites[parent].child_ids
        ):
            self.composites[parent].child_ids.append(state_id)

    def _resolve(self, token: str) -> str:
        name = token.strip().strip('"')
        if name in self.alias_map:
            return self.alias_map[name]
        node = StateNode(id=name, name=name, parent_state_id=self._parent)
        self.states[name] = node
        self.alias_map[name] = name
        self._register_child(name)
        return name

    def _new_pseudostate(self, *, is_initial: bool) -> str:
        self._pseudo_counter += 1
        sid = f"__{'init' if is_initial else 'final'}{self._pseudo_counter}"
        self.states[sid] = StateNode(
            id=sid,
            name="[*]",
            is_initial=is_initial,
            is_final=not is_initial,
            parent_state_id=self._parent,
        )
        self._register_child(sid)
        return sid

    def declare_state(self, name: str, alias: str | None, remainder: str) -> None:
        name = name.strip().strip('"')
        sid = alias or name
        if sid not in self.states:
            self.states[sid] = StateNode(id=sid, name=name, parent_state_id=self._parent)
            self._register_child(sid)
        self.alias_map[name] = sid
        if alias:
            self.alias_map[alias] = sid

        if "{" in remainder:
            self.composites.setdefault(sid, CompositeState(id=sid, name=name))
            self.states[sid].parent_state_id = self._parent
            self._stack.append(sid)
        elif ":" in remainder:
            self._apply_action(sid, remainder.split(":", 1)[1])

    def close_composite(self) -> None:
        if self._stack:
            self._stack.pop()

    def add_action_line(self, target: str, body: str) -> None:
        sid = self._resolve(target)
        self._apply_action(sid, body)

    def _apply_action(self, sid: str, body: str) -> None:
        m = _STATE_ACTION_RE.match(body)
        if not m:
            return
        kind, action = m.group(1).lower(), m.group(2).strip() or None
        state = self.states[sid]
        if kind == "entry":
            state.entry_action = action
        elif kind == "do":
            state.do_action = action
        elif kind == "exit":
            state.exit_action = action

    def add_transition(
        self,
        left: str,
        right: str,
        event: str | None,
        guard: str | None,
        action: str | None,
    ) -> None:
        if left.strip() == "[*]":
            src = self._new_pseudostate(is_initial=True)
            tgt = self._resolve(right)
            if self._parent is None and self.initial_state_id is None:
                self.initial_state_id = src
        elif right.strip() == "[*]":
            src = self._resolve(left)
            tgt = self._new_pseudostate(is_initial=False)
            self.final_state_ids.append(tgt)
        else:
            src = self._resolve(left)
            tgt = self._resolve(right)
        self._edge_counter += 1
        transition = Transition(
            id=f"t{self._edge_counter}",
            source_id=src,
            target_id=tgt,
            event=event,
            guard=guard,
            action=action,
        )
        self.transitions.append(transition)
        parent = self._parent
        if parent is not None and parent in self.composites:
            self.composites[parent].internal_transition_ids.append(transition.id)

    def finish(self) -> StateModel:
        model = StateModel(
            states=list(self.states.values()),
            transitions=self.transitions,
            composite_states=list(self.composites.values()),
            initial_state_id=self.initial_state_id,
            final_state_ids=self.final_state_ids,
        )
        model.warnings = _validate(model)
        return model
