"""GUI analysis orchestrator — Story 3.8, AC1-AC6.

Runs the screenshot analysis pipeline sequentially: image decode -> OCR ->
component detection -> layout analysis. Each stage degrades gracefully when its
optional heavy dependency (cv2 / pytesseract / PIL / numpy) is missing, so the
orchestrator always returns a :class:`GUIAnalysisOutput` with whatever partial
results were obtained plus accumulated warnings (AC6).
"""

import logging
import time

from app.services.analysis.gui.component_detector import ComponentDetector
from app.services.analysis.gui.layout_analyzer import LayoutAnalyzer
from app.services.analysis.gui.models import GUIAnalysisOutput
from app.services.analysis.gui.ocr_service import OCRService

logger = logging.getLogger(__name__)


def decode_image(data: bytes) -> tuple[object | None, tuple[int, int] | None, str | None]:
    """Decode raw image bytes into a numpy array.

    Tries OpenCV first, then Pillow. Returns ``(image, (width, height), warning)``
    where ``image`` is ``None`` if no decoder is available.
    """
    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(data, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is not None:
            h, w = image.shape[:2]
            return image, (int(w), int(h)), None
    except ImportError:
        pass
    except Exception as exc:  # pragma: no cover - depends on binary
        logger.warning("OpenCV image decode failed: %s", exc)

    try:
        import io

        import numpy as np
        from PIL import Image

        with Image.open(io.BytesIO(data)) as pil_img:
            rgb = pil_img.convert("RGB")
            image = np.array(rgb)
            h, w = image.shape[:2]
            return image, (int(w), int(h)), None
    except ImportError:
        return None, None, "Brak bibliotek do dekodowania obrazu (cv2/PIL) — analiza pominięta."
    except Exception as exc:
        logger.warning("Pillow image decode failed: %s", exc)
        return None, None, f"Nie udało się zdekodować obrazu: {exc}"


class GUIAnalyzerOrchestrator:
    """Coordinate OCR, component detection and layout analysis."""

    def __init__(
        self,
        ocr_service: OCRService | None = None,
        component_detector: ComponentDetector | None = None,
        layout_analyzer: LayoutAnalyzer | None = None,
    ) -> None:
        self._ocr = ocr_service or OCRService()
        self._detector = component_detector or ComponentDetector()
        self._layout = layout_analyzer or LayoutAnalyzer()

    def analyze(self, image_bytes: bytes) -> GUIAnalysisOutput:
        """Run the full pipeline over raw image bytes; never raises (AC6)."""
        start = time.perf_counter()
        warnings: list[str] = []

        image, image_size, decode_warning = decode_image(image_bytes)
        if decode_warning:
            warnings.append(decode_warning)
        if image is None:
            return GUIAnalysisOutput(
                warnings=warnings,
                processing_time_ms=int((time.perf_counter() - start) * 1000),
            )

        text_blocks, ocr_warnings = self._ocr.extract_text(image)
        warnings.extend(ocr_warnings)

        components, comp_warnings = self._detector.detect_components(image, text_blocks)
        warnings.extend(comp_warnings)

        layout_tree, layout_warnings = self._layout.analyze(components, text_blocks, image_size)
        warnings.extend(layout_warnings)

        return GUIAnalysisOutput(
            text_blocks=text_blocks,
            components=components,
            layout_tree=layout_tree,
            warnings=warnings,
            processing_time_ms=int((time.perf_counter() - start) * 1000),
        )
