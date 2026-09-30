"""Image-gated golden test — scanned-PDF OCR (Epic 2, Story 2-pdf-ocr-domknięcie).

End-to-end verification that a scanned PDF (no text layer) is OCR-ified for real
once the imaging stack — PyMuPDF rasteriser + Tesseract via the shared
``OCRService`` — is present. Collected by the ``golden-regression`` CI stage,
which installs ``.[dev,imaging]`` and the ``tesseract-ocr`` binary, so the OCR
path is actually exercised (previously every image-gated test was a *silent
skip* that never validated the rasterise→recognise pipeline — see Story
2-pdf-ocr verification). On minimal environments these skip cleanly via
``importorskip`` rather than failing the suite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.services.analysis.document.pdf_parser import PDFParser

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.golden

# The exact marker emitted by the legacy stub — must never appear in output.
PLACEHOLDER_MARKER = "[OCR extracted text from"


def _make_scanned_pdf(path: Path, text: str = "Wymagania funkcjonalne systemu") -> Path:
    """Image-only PDF (no text layer) — emulates a scanned document."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (2480, 3508), "white")  # A4 @ 300dpi
    draw = ImageDraw.Draw(img)
    font = None
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            font = ImageFont.truetype(name, 110)
            break
        except OSError:
            continue
    if font is None:  # Pillow >= 10.1 supports a scaled default font
        font = ImageFont.load_default(size=110)
    draw.text((180, 400), text, fill="black", font=font)
    # resolution=300 → A4-sized PDF page; without it PIL saves at 72 DPI, making
    # the page ~35x49" so the 300-DPI rasterisation explodes to a decompression
    # bomb. 300 keeps the page A4 and the rasterised render a sane ~8.7 Mpx.
    img.save(str(path), "PDF", resolution=300.0)
    return path


def test_extract_text_with_ocr_delegates_to_ocr_service(tmp_path):
    """AC2 — the scanned-PDF path reuses gui.ocr_service.OCRService (no dup)."""
    pytest.importorskip("fitz")  # rasteriser required for the real path

    class _FakeBlock:
        def __init__(self, t):
            self.text = t

    captured: dict = {}

    class _FakeOCRService:
        def __init__(self, *args, **kwargs):
            captured["instantiated"] = True

        def extract_text(self, image):
            captured["called"] = True
            return [_FakeBlock("wykryty tekst OCR"), _FakeBlock("druga linia")], []

    pdf = _make_scanned_pdf(tmp_path / "scan.pdf")
    with patch("app.services.analysis.gui.ocr_service.OCRService", _FakeOCRService):
        text, applied = PDFParser(pdf)._extract_text_with_ocr(pdf)

    assert captured.get("instantiated") is True
    assert captured.get("called") is True
    assert applied is True
    assert "wykryty tekst OCR" in text
    assert "druga linia" in text
    assert PLACEHOLDER_MARKER not in text


def test_scanned_pdf_real_ocr(tmp_path):
    """AC1/AC4 — a scanned PDF is OCR-ified end-to-end; has_ocr is honest."""
    pytest.importorskip("fitz")
    pytest.importorskip("pytesseract")
    # Gate na BINARKĘ tesseract, nie tylko pakiet Pythona: bez niej na PATH
    # pytesseract podnosi TesseractNotFoundError w trakcie parsowania, przez
    # co ``has_ocr`` jest uczciwie False i asercja failuje zamiast się
    # czysto skipować (image-gated z reason — wzorzec cv2 w tym repo).
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("tesseract binary not on PATH (install Tesseract-OCR or extend PATH)")
    pdf = _make_scanned_pdf(tmp_path / "scan.pdf", "Wymagania funkcjonalne systemu")
    parsed = PDFParser(pdf).parse()
    assert parsed.metadata["has_ocr"] is True
    assert PLACEHOLDER_MARKER not in parsed.raw_text
    assert len(parsed.raw_text.strip()) > 0
    assert parsed.sections


def test_ocr_text_never_placeholder(tmp_path):
    """AC1 regression — OCR output is never the legacy stub placeholder."""
    pytest.importorskip("fitz")
    pytest.importorskip("pytesseract")
    pdf = _make_scanned_pdf(tmp_path / "scan.pdf")
    text, applied = PDFParser(pdf)._extract_text_with_ocr(pdf)
    assert PLACEHOLDER_MARKER not in text
    assert isinstance(applied, bool)
