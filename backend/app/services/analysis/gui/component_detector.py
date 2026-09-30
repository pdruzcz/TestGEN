"""GUI component detection + classification — Story 3.8, AC4.

The contour-detection step depends on OpenCV (``cv2``), which is an optional
dependency. When ``cv2`` is unavailable :func:`detect_components` returns an
empty list plus a warning so the pipeline degrades gracefully (AC6).

The *classification* logic (:func:`classify_region`) is deliberately pure
Python — it operates on :class:`BBox` geometry plus any OCR text overlapping a
region — so it stays unit-testable without the heavy CV dependencies.
"""

import logging

from app.models.gui_screenshot import GUIComponentType
from app.services.analysis.gui.models import BBox, DetectedComponent, TextBlock

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE = 0.5

# Heuristic geometric signatures, ordered by specificity. The first rule whose
# predicate matches wins; ``unknown`` is the implicit fallback.
_KEYWORD_BUTTON = (
    "ok",
    "anuluj",
    "zapisz",
    "wyślij",
    "submit",
    "zaloguj",
    "dalej",
    "wstecz",
    "usuń",
    "dodaj",
    "save",
    "cancel",
    "login",
    "delete",
    "add",
    "next",
)
_KEYWORD_MENU = ("plik", "edycja", "widok", "pomoc", "file", "edit", "view", "help", "menu")


def classify_region(
    bbox: BBox, text: str | None = None, *, is_square_marker: bool = False
) -> tuple[GUIComponentType, float]:
    """Classify a single region into a :class:`GUIComponentType` + confidence.

    Pure geometry/text heuristics — no CV dependency. ``is_square_marker`` is a
    hint from the caller that the region is a small filled/outlined square
    (checkbox/radio candidate).
    """
    ar = bbox.aspect_ratio
    area = bbox.area
    label = (text or "").strip().lower()

    # Small square markers -> checkbox / radio.
    if is_square_marker or (area and area < 1200 and 0.7 <= ar <= 1.4):
        return GUIComponentType.CHECKBOX, 0.6

    # Explicit keyword matches take priority over pure geometry.
    if label:
        if any(k in label for k in _KEYWORD_MENU) and ar > 2.5:
            return GUIComponentType.MENU, 0.7
        if any(label == k or label.startswith(k) for k in _KEYWORD_BUTTON):
            return GUIComponentType.BUTTON, 0.8

    # Wide thin bars near the top -> menu / tab strip.
    if ar >= 6.0 and bbox.height <= 48:
        return GUIComponentType.MENU, 0.55

    # Text inputs: wide, short, no/sparse text.
    if 2.5 <= ar <= 12.0 and 18 <= bbox.height <= 70 and not label:
        return GUIComponentType.INPUT, 0.65

    # Dropdowns resemble inputs but tend to be slightly wider with a marker.
    if 3.0 <= ar <= 10.0 and 20 <= bbox.height <= 60 and label and len(label) < 24:
        return GUIComponentType.DROPDOWN, 0.55

    # Compact rectangles with a short centred label -> button.
    if 1.5 <= ar <= 5.0 and 20 <= bbox.height <= 60 and label and len(label) <= 20:
        return GUIComponentType.BUTTON, 0.65

    # Large regions -> table / form / modal container.
    if area >= 60000 and ar < 2.5:
        return GUIComponentType.FORM, 0.5

    return GUIComponentType.UNKNOWN, 0.3


def _text_in_bbox(bbox: BBox, text_blocks: list[TextBlock]) -> str | None:
    """Return the concatenated OCR text whose blocks fall inside ``bbox``."""
    parts: list[str] = []
    for tb in text_blocks:
        if bbox.contains(tb.bbox) or bbox.iou(tb.bbox) > 0.4:
            parts.append(tb.text)
    return " ".join(parts) if parts else None


def _dedup_regions(regions: list[BBox], *, iou_threshold: float = 0.4) -> list[BBox]:
    """Collapse near-duplicate boxes (greedy, by descending area).

    A component drawn with a thick border yields two contours — an inner
    content rect and a slightly larger outer border rect — with high IoU.
    Boxes whose IoU >= ``iou_threshold`` are merged by keeping the larger.
    Genuinely nested-but-distinct components (an input inside a form) have low
    IoU and are preserved.
    """
    ordered = sorted(regions, key=lambda b: b.area, reverse=True)
    kept: list[BBox] = []
    for box in ordered:
        if any(box.iou(k) >= iou_threshold for k in kept):
            continue
        kept.append(box)
    return kept


def _cv2_regions(image) -> list[BBox] | None:
    """Detect candidate regions via OpenCV contours; ``None`` if cv2 missing."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)
        # RETR_LIST (not RETR_EXTERNAL) so nested UI boxes — inputs/buttons drawn
        # inside a form/card — are surfaced; RETR_EXTERNAL returned only the
        # outermost container (Story 2-pdf-ocr verification surfaced this: 1 of
        # ~5 components detected). Near-duplicate border boxes are collapsed by
        # _dedup_regions afterwards.
        contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    except Exception as exc:  # pragma: no cover - depends on system binary
        logger.warning("OpenCV component detection failed: %s", exc)
        return None

    regions: list[BBox] = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 12 or h < 8:
            continue
        if w * h < 200:
            continue
        regions.append(BBox(x=int(x), y=int(y), width=int(w), height=int(h)))
    return _dedup_regions(regions)


class ComponentDetector:
    """Detect and classify GUI components from a decoded image."""

    def detect_components(
        self, image, text_blocks: list[TextBlock] | None = None
    ) -> tuple[list[DetectedComponent], list[str]]:
        """Return ``(components, warnings)``.

        Uses OpenCV contour detection when available, then classifies each
        region with the pure-Python heuristics. When ``cv2`` is unavailable a
        warning is appended and an empty component list returned (AC6).
        """
        text_blocks = text_blocks or []
        warnings: list[str] = []

        regions = _cv2_regions(image)
        if regions is None:
            warnings.append("OpenCV niedostępny — pominięto detekcję komponentów wizualnych.")
            return [], warnings

        components: list[DetectedComponent] = []
        for bbox in regions:
            text = _text_in_bbox(bbox, text_blocks)
            ctype, conf = classify_region(bbox, text)
            if conf < _MIN_CONFIDENCE:
                continue
            components.append(
                DetectedComponent(
                    component_type=ctype,
                    bbox=bbox,
                    confidence=conf,
                    label=text,
                )
            )

        if not components:
            warnings.append("Nie wykryto komponentów GUI o wystarczającej pewności.")
        return components, warnings
