"""ActivityDiagramParser — PlantUML and XMI activity diagrams (Story 3.5).

Builds an :class:`ActivityModel` (a directed graph of nodes and edges, plus
swimlanes) from PlantUML activity syntax or XMI ``uml:Activity`` elements, then
delegates to :class:`ActivityPathAnalyzer` for path-coverage scenarios.

PlantUML control structures handled with an explicit frame stack:
``start``/``stop``, actions ``:label;``, ``if/elseif/else/endif``,
``fork``/``fork again``/``end fork``, ``while``/``endwhile``,
``repeat``/``repeat while`` and swimlanes (``|Lane|`` or ``partition``).
"""

import re
from xml.etree.ElementTree import Element

from app.models.uml_diagram import DiagramType
from app.services.analysis.uml.models import (
    ActivityEdge,
    ActivityModel,
    ActivityNode,
    ActivityNodeType,
    Swimlane,
)
from app.services.analysis.uml.parsers.activity_path_analyzer import ActivityPathAnalyzer
from app.services.analysis.uml.parsers.base import ParsedModel, ValidationResult

_COMMENT_RE = re.compile(r"^\s*'.*$", re.MULTILINE)

# Decisive activity markers used by the orchestrator to short-circuit the naive
# keyword scoring (``:`` / ``->`` collide with class members and messages).
_ACTIVITY_MARKER_RE = re.compile(
    r"(?m)^\s*(?:start|stop)\s*$|^\s*:[^;]*;|^\s*(?:fork|end\s*fork|fork\s+again)\b"
    r"|^\s*if\s*\(|^\s*(?:repeat|while)\b",
)

# ``|Lane|`` or ``|#color|Lane|`` swimlane switch.
_SWIMLANE_RE = re.compile(r"^\s*\|(?:#[\w]+\|)?\s*([^|]+?)\s*\|\s*$")
# ``partition "Name" {`` or ``partition Name {``.
_PARTITION_RE = re.compile(r'^\s*partition\s+(?:"([^"]+)"|([\w .]+?))\s*\{')
# ``:multi-line action;`` — handled by accumulating until ``;``.
_ACTION_RE = re.compile(r"^\s*:(.*?);\s*$", re.DOTALL)
# ``if (cond) then (label)`` — label optional.
_IF_RE = re.compile(r"^\s*if\s*\((.*?)\)\s*(?:then\s*\((.*?)\))?", re.IGNORECASE)
_ELSEIF_RE = re.compile(r"^\s*elseif\s*\((.*?)\)\s*(?:then\s*\((.*?)\))?", re.IGNORECASE)
_ELSE_RE = re.compile(r"^\s*else\s*(?:\((.*?)\))?", re.IGNORECASE)
_WHILE_RE = re.compile(r"^\s*while\s*\((.*?)\)\s*(?:is\s*\((.*?)\))?", re.IGNORECASE)
_ENDWHILE_RE = re.compile(r"^\s*endwhile\s*(?:\((.*?)\))?", re.IGNORECASE)
_REPEATWHILE_RE = re.compile(
    r"^\s*repeat\s+while\s*\((.*?)\)\s*(?:is\s*\((.*?)\))?", re.IGNORECASE
)


def is_activity_diagram(text: str) -> bool:
    return bool(_ACTIVITY_MARKER_RE.search(text))


class ActivityDiagramParser:
    """Sub-parser for activity diagrams (PlantUML + XMI)."""

    def supported_type(self) -> DiagramType:
        return DiagramType.ACTIVITY

    # --- IPlantUMLSubParser protocol -------------------------------------

    def parse_plantuml(self, text: str) -> ParsedModel:
        return self.build_activity_model(text).to_parsed_model()

    def parse_xmi(self, root: Element) -> ParsedModel:
        return self.build_activity_model_from_xmi(root).to_parsed_model()

    # --- PlantUML --------------------------------------------------------

    def build_activity_model(self, text: str) -> ActivityModel:
        body = self._preprocess(text)
        builder = _GraphBuilder()
        lines = body.splitlines()
        i = 0
        while i < len(lines):
            raw = lines[i]
            line = raw.strip()
            i += 1
            if not line or line in ("@startuml", "@enduml") or line == "}":
                # ``}`` may close a partition — clear current swimlane.
                if line == "}":
                    builder.swimlane = None
                continue

            sl = _SWIMLANE_RE.match(raw)
            if sl:
                builder.set_swimlane(sl.group(1).strip())
                continue
            part = _PARTITION_RE.match(raw)
            if part:
                builder.set_swimlane((part.group(1) or part.group(2) or "").strip())
                continue

            low = line.lower()
            if low in ("start",):
                builder.add_start()
                continue
            if low in ("stop", "end"):
                builder.add_stop()
                continue

            # Multi-line action: accumulate until a terminating ``;``.
            if line.startswith(":") and ";" not in line:
                buf = [line]
                while i < len(lines) and ";" not in lines[i]:
                    buf.append(lines[i].strip())
                    i += 1
                if i < len(lines):
                    buf.append(lines[i].strip())
                    i += 1
                line = " ".join(buf)
            am = _ACTION_RE.match(line)
            if am:
                builder.add_action(am.group(1).strip())
                continue

            if _REPEATWHILE_RE.match(line):
                m = _REPEATWHILE_RE.match(line)
                builder.repeat_while(m.group(1).strip(), (m.group(2) or "").strip())
                continue
            ei = _ELSEIF_RE.match(line)
            if ei:
                builder.add_elseif(ei.group(1).strip(), (ei.group(2) or "").strip())
                continue
            if low.startswith("if") and _IF_RE.match(line):
                m = _IF_RE.match(line)
                builder.add_if(m.group(1).strip(), (m.group(2) or "").strip())
                continue
            el = _ELSE_RE.match(line)
            if low.startswith("else") and el:
                builder.add_else((el.group(1) or "").strip())
                continue
            if low.startswith("endif"):
                builder.end_if()
                continue
            if low.startswith("fork again"):
                builder.fork_again()
                continue
            if low == "fork":
                builder.add_fork()
                continue
            if low in ("end fork", "endfork", "end merge"):
                builder.end_fork()
                continue
            wm = _WHILE_RE.match(line)
            if low.startswith("while") and wm:
                builder.add_while(wm.group(1).strip(), (wm.group(2) or "").strip())
                continue
            em = _ENDWHILE_RE.match(line)
            if low.startswith("endwhile"):
                builder.end_while((em.group(1) or "").strip() if em else "")
                continue
            if low == "repeat":
                builder.add_repeat()
                continue
            # Unknown line — ignore (graceful degradation).

        model = builder.finish()
        analyzer = ActivityPathAnalyzer()
        model.scenarios = analyzer.generate_scenarios(model)
        return model

    def _preprocess(self, text: str) -> str:
        without_comments = _COMMENT_RE.sub("", text)
        lines = [line.rstrip() for line in without_comments.splitlines()]
        return "\n".join(line for line in lines if line.strip())

    # --- XMI -------------------------------------------------------------

    def build_activity_model_from_xmi(self, root: Element) -> ActivityModel:
        nodes: list[ActivityNode] = []
        edges: list[ActivityEdge] = []
        id_to_node: dict[str, ActivityNode] = {}
        partitions: dict[str, str] = {}  # node id → swimlane name

        # First pass: activity partitions (swimlanes) and their node references.
        swimlane_names: dict[str, list[str]] = {}
        for node in root.iter():
            if self._xmi_type(node).endswith("ActivityPartition"):
                name = node.attrib.get("name", "") or self._xmi_attr(node, "id")
                refs = self._xmi_attr(node, "node")
                node_ids = refs.split() if refs else []
                # Some tools nest <node xmi:idref=...> children.
                for child in node:
                    if self._xmi_local(child.tag) == "node":
                        idref = self._xmi_attr(child, "idref")
                        if idref:
                            node_ids.append(idref)
                swimlane_names.setdefault(name, [])
                for nid in node_ids:
                    partitions[nid] = name
                    swimlane_names[name].append(nid)

        for node in root.iter():
            xtype = self._xmi_type(node)
            xid = self._xmi_attr(node, "id")
            if not xid:
                continue
            node_type = self._xmi_node_type(xtype)
            if node_type is None:
                continue
            an = ActivityNode(
                id=xid,
                name=node.attrib.get("name", "") or xid,
                node_type=node_type,
                swimlane=partitions.get(xid),
            )
            nodes.append(an)
            id_to_node[xid] = an

        for node in root.iter():
            if self._xmi_type(node).endswith("ControlFlow") or self._xmi_local(
                node.tag
            ) == "edge":
                src = self._xmi_attr(node, "source")
                tgt = self._xmi_attr(node, "target")
                if src in id_to_node and tgt in id_to_node:
                    guard = self._xmi_guard(node)
                    edges.append(
                        ActivityEdge(
                            id=self._xmi_attr(node, "id") or f"{src}_{tgt}",
                            source_id=src,
                            target_id=tgt,
                            guard=guard,
                        )
                    )

        swimlanes = [
            Swimlane(name=name, node_ids=ids) for name, ids in swimlane_names.items()
        ]
        model = ActivityModel(nodes=nodes, edges=edges, swimlanes=swimlanes)
        model.warnings = _validate(model)
        analyzer = ActivityPathAnalyzer()
        model.scenarios = analyzer.generate_scenarios(model)
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

    def _xmi_node_type(self, xtype: str) -> ActivityNodeType | None:
        mapping = {
            "InitialNode": ActivityNodeType.START,
            "ActivityFinalNode": ActivityNodeType.STOP,
            "FlowFinalNode": ActivityNodeType.STOP,
            "OpaqueAction": ActivityNodeType.ACTION,
            "CallBehaviorAction": ActivityNodeType.ACTION,
            "Action": ActivityNodeType.ACTION,
            "DecisionNode": ActivityNodeType.DECISION,
            "MergeNode": ActivityNodeType.MERGE,
            "ForkNode": ActivityNodeType.FORK,
            "JoinNode": ActivityNodeType.JOIN,
        }
        for suffix, node_type in mapping.items():
            if xtype.endswith(suffix):
                return node_type
        return None

    def _xmi_guard(self, node: Element) -> str | None:
        guard = self._xmi_attr(node, "guard")
        if guard:
            return guard
        for child in node:
            if self._xmi_local(child.tag) == "guard":
                body = child.attrib.get("name") or self._xmi_attr(child, "value")
                if body:
                    return body
                for spec in child:
                    val = spec.attrib.get("value") or spec.attrib.get("body")
                    if val:
                        return val
        return None

    # --- validation ------------------------------------------------------

    def validate(self, content: str) -> ValidationResult:
        errors: list[str] = []
        if "@startuml" not in content and "Activity" not in content:
            errors.append("Brak znacznika diagramu aktywności")
        return ValidationResult(is_valid=not errors, errors=errors)


def _negate(guard: str) -> str:
    guard = guard.strip()
    return f"not ({guard})" if guard else "else"


def _validate(model: ActivityModel) -> list[str]:
    warnings: list[str] = []
    types = {n.node_type for n in model.nodes}
    if ActivityNodeType.START not in types:
        warnings.append("Brak węzła start")
    if ActivityNodeType.STOP not in types:
        warnings.append("Brak węzła końcowego (stop)")
    node_ids = {n.id for n in model.nodes}
    for edge in model.edges:
        if edge.source_id not in node_ids or edge.target_id not in node_ids:
            warnings.append(f"Wisząca krawędź {edge.source_id}→{edge.target_id}")
    targets = {e.target_id for e in model.edges}
    sources = {e.source_id for e in model.edges}
    for node in model.nodes:
        if (
            node.node_type not in (ActivityNodeType.START,)
            and node.id not in targets
            and node.id not in sources
        ):
            warnings.append(f"Nieosiągalny węzeł {node.name or node.id}")
    return warnings


class _GraphBuilder:
    """Sequential, stack-based builder of an ActivityModel from PlantUML lines."""

    def __init__(self) -> None:
        self.nodes: list[ActivityNode] = []
        self.edges: list[ActivityEdge] = []
        self.swimlane: str | None = None
        self.swimlane_order: list[str] = []
        self._counter = 0
        self._edge_counter = 0
        # Loose ends to connect from: list of (node_id, guard).
        self._prev: list[tuple[str, str | None]] = []
        self._stack: list[dict] = []

    def _new_id(self) -> str:
        self._counter += 1
        return f"n{self._counter}"

    def set_swimlane(self, name: str) -> None:
        self.swimlane = name
        if name not in self.swimlane_order:
            self.swimlane_order.append(name)

    def _add_node(self, name: str, node_type: ActivityNodeType) -> str:
        nid = self._new_id()
        self.nodes.append(
            ActivityNode(id=nid, name=name, node_type=node_type, swimlane=self.swimlane)
        )
        for src, guard in self._prev:
            self._edge_counter += 1
            self.edges.append(
                ActivityEdge(
                    id=f"e{self._edge_counter}",
                    source_id=src,
                    target_id=nid,
                    guard=guard,
                )
            )
        self._prev = [(nid, None)]
        return nid

    def _connect(self, src: str, tgt: str, guard: str | None) -> None:
        self._edge_counter += 1
        self.edges.append(
            ActivityEdge(
                id=f"e{self._edge_counter}", source_id=src, target_id=tgt, guard=guard
            )
        )

    def add_start(self) -> None:
        self._add_node("start", ActivityNodeType.START)

    def add_stop(self) -> None:
        self._add_node("stop", ActivityNodeType.STOP)
        self._prev = []  # branch terminates

    def add_action(self, label: str) -> None:
        self._add_node(label, ActivityNodeType.ACTION)

    # --- if / elseif / else / endif --------------------------------------

    def add_if(self, cond: str, then_label: str) -> None:
        decision = self._add_node(cond, ActivityNodeType.DECISION)
        positive = then_label or cond
        self._prev = [(decision, positive)]
        self._stack.append(
            {
                "type": "if",
                "decision": decision,
                "cond": cond,
                "branch_ends": [],
                "else_seen": False,
            }
        )

    def add_elseif(self, cond: str, then_label: str) -> None:
        frame = self._stack[-1]
        frame["branch_ends"].extend(self._prev)
        self._prev = [(frame["decision"], then_label or cond)]

    def add_else(self, label: str) -> None:
        frame = self._stack[-1]
        frame["branch_ends"].extend(self._prev)
        frame["else_seen"] = True
        guard = label or _negate(frame["cond"])
        self._prev = [(frame["decision"], guard)]

    def end_if(self) -> None:
        frame = self._stack.pop()
        ends = [*frame["branch_ends"], *self._prev]
        if not frame["else_seen"]:
            # Implicit fall-through edge straight from the decision.
            ends.append((frame["decision"], _negate(frame["cond"])))
        merge = self._new_id()
        self.nodes.append(
            ActivityNode(id=merge, name="", node_type=ActivityNodeType.MERGE, swimlane=self.swimlane)
        )
        for src, guard in ends:
            self._connect(src, merge, guard)
        self._prev = [(merge, None)]

    # --- fork / fork again / end fork ------------------------------------

    def add_fork(self) -> None:
        fork = self._add_node("", ActivityNodeType.FORK)
        self._prev = [(fork, None)]
        self._stack.append({"type": "fork", "fork": fork, "branch_ends": []})

    def fork_again(self) -> None:
        frame = self._stack[-1]
        frame["branch_ends"].extend(self._prev)
        self._prev = [(frame["fork"], None)]

    def end_fork(self) -> None:
        frame = self._stack.pop()
        ends = [*frame["branch_ends"], *self._prev]
        join = self._new_id()
        self.nodes.append(
            ActivityNode(id=join, name="", node_type=ActivityNodeType.JOIN, swimlane=self.swimlane)
        )
        for src, guard in ends:
            self._connect(src, join, guard)
        self._prev = [(join, None)]

    # --- while / endwhile ------------------------------------------------

    def add_while(self, cond: str, label: str) -> None:
        head = self._add_node(cond, ActivityNodeType.DECISION)
        positive = label or cond
        self._prev = [(head, positive)]
        self._stack.append({"type": "while", "head": head, "cond": cond})

    def end_while(self, exit_label: str) -> None:
        frame = self._stack.pop()
        head = frame["head"]
        for src, guard in self._prev:
            self._connect(src, head, guard)  # loop-back edge
        self._prev = [(head, exit_label or _negate(frame["cond"]))]

    # --- repeat / repeat while -------------------------------------------

    def add_repeat(self) -> None:
        start = self._add_node("", ActivityNodeType.MERGE)
        self._stack.append({"type": "repeat", "start": start})

    def repeat_while(self, cond: str, label: str) -> None:
        frame = self._stack.pop()
        decision = self._add_node(cond, ActivityNodeType.DECISION)
        self._connect(decision, frame["start"], label or cond)  # loop-back
        self._prev = [(decision, _negate(cond))]

    def finish(self) -> ActivityModel:
        model = ActivityModel(
            nodes=self.nodes,
            edges=self.edges,
            swimlanes=[
                Swimlane(
                    name=name,
                    node_ids=[n.id for n in self.nodes if n.swimlane == name],
                )
                for name in self.swimlane_order
            ],
        )
        model.warnings = _validate(model)
        return model
