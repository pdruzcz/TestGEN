"""OCR text extraction for GUI screenshots — Story 3.8, AC3.

Tesseract (``pytesseract``) is the primary engine with EasyOCR as a fallback.
Both are optional dependencies: when neither is importable the service degrades
gracefully, returning no text blocks plus a warning rather than raising, so the
overall pipeline can still produce partial results (AC6).
"""

import logging

from app.services.analysis.gui.models import BBox, TextBlock

logger = logging.getLogger(__name__)

_MIN_CONFIDENCE = 0.3


def _tesseract_blocks(image) -> list[TextBlock] | None:
    """Run Tesseract; return blocks or ``None`` if the engine is unavailable."""
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError:
        return None

    try:
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
    except Exception as exc:  # pragma: no cover - depends on system binary
        logger.warning("Tesseract OCR failed: %s", exc)
        return None

    blocks: list[TextBlock] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i]) / 100.0
        except (ValueError, TypeError):
            conf = 0.0
        if conf < _MIN_CONFIDENCE:
            continue
        blocks.append(
            TextBlock(
                text=text,
                bbox=BBox(
                    x=int(data["left"][i]),
                    y=int(data["top"][i]),
                    width=int(data["width"][i]),
                    height=int(data["height"][i]),
                ),
                confidence=conf,
            )
        )
    return blocks


def _easyocr_blocks(image) -> list[TextBlock] | None:
    """Run EasyOCR fallback; return blocks or ``None`` if unavailable."""
    try:
        import easyocr
    except ImportError:
        return None

    try:
        reader = easyocr.Reader(["pl", "en"], gpu=False)
        results = reader.readtext(image)
    except Exception as exc:  # pragma: no cover - heavy optional dependency
        logger.warning("EasyOCR failed: %s", exc)
        return None

    blocks: list[TextBlock] = []
    for box, text, conf in results:
        text = (text or "").strip()
        if not text:
            continue
        xs = [int(p[0]) for p in box]
        ys = [int(p[1]) for p in box]
        blocks.append(
            TextBlock(
                text=text,
                bbox=BBox(x=min(xs), y=min(ys), width=max(xs) - min(xs), height=max(ys) - min(ys)),
                confidence=float(conf),
            )
        )
    return blocks


class OCRService:
    """Extract text blocks from a decoded image (numpy array)."""

    def extract_text(self, image) -> tuple[list[TextBlock], list[str]]:
        """Return ``(text_blocks, warnings)``.

        Tries Tesseract first, then EasyOCR. If both engines are unavailable or
        return nothing, an explanatory warning is appended (AC6).
        """
        warnings: list[str] = []

        blocks = _tesseract_blocks(image)
        if blocks is None:
            warnings.append("Tesseract OCR niedostępny — pominięto podstawowy silnik OCR.")
            blocks = _easyocr_blocks(image)
            if blocks is None:
                warnings.append("EasyOCR niedostępny — analiza tekstu pominięta.")
                return [], warnings
        elif not blocks:
            fallback = _easyocr_blocks(image)
            if fallback:
                blocks = fallback

        if not blocks:
            warnings.append("Nie wykryto czytelnego tekstu na zrzucie ekranu.")
        return blocks, warnings
