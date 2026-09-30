"""Raster image / PDF → shapes for visual UML parsing (Story 3.1b, AC2/AC3).

Reuses the GUI module's :class:`~app.services.analysis.gui.ocr_service.OCRService`
for text extraction and applies OpenCV shape detection for UML nodes/edges. The
heavy dependencies (``cv2``/``numpy``/``PIL`` for raster, ``fitz`` for PDF
rasterisation) are **optional**: when any is missing the path degrades
gracefully — no shapes, an explanatory warning — mirroring the GUI pipeline
(AC6 of Story 3.8). The shape → UML mapping itself is format-agnostic and lives
in :mod:`visual.shapes`, so the degraded path still produces a valid (empty)
model.

UML shape semantics from contours:

* 4-vertex polygon, axis-aligned → rectangle (class)
* 4-vertex polygon, rhombus      → diamond (decision)
* large smooth contour           → ellipse (use case)
* Hough line segment             → connector (arrow/relationship)
"""

from __future__ import annotations

import logging

from app.services.analysis.gui.ocr_service import OCRService
from app.services.analysis.uml.visual.shapes import (
    ARROW,
    DIAMOND,
    ELLIPSE,
    RECTANGLE,
    Box,
    Shape,
    TextLabel,
)

logger = logging.getLogger(__name__)


def _decode_image(image_bytes: bytes):
    """Decode raw image bytes into an OpenCV/numpy image, or ``None``.

    Returns ``None`` when neither OpenCV nor PIL is importable or decoding
    fails, so callers can degrade gracefully.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img if img is not None else None
    except Exception as exc:  # pragma: no cover - depends on system libs
        logger.warning("Image decode failed: %s", exc)
        return None


def _detect_shapes_cv2(image) -> list[Shape]:  # pragma: no cover - requires cv2
    """Detect UML node shapes + connectors via OpenCV (no-op without cv2)."""
    try:
        import cv2
    except ImportError:
        return []
    shapes: list[Shape] = []
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    except Exception as exc:
        logger.warning("OpenCV shape detection failed: %s", exc)
        return []

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 16 or h < 12 or w * h < 400:
            continue
        approx = cv2.approxPolyDP(cnt, 0.04 * cv2.arcLength(cnt, True), True)
        box = Box(x=float(x), y=float(y), width=float(w), height=float(h))
        if len(approx) == 4:
            pts = [(float(p[0][0]), float(p[0][1])) for p in approx]
            kind = DIAMOND if _is_rhombus(pts, box) else RECTANGLE
            shapes.append(Shape(kind=kind, box=box, confidence=0.8 if kind == RECTANGLE else 0.6))
        elif len(approx) > 6:
            shapes.append(Shape(kind=ELLIPSE, box=box, confidence=0.7))

    # Connectors via probabilistic Hough line transform.
    try:
        lines = cv2.HoughLinesP(edges, 1, 3.14159 / 180, threshold=40, minLineLength=30, maxLineGap=10)
    except Exception:
        lines = None
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            box = Box(x=float(min(x1, x2)), y=float(min(y1, y2)), width=float(abs(x2 - x1)), height=float(abs(y2 - y1)))
            shapes.append(
                Shape(kind=ARROW, box=box, start=(float(x1), float(y1)), end=(float(x2), float(y2)), confidence=0.6)
            )
    return shapes


def _is_rhombus(pts: list[tuple[float, float]], box: Box) -> bool:  # pragma: no cover
    """Heuristic: 4 points with none sharing the bounding-box corners → diamond."""
    corners = {
        (box.x, box.y),
        (box.x + box.width, box.y),
        (box.x, box.y + box.height),
        (box.x + box.width, box.y + box.height),
    }
    matches = sum(1 for p in pts if any(abs(p[0] - c[0]) < 4 and abs(p[1] - c[1]) < 4 for c in corners))
    return matches == 0


def raster_to_shapes(image_bytes: bytes) -> tuple[list[Shape], list[TextLabel], list[str]]:
    """Extract ``(shapes, labels, warnings)`` from raster image bytes."""
    warnings: list[str] = []
    image = _decode_image(image_bytes)
    if image is None:
        warnings.append("Dekodowanie obrazu niedostępne (cv2/PIL) — pominięto analizę rastrowego UML.")
        return [], [], warnings

    text_blocks, ocr_warnings = OCRService().extract_text(image)
    warnings.extend(ocr_warnings)
    labels = [
        TextLabel(
            text=tb.text,
            x=tb.bbox.x + tb.bbox.width / 2.0,
            y=tb.bbox.y + tb.bbox.height / 2.0,
            confidence=tb.confidence,
        )
        for tb in text_blocks
    ]

    shapes = _detect_shapes_cv2(image)
    if not shapes:
        warnings.append("Nie wykryto kształtów UML na obrazie rastrowym.")
    return shapes, labels, warnings


def pdf_to_shapes(pdf_bytes: bytes) -> tuple[list[Shape], list[TextLabel], list[str]]:
    """Rasterise the first PDF page then extract shapes (graceful degrade)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return (
            [],
            [],
            ["Rasteryzacja PDF niedostępna (PyMuPDF/fitz) — pominięto analizę PDF."],
        )
    try:  # pragma: no cover - requires PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        image_bytes = pix.tobytes("png")
        doc.close()
        return raster_to_shapes(image_bytes)
    except Exception as exc:  # pragma: no cover
        logger.warning("PDF rasterisation failed: %s", exc)
        return [], [], [f"Rasteryzacja PDF nie powiodła się: {exc}"]
