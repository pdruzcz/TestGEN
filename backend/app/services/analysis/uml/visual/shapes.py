"""Pure-Python geometry for visual UML parsing (Story 3.1b, Tier 2).

This module is deliberately free of any CV/OCR dependency so the shape → UML
mapping, diagram-type classification and confidence computation stay fully
unit-testable on synthetic geometry. The acquisition of shapes (SVG elements or
OpenCV contours) and text blocks (OCR) lives in :mod:`visual.svg_parser` and
:mod:`visual.image_parser`; both feed the same :class:`Shape` / :class:`Box`
abstractions defined here.

Shape → UML semantics (epics.md:2561-2563):

* rectangle  → class element
* ellipse    → use-case element
* diamond    → decision node (activity / state)
* arrow/line → relationship, source/target reconstructed from endpoint geometry
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.models.uml_diagram import DiagramType, UMLModelSource
from app.services.analysis.uml.parsers.base import ParsedModel

# Shape kinds recognised by the visual pipeline.
RECTANGLE = "rectangle"
ELLIPSE = "ellipse"
DIAMOND = "diamond"
ARROW = "arrow"
LINE = "line"

_NON_NODE_KINDS = {ARROW, LINE}


@dataclass
class Box:
    """Axis-aligned bounding box (SVG / image coordinates)."""

    x: float
    y: float
    width: float
    height: float

    @property
    def cx(self) -> float:
        return self.x + self.width / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.height / 2.0

    @property
    def center(self) -> tuple[float, float]:
        return (self.cx, self.cy)

    def distance_to_point(self, px: float, py: float) -> float:
        return math.hypot(self.cx - px, self.cy - py)


@dataclass
class Shape:
    """A recognised visual primitive.

    For nodes (rectangle/ellipse/diamond) ``box`` is authoritative. For
    connectors (arrow/line) ``start`` / ``end`` carry the directed endpoints.
    """

    kind: str
    box: Box
    label: str | None = None
    start: tuple[float, float] | None = None
    end: tuple[float, float] | None = None
    confidence: float = 1.0


@dataclass
class TextLabel:
    """A piece of recognised text with its anchor point."""

    text: str
    x: float
    y: float
    confidence: float = 1.0


def _node_shapes(shapes: list[Shape]) -> list[Shape]:
    return [s for s in shapes if s.kind not in _NON_NODE_KINDS]


def _connectors(shapes: list[Shape]) -> list[Shape]:
    return [s for s in shapes if s.kind in _NON_NODE_KINDS]


def attach_labels(shapes: list[Shape], labels: list[TextLabel]) -> list[Shape]:
    """Bind each text label to its nearest node shape (if reasonably close).

    Labels are matched to the node whose centre is nearest, but only when that
    centre falls within ~1.5 times the node's half-extent — otherwise the label
    is treated as an arrow label (handled later) or noise.
    """
    nodes = _node_shapes(shapes)
    for label in labels:
        best: Shape | None = None
        best_dist = math.inf
        for node in nodes:
            dist = node.box.distance_to_point(label.x, label.y)
            # Tolerance: label may sit just inside or above the node box.
            reach = 1.5 * max(node.box.width, node.box.height) / 2.0 + 24.0
            if dist < reach and dist < best_dist:
                best, best_dist = node, dist
        if best is not None and not best.label:
            best.label = label.text.strip() or None
    return shapes


def _anonymous_name(kind: str, index: int) -> str:
    return f"{kind.capitalize()}_{index}"


def _ensure_names(nodes: list[Shape]) -> None:
    """Name every node so relationships can reference them by name."""
    counters: dict[str, int] = {}
    for node in nodes:
        if node.label:
            node_name = node.label
        else:
            counters[node.kind] = counters.get(node.kind, 0) + 1
            node_name = _anonymous_name(node.kind, counters[node.kind])
        # Stash the resolved name on the box via a private attribute carrier.
        node.box.__dict__["_name"] = node_name  # type: ignore[attr-defined]


def _node_name(node: Shape) -> str:
    return getattr(node.box, "_name", None) or node.label or _anonymous_name(node.kind, 0)  # type: ignore[attr-defined]


# --- Structural field derivation (Story 3.1b closure) --------------------
#
# Visual primitives carry geometry + a name; downstream (cross-diagram 3.7,
# compare-code 3.4, traceability 3.15) reads the structural schema emitted by
# the XMI/PlantUML parsers (element_kind / id / node_type / is_initial /
# is_final / source_id / target_id). The helpers below derive those structural
# fields from the visual signal so OCR-derived diagrams feed downstream instead
# of silently yielding empty mappings. Start/stop (and initial/final) nodes are
# read from explicit labels first, with topological roots/sinks as a
# best-effort fallback — honest given OCR's lower fidelity, already signalled by
# ``source = ocr`` + ``confidence``.

_START_LABELS = {"start", "begin", "poczatek", "pocztek", "initial", "startstate"}
_STOP_LABELS = {"stop", "end", "koniec", "finish", "final", "endstate", "finalstate"}


def _norm_label(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _topology(relationships: list[dict]) -> tuple[set[str], set[str]]:
    """Return the (sources, targets) node-name sets from name-based relationships.

    A *root* is a node that is a relationship source but never a target (entry
    point); a *sink* is a target that is never a source (exit point).
    """
    sources: set[str] = set()
    targets: set[str] = set()
    for rel in relationships:
        s = str(rel.get("source") or "")
        t = str(rel.get("target") or "")
        if s:
            sources.add(s)
        if t:
            targets.add(t)
    return sources, targets


def _activity_node_type(kind: str, name: str, is_root: bool, is_sink: bool) -> str:
    """Classify an activity node's type from shape, label and topology."""
    if kind == DIAMOND:
        return "decision"
    norm = _norm_label(name)
    if norm in _START_LABELS:
        return "start"
    if norm in _STOP_LABELS:
        return "stop"
    # OCR cannot see the filled start / bullseye stop circles of real UML; fall
    # back to DAG topology so flow reconstruction has entry/exit points.
    if is_sink:
        return "stop"
    if is_root:
        return "start"
    return "action"


def _state_flags(name: str, is_root: bool, is_sink: bool) -> tuple[bool, bool]:
    """Derive (is_initial, is_final) for a state-machine node."""
    norm = _norm_label(name)
    is_initial = norm in _START_LABELS or is_root
    is_final = norm in _STOP_LABELS or is_sink
    return is_initial, is_final


def build_relationships(shapes: list[Shape], labels: list[TextLabel]) -> list[dict]:
    """Reconstruct relationships from connector endpoints.

    Each connector's ``start`` / ``end`` points are matched to the nearest node
    centre. Arrow labels (text not attached to a node) are bound to the nearest
    connector.
    """
    nodes = _node_shapes(shapes)
    connectors = _connectors(shapes)
    relationships: list[dict] = []

    for conn in connectors:
        start = conn.start or conn.box.center
        end = conn.end or conn.box.center
        if start == end:
            continue
        source = _nearest_node(nodes, *start, exclude=None)
        target = _nearest_node(nodes, *end, exclude=source)
        if source is None or target is None:
            continue
        relationships.append(
            {
                "source": _node_name(source),
                "target": _node_name(target),
                "relationship_type": "association",
                "label": conn.label,
            }
        )
    return relationships


def _nearest_node(nodes: list[Shape], px: float, py: float, exclude: Shape | None) -> Shape | None:
    best: Shape | None = None
    best_dist = math.inf
    for node in nodes:
        if node is exclude:
            continue
        dist = node.box.distance_to_point(px, py)
        if dist < best_dist:
            best, best_dist = node, dist
    return best


def classify_visual_diagram_type(shapes: list[Shape]) -> DiagramType:
    """Heuristic diagram-type classification from shape composition."""
    ovals = sum(1 for s in shapes if s.kind == ELLIPSE)
    rects = sum(1 for s in shapes if s.kind == RECTANGLE)
    diamonds = sum(1 for s in shapes if s.kind == DIAMOND)
    connectors = len(_connectors(shapes))

    scores: dict[DiagramType, int] = {
        DiagramType.SEQUENCE: 0,
        DiagramType.USE_CASE: 0,
        DiagramType.CLASS: 0,
        DiagramType.ACTIVITY: 0,
        DiagramType.STATE_MACHINE: 0,
    }
    if ovals:
        scores[DiagramType.USE_CASE] += ovals * 2
    if rects:
        scores[DiagramType.CLASS] += rects
    if diamonds:
        # Decision diamonds strongly signal flow diagrams; weight high enough
        # to outrank rectangles (a class diagram has no diamonds).
        scores[DiagramType.ACTIVITY] += diamonds * 3
        scores[DiagramType.STATE_MACHINE] += diamonds
    if connectors:
        scores[DiagramType.SEQUENCE] += connectors // 2
        scores[DiagramType.ACTIVITY] += connectors // 3

    best = max(scores, key=lambda dt: scores[dt])
    return best if scores[best] > 0 else DiagramType.SEQUENCE


def _compute_confidence(shapes: list[Shape], labels: list[TextLabel]) -> float:
    """Aggregate OCR/shape confidence: labelled-node ratio times mean label confidence.

    Unlabelled nodes lower confidence (names are anonymous); a diagram with no
    labels at all still yields a small non-zero confidence rather than 0.
    """
    nodes = _node_shapes(shapes)
    if not nodes:
        return 0.0
    labelled = [n for n in nodes if n.label]
    label_ratio = len(labelled) / len(nodes)
    mean_label_conf = sum(n.confidence for n in labelled) / len(labelled) if labelled else 0.4
    # Shape-detection certainty: rectangles/ellipses are reliable; diamonds less so.
    shape_conf = sum(n.confidence for n in nodes) / len(nodes)
    confidence = 0.5 * label_ratio * mean_label_conf + 0.5 * shape_conf
    if not labelled:
        # No text at all — cap low, this is shape-only inference.
        confidence = min(confidence, 0.35)
    return round(max(0.0, min(1.0, confidence)), 3)


def build_visual_model(
    shapes: list[Shape],
    labels: list[TextLabel] | None = None,
    *,
    diagram_type: DiagramType | None = None,
) -> ParsedModel:
    """Map raw visual primitives onto a :class:`ParsedModel` (source = OCR).

    This is the single entry point shared by the SVG and raster/PDF paths.

    Elements carry BOTH the visual fields (``element_type``, ``bbox``) and the
    structural discriminators downstream reads (Story 3.1b closure): class
    elements get ``element_kind``; activity nodes get ``id`` + ``node_type``;
    state nodes get ``id`` + ``is_initial``/``is_final``; relationships carry
    resolved ``source_id``/``target_id`` alongside the name-based endpoints.
    """
    labels = labels or []
    attach_labels(shapes, labels)
    nodes = _node_shapes(shapes)
    _ensure_names(nodes)

    dtype = diagram_type or classify_visual_diagram_type(shapes)
    relationships = build_relationships(shapes, labels)
    confidence = _compute_confidence(shapes, labels)

    # Stable ids keyed by node name, so name-based relationships can be resolved
    # to source_id/target_id. First occurrence wins on a (rare) name collision.
    node_ids = {_node_name(node): f"v{idx}" for idx, node in enumerate(nodes)}
    sources, targets = _topology(relationships)

    elements: list[dict] = []
    participants: list[dict] = []
    fragments: list[dict] = []

    for node in nodes:
        name = _node_name(node)
        is_root = name in sources and name not in targets
        is_sink = name in targets and name not in sources
        entry: dict = {
            "id": node_ids[name],
            "name": name,
            "element_type": _element_type_for(node.kind, dtype),
            "bbox": {"x": node.box.x, "y": node.box.y, "width": node.box.width, "height": node.box.height},
        }
        if node.kind == RECTANGLE and dtype == DiagramType.CLASS:
            # OCR cannot read class members; attributes/methods stay empty and
            # compare-code (Story 3.4) must report that honestly (not vacuous).
            entry["element_kind"] = "class"
            entry["attributes"] = []
        if dtype == DiagramType.ACTIVITY:
            entry["node_type"] = _activity_node_type(node.kind, name, is_root, is_sink)
        if dtype == DiagramType.STATE_MACHINE:
            entry["is_initial"], entry["is_final"] = _state_flags(name, is_root, is_sink)
        if node.kind == DIAMOND:
            entry["decision"] = True
        elements.append(entry)
        if dtype == DiagramType.SEQUENCE:
            participants.append({"name": name, "participant_type": "object"})

    # Resolve name-based endpoints to structural ids (kept alongside source/target).
    for rel in relationships:
        rel["source_id"] = node_ids.get(str(rel.get("source")))
        rel["target_id"] = node_ids.get(str(rel.get("target")))

    # Diamonds also surface as decision fragments for activity diagrams.
    if dtype == DiagramType.ACTIVITY:
        for node in nodes:
            if node.kind == DIAMOND:
                fragments.append({"type": "decision", "name": _node_name(node)})

    return ParsedModel(
        diagram_type=dtype,
        participants=participants,
        elements=elements,
        relationships=relationships,
        fragments=fragments,
        flows=[],
        source=UMLModelSource.OCR,
        confidence=confidence,
    )


def _element_type_for(kind: str, dtype: DiagramType) -> str:
    if kind == ELLIPSE:
        return "use_case"
    if kind == DIAMOND:
        return "decision"
    if kind == RECTANGLE:
        return "class" if dtype == DiagramType.CLASS else "node"
    return "node"
