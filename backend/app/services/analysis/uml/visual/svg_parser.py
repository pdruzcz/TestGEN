"""SVG → shapes extraction for visual UML parsing (Story 3.1b, AC3).

SVG is a vector format carried as text (``raw_content``), so this path needs no
binary/CV dependency — shapes are read directly from the DOM via ``defusedxml``.
This makes SVG the highest-fidelity and fully unit-testable Tier 2 input.

Recognised SVG primitives → UML shapes:

* ``<rect>``            → rectangle (class)
* ``<ellipse>``/``<circle>`` → ellipse (use case)
* ``<polygon>`` (4 pts) → diamond (decision) when the points form a rhombus,
                          otherwise rectangle
* ``<line>``/``<path>`` → connector; ``marker-end`` marks it as a directed arrow
* ``<text>``            → text label (bound to the nearest node later)
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from defusedxml import ElementTree

from app.services.analysis.uml.visual.shapes import (
    ARROW,
    DIAMOND,
    ELLIPSE,
    LINE,
    RECTANGLE,
    Box,
    Shape,
    TextLabel,
)

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

logger = logging.getLogger(__name__)

_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
_POINT_PAIR_RE = re.compile(rf"{_NUM}\s*,?\s*{_NUM}")
_PATH_NUMS_RE = re.compile(_NUM)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _f(value: str | None, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _is_diamond(points: list[tuple[float, float]]) -> bool:
    """True when 4 points form a rhombus sitting on edge midpoints (not corners).

    A rectangle's vertices coincide with the bounding-box corners; a diamond's
    vertices sit on the edge midpoints, so none touches a corner.
    """
    if len(points) != 4:
        return False
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    tol = max(2.0, 0.05 * max(x1 - x0, y1 - y0))
    corner_hits = sum(1 for p in points if any(abs(p[0] - c[0]) < tol and abs(p[1] - c[1]) < tol for c in corners))
    return corner_hits == 0


def _box_from_points(points: list[tuple[float, float]]) -> Box:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return Box(x=x0, y=y0, width=max(0.0, x1 - x0), height=max(0.0, y1 - y0))


def _parse_points(raw: str) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for m in _POINT_PAIR_RE.finditer(raw):
        nums = [float(n) for n in _PATH_NUMS_RE.findall(m.group(0))]
        if len(nums) >= 2:
            points.append((nums[0], nums[1]))
    return points


def _shape_from_rect(node: Element) -> Shape:
    box = Box(
        x=_f(node.get("x")),
        y=_f(node.get("y")),
        width=_f(node.get("width")),
        height=_f(node.get("height")),
    )
    return Shape(kind=RECTANGLE, box=box)


def _shape_from_ellipse(node: Element) -> Shape:
    cx = _f(node.get("cx"))
    cy = _f(node.get("cy"))
    if _local(node.tag) == "circle":
        rx = ry = _f(node.get("r"))
    else:
        rx = _f(node.get("rx"))
        ry = _f(node.get("ry"))
    return Shape(kind=ELLIPSE, box=Box(x=cx - rx, y=cy - ry, width=2 * rx, height=2 * ry))


def _shape_from_polygon(node: Element) -> Shape:
    points = _parse_points(node.get("points", ""))
    if not points:
        return Shape(kind=RECTANGLE, box=Box(0, 0, 0, 0))
    kind = DIAMOND if _is_diamond(points) else RECTANGLE
    return Shape(kind=kind, box=_box_from_points(points))


def _shape_from_line(node: Element, kind: str) -> Shape:
    x1, y1 = _f(node.get("x1")), _f(node.get("y1"))
    x2, y2 = _f(node.get("x2")), _f(node.get("y2"))
    box = Box(x=min(x1, x2), y=min(y1, y2), width=abs(x2 - x1), height=abs(y2 - y1))
    return Shape(kind=kind, box=box, start=(x1, y1), end=(x2, y2))


def _shape_from_path(node: Element, kind: str) -> Shape:
    d = node.get("d", "")
    nums = [float(n) for n in _PATH_NUMS_RE.findall(d)]
    if len(nums) < 4:
        return Shape(kind=kind, box=Box(0, 0, 0, 0))
    start = (nums[0], nums[1])
    end = (nums[-2], nums[-1])
    xs, ys = nums[0::2], nums[1::2]
    box = Box(x=min(xs), y=min(ys), width=max(xs) - min(xs), height=max(ys) - min(ys))
    return Shape(kind=kind, box=box, start=start, end=end)


def _connector_kind(node: Element) -> str:
    return ARROW if node.get("marker-end") else LINE


def svg_to_shapes(svg_text: str) -> tuple[list[Shape], list[TextLabel], list[str]]:
    """Parse SVG text into ``(shapes, labels, warnings)``.

    Malformed SVG yields no shapes plus a warning rather than raising, so the
    orchestrator can mark the diagram gracefully.
    """
    warnings: list[str] = []
    try:
        root = ElementTree.fromstring(svg_text)
    except Exception as exc:  # defusedxml raises on malformed XML.
        logger.warning("SVG parse failed: %s", exc)
        return [], [], [f"Nieprawidłowy SVG: {exc}"]

    shapes: list[Shape] = []
    labels: list[TextLabel] = []

    # Collect every element inside <defs> (gradients, markers, symbol paths) so
    # definition primitives are not mistaken for diagram shapes.
    skip: set[Element] = set()
    for defs in root.iter():
        if _local(defs.tag) == "defs":
            skip.update(defs.iter())

    for node in root.iter():
        if node in skip:
            continue
        local = _local(node.tag)
        if local == "rect":
            shapes.append(_shape_from_rect(node))
        elif local in ("ellipse", "circle"):
            shapes.append(_shape_from_ellipse(node))
        elif local == "polygon":
            shapes.append(_shape_from_polygon(node))
        elif local == "line":
            shapes.append(_shape_from_line(node, _connector_kind(node)))
        elif local == "path":
            shapes.append(_shape_from_path(node, _connector_kind(node)))
        elif local == "text":
            text = (node.text or "").strip()
            if text:
                labels.append(TextLabel(text=text, x=_f(node.get("x")), y=_f(node.get("y"))))

    if not shapes:
        warnings.append("SVG nie zawiera rozpoznawalnych kształtów UML.")
    return shapes, labels, warnings
