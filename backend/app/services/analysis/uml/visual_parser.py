"""VisualUMLParser — Tier 2 visual UML (SVG/PDF/raster) → ParsedModel (Story 3.1b).

Dispatches to the SVG (text/vector) or raster/PDF (OCR + shape detection) paths
and reduces both to the shared shape → UML mapping. Results always carry
``source = ocr`` and a ``confidence`` score (AC5); acquisition warnings are
surfaced via ``ParsedModel.warnings`` for the orchestrator to log.

The structural parsers (XMI/PlantUML) remain the orchestrator's Tier 1 path;
this class is only invoked for visual formats (see ``is_visual_format``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.uml_diagram import UMLFormat
from app.services.analysis.uml.visual.image_parser import pdf_to_shapes, raster_to_shapes
from app.services.analysis.uml.visual.shapes import build_visual_model
from app.services.analysis.uml.visual.svg_parser import svg_to_shapes

if TYPE_CHECKING:
    from app.services.analysis.uml.parsers.base import ParsedModel

logger = logging.getLogger(__name__)


class VisualUMLParser:
    """Parse visual UML inputs into ``source = ocr`` models."""

    def parse_svg(self, svg_text: str) -> ParsedModel:
        """Parse SVG (vector) directly from text — no binary dependency."""
        shapes, labels, warnings = svg_to_shapes(svg_text)
        model = build_visual_model(shapes, labels)
        model.warnings = warnings
        return model

    def parse_raster(self, image_bytes: bytes) -> ParsedModel:
        """Parse PNG/JPEG via OCR + OpenCV shape detection (graceful degrade)."""
        shapes, labels, warnings = raster_to_shapes(image_bytes)
        model = build_visual_model(shapes, labels)
        model.warnings = warnings
        return model

    def parse_pdf(self, pdf_bytes: bytes) -> ParsedModel:
        """Rasterise PDF page 1 then parse as raster (graceful degrade)."""
        shapes, labels, warnings = pdf_to_shapes(pdf_bytes)
        model = build_visual_model(shapes, labels)
        model.warnings = warnings
        return model

    def parse_bytes(self, data: bytes, fmt: UMLFormat) -> ParsedModel:
        """Dispatch binary visual payloads (PDF/raster) by format."""
        if fmt == UMLFormat.PDF:
            return self.parse_pdf(data)
        return self.parse_raster(data)
