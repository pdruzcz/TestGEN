"""Visual UML parsing (Tier 2) — SVG / PDF / raster via OCR + shape inference.

Story 3.1b. See :mod:`visual.shapes` for the format-agnostic mapping and
:mod:`visual.svg_parser` / :mod:`visual.image_parser` for acquisition.
"""

from app.services.analysis.uml.visual.shapes import (
    Box,
    Shape,
    TextLabel,
    build_visual_model,
    classify_visual_diagram_type,
)

__all__ = [
    "Box",
    "Shape",
    "TextLabel",
    "build_visual_model",
    "classify_visual_diagram_type",
]
