"""Spatial layout analysis — Story 3.8, AC5.

Builds a nesting hierarchy (:class:`LayoutTreeNode`) from detected components
and OCR text blocks using pure bbox geometry, so it is fully unit-testable
without any CV/OCR dependency. It also assigns nearby OCR labels to unlabeled
components (e.g. a caption sitting just left of / above an input).
"""

from app.models.gui_screenshot import GUIComponentType
from app.services.analysis.gui.models import BBox, DetectedComponent, LayoutTreeNode, TextBlock

# Max gap (px) between a label and the component it annotates.
_LABEL_GAP = 24


def _nearest_label(comp: DetectedComponent, text_blocks: list[TextBlock]) -> str | None:
    """Find an OCR label to the left of or above ``comp`` within ``_LABEL_GAP``."""
    cx, cy = comp.bbox.center
    best: tuple[float, str] | None = None
    for tb in text_blocks:
        if comp.bbox.contains(tb.bbox):
            continue
        tx, ty = tb.bbox.center
        # Label to the left, vertically aligned.
        left_gap = comp.bbox.x - tb.bbox.x2
        if 0 <= left_gap <= _LABEL_GAP and abs(ty - cy) <= comp.bbox.height:
            dist = left_gap + abs(ty - cy)
            if best is None or dist < best[0]:
                best = (dist, tb.text)
            continue
        # Label above, horizontally aligned.
        top_gap = comp.bbox.y - tb.bbox.y2
        if 0 <= top_gap <= _LABEL_GAP and abs(tx - cx) <= comp.bbox.width:
            dist = top_gap + abs(tx - cx)
            if best is None or dist < best[0]:
                best = (dist, tb.text)
    return best[1] if best else None


def _node_for(comp: DetectedComponent) -> LayoutTreeNode:
    return LayoutTreeNode(type=comp.component_type.value, label=comp.label, bbox=comp.bbox)


class LayoutAnalyzer:
    """Reconstruct a spatial hierarchy + component relations."""

    def analyze(
        self,
        components: list[DetectedComponent],
        text_blocks: list[TextBlock] | None = None,
        image_size: tuple[int, int] | None = None,
    ) -> tuple[LayoutTreeNode, list[str]]:
        """Return ``(layout_tree, warnings)``.

        Assigns nearby labels to unlabeled components, then nests components by
        bbox containment under a synthetic ``screen`` root.
        """
        text_blocks = text_blocks or []
        warnings: list[str] = []

        # Assign labels to components that lack one.
        for comp in components:
            if not comp.label:
                comp.label = _nearest_label(comp, text_blocks)

        width, height = image_size or (0, 0)
        root = LayoutTreeNode(
            type="screen",
            label=None,
            bbox=BBox(x=0, y=0, width=width, height=height) if image_size else None,
        )

        if not components:
            warnings.append("Brak komponentów do zbudowania drzewa układu.")
            return root, warnings

        # Nest by containment: largest areas become parents. Sort descending so
        # parents are placed before their children.
        ordered = sorted(components, key=lambda c: c.bbox.area, reverse=True)
        placed: list[tuple[DetectedComponent, LayoutTreeNode]] = []
        for comp in ordered:
            node = _node_for(comp)
            parent_node = root
            best_area: int | None = None
            for pcomp, pnode in placed:
                if (
                    pcomp.bbox.contains(comp.bbox)
                    and pcomp.bbox.area > comp.bbox.area
                    and (best_area is None or pcomp.bbox.area < best_area)
                ):
                    best_area = pcomp.bbox.area
                    parent_node = pnode
            parent_node.children.append(node)
            placed.append((comp, node))

        return root, warnings

    def detect_relations(self, components: list[DetectedComponent]) -> list[dict]:
        """Return simple label->input / button->form relations (AC5)."""
        relations: list[dict] = []
        forms = [c for c in components if c.component_type == GUIComponentType.FORM]
        for comp in components:
            if comp.component_type == GUIComponentType.BUTTON:
                for form in forms:
                    if form.bbox.contains(comp.bbox):
                        relations.append(
                            {"type": "button-form", "button": comp.label, "form": form.label}
                        )
            if comp.component_type == GUIComponentType.INPUT and comp.label:
                relations.append({"type": "label-input", "label": comp.label})
        return relations
