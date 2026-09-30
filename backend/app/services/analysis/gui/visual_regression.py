"""Visual regression engine — Epic 3, Story 3.10.

Compares two analysed GUI screenshots (baseline vs comparison) and produces:

- a pixel-diff percentage (SSIM via ``scikit-image`` when available, else an
  absolute-difference fallback),
- a per-component *semantic* delta (added / removed / moved / text / color),
- a classification of each change into one of six ``change_type`` values and one
  of three ``severity`` levels,
- an optional annotated ``diff_image`` (OpenCV overlay when available),
- an overall :class:`ComparisonStatus`.

Heavy imaging dependencies (``numpy``, ``scikit-image``, ``cv2``) are optional;
when missing the engine degrades gracefully (pixel diff skipped, diff-image not
generated), keeping the pure-Python semantic diff + classification testable.
"""

import logging
from dataclasses import dataclass, field

from app.models.gui_screenshot import GUIComponentType
from app.models.visual_regression import ComparisonStatus
from app.services.analysis.gui.flow_reconstructor import _label_similarity, match_components
from app.services.analysis.gui.models import BBox, DetectedComponent

logger = logging.getLogger(__name__)

# change_type values (AC-3).
CHANGE_LAYOUT = "layout_change"
CHANGE_TEXT = "text_change"
CHANGE_COLOR = "color_change"
CHANGE_ADDED = "element_added"
CHANGE_REMOVED = "element_removed"
CHANGE_MOVED = "element_moved"

# severity values (AC-4).
SEVERITY_BREAKING = "breaking"
SEVERITY_VISUAL = "visual"
SEVERITY_MINOR = "minor"

# Default thresholds.
_DEFAULT_PIXEL_THRESHOLD = 0.02  # fraction; below this -> MATCH
_MOVE_THRESHOLD_PX = 5
_LAYOUT_SHIFT_PX = 40
_LABEL_SAME = 0.85  # similarity above which two labels are "the same"

# Component types that, when removed, are considered breaking.
_BREAKING_CONTAINERS = {GUIComponentType.FORM, GUIComponentType.MENU, GUIComponentType.BUTTON}


@dataclass
class ComponentDelta:
    component_type: str
    change_type: str
    severity: str
    description: str
    baseline_bbox: dict | None = None
    comparison_bbox: dict | None = None
    confidence: float = 0.0


@dataclass
class VisualComparisonResult:
    pixel_diff_percentage: float
    status: ComparisonStatus
    deltas: list[ComponentDelta] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    diff_image: object | None = None  # encoded PNG bytes when generated

    def semantic_diff_payload(self) -> list[dict]:
        return [
            {
                "component_type": d.component_type,
                "change_type": d.change_type,
                "severity": d.severity,
                "description": d.description,
                "baseline_bbox": d.baseline_bbox,
                "comparison_bbox": d.comparison_bbox,
                "confidence": d.confidence,
            }
            for d in self.deltas
        ]


def compute_pixel_diff(baseline, comparison) -> tuple[float, str | None]:
    """Return ``(pixel_diff_percentage, warning)`` in ``[0, 100]``.

    Uses SSIM (``1 - ssim``) when ``scikit-image`` is available, otherwise an
    absolute-difference ratio. Returns ``(0.0, warning)`` when imaging deps are
    missing or the images cannot be compared.
    """
    if baseline is None or comparison is None:
        return 0.0, "Brak danych obrazu - pominięto pixel diff."
    try:
        import numpy as np
    except ImportError:
        return 0.0, "Brak numpy - pominięto pixel diff (porównanie tylko semantyczne)."

    a = np.asarray(baseline)
    b = np.asarray(comparison)
    if a.shape != b.shape:
        return 0.0, "Różne wymiary obrazów - pominięto pixel diff."

    try:
        from skimage.metrics import structural_similarity as ssim

        gray_a = a.mean(axis=2) if a.ndim == 3 else a
        gray_b = b.mean(axis=2) if b.ndim == 3 else b
        score = ssim(gray_a, gray_b, data_range=255)
        return float(max(0.0, 1.0 - score)) * 100.0, None
    except ImportError:
        delta = np.abs(a.astype("int16") - b.astype("int16"))
        if delta.ndim == 3:
            delta = delta.max(axis=2)
        changed = (delta > 30).sum()
        total = delta.size if delta.size else 1
        return float(changed) / float(total) * 100.0, None


def _bbox_shift(a: BBox, b: BBox) -> float:
    (ax, ay), (bx, by) = a.center, b.center
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _classify_matched(
    base: DetectedComponent, comp: DetectedComponent, pixel_pct: float
) -> ComponentDelta | None:
    """Classify a change between two matched components, or ``None`` if identical."""
    shift = _bbox_shift(base.bbox, comp.bbox)
    label_sim = _label_similarity(base.label, comp.label)
    text_changed = bool(base.label or comp.label) and label_sim < _LABEL_SAME

    if text_changed:
        severity = SEVERITY_VISUAL if pixel_pct >= 5 else SEVERITY_MINOR
        return ComponentDelta(
            component_type=base.component_type.value,
            change_type=CHANGE_TEXT,
            severity=severity,
            description=f"Zmiana tekstu „{base.label or '—'}” -> „{comp.label or '—'}”.",
            baseline_bbox=base.bbox.to_dict(),
            comparison_bbox=comp.bbox.to_dict(),
            confidence=0.7,
        )

    if shift > _MOVE_THRESHOLD_PX:
        is_layout = shift >= _LAYOUT_SHIFT_PX
        change_type = CHANGE_LAYOUT if is_layout else CHANGE_MOVED
        if is_layout and pixel_pct > 30:
            severity = SEVERITY_BREAKING
        elif shift < _MOVE_THRESHOLD_PX:
            severity = SEVERITY_MINOR
        else:
            severity = SEVERITY_VISUAL
        return ComponentDelta(
            component_type=base.component_type.value,
            change_type=change_type,
            severity=severity,
            description=f"Przesunięcie elementu o {shift:.0f}px.",
            baseline_bbox=base.bbox.to_dict(),
            comparison_bbox=comp.bbox.to_dict(),
            confidence=0.65,
        )

    return None


def compute_component_delta(
    baseline_components: list[DetectedComponent],
    comparison_components: list[DetectedComponent],
    pixel_pct: float = 0.0,
) -> list[ComponentDelta]:
    """Compute the per-component semantic delta (AC-2, AC-3, AC-4)."""
    deltas: list[ComponentDelta] = []
    matches = match_components(baseline_components, comparison_components)
    matched_base = {m.index_a for m in matches}
    matched_comp = {m.index_b for m in matches}

    # Removed: present on baseline, unmatched on comparison.
    for i, base in enumerate(baseline_components):
        if i in matched_base:
            continue
        breaking = base.component_type in _BREAKING_CONTAINERS
        deltas.append(
            ComponentDelta(
                component_type=base.component_type.value,
                change_type=CHANGE_REMOVED,
                severity=SEVERITY_BREAKING if breaking else SEVERITY_VISUAL,
                description=f"Usunięto element „{base.label or base.component_type.value}”.",
                baseline_bbox=base.bbox.to_dict(),
                comparison_bbox=None,
                confidence=0.7,
            )
        )

    # Added: present on comparison, unmatched on baseline.
    for j, comp in enumerate(comparison_components):
        if j in matched_comp:
            continue
        deltas.append(
            ComponentDelta(
                component_type=comp.component_type.value,
                change_type=CHANGE_ADDED,
                severity=SEVERITY_VISUAL,
                description=f"Dodano element „{comp.label or comp.component_type.value}”.",
                baseline_bbox=None,
                comparison_bbox=comp.bbox.to_dict(),
                confidence=0.7,
            )
        )

    # Matched: detect moves / text changes.
    for m in matches:
        delta = _classify_matched(
            baseline_components[m.index_a], comparison_components[m.index_b], pixel_pct
        )
        if delta is not None:
            deltas.append(delta)

    return deltas


def classify_status(pixel_pct: float, deltas: list[ComponentDelta], pixel_threshold: float) -> ComparisonStatus:
    """Derive the overall comparison status (AC-7)."""
    has_breaking = any(d.severity == SEVERITY_BREAKING for d in deltas)
    if has_breaking or pixel_pct >= 30:
        return ComparisonStatus.MAJOR_DIFF
    if pixel_pct < pixel_threshold * 100.0 and not deltas:
        return ComparisonStatus.MATCH
    return ComparisonStatus.MINOR_DIFF


_SEVERITY_BGR = {
    SEVERITY_BREAKING: (0, 0, 255),
    SEVERITY_VISUAL: (0, 255, 255),
    SEVERITY_MINOR: (0, 255, 0),
}


def generate_diff_image(baseline, deltas: list[ComponentDelta]) -> tuple[object | None, str | None]:
    """Render an annotated diff image (OpenCV) or ``(None, warning)`` if unavailable."""
    if baseline is None:
        return None, None
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None, "Brak cv2/numpy - nie wygenerowano obrazu różnicy."

    try:
        canvas = (np.asarray(baseline).astype("float32") * 0.6).astype("uint8").copy()
        if canvas.ndim == 2:
            canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
        for d in deltas:
            box = d.comparison_bbox or d.baseline_bbox
            if not box:
                continue
            color = _SEVERITY_BGR.get(d.severity, (255, 255, 255))
            x, y, w, h = box["x"], box["y"], box["width"], box["height"]
            cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                canvas, d.change_type, (x, max(0, y - 4)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA,
            )
        ok, buf = cv2.imencode(".png", canvas)
        if not ok:
            return None, "Kodowanie obrazu różnicy nie powiodło się."
        return buf.tobytes(), None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Diff image generation failed: %s", exc)
        return None, f"Generowanie obrazu różnicy nie powiodło się: {exc}"


class VisualRegressionEngine:
    """Coordinate pixel diff + semantic diff + classification (AC-1, AC-2, AC-7)."""

    def __init__(self, pixel_threshold: float = _DEFAULT_PIXEL_THRESHOLD):
        self._pixel_threshold = pixel_threshold

    def compare(
        self,
        baseline_image,
        comparison_image,
        baseline_components: list[DetectedComponent],
        comparison_components: list[DetectedComponent],
    ) -> VisualComparisonResult:
        warnings: list[str] = []
        pixel_pct, pixel_warning = compute_pixel_diff(baseline_image, comparison_image)
        if pixel_warning:
            warnings.append(pixel_warning)

        deltas = compute_component_delta(baseline_components, comparison_components, pixel_pct)
        status = classify_status(pixel_pct, deltas, self._pixel_threshold)

        diff_image, diff_warning = generate_diff_image(baseline_image, deltas)
        if diff_warning:
            warnings.append(diff_warning)

        return VisualComparisonResult(
            pixel_diff_percentage=round(pixel_pct, 4),
            status=status,
            deltas=deltas,
            warnings=warnings,
            diff_image=diff_image,
        )
