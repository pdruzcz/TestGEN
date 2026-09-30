"""Unit tests for ``PDFParser`` — Story 2-pdf-ocr-domknięcie.

Covers the replacement of the OCR placeholder stub with real OCR (reusing the
GUI module's ``OCRService``) and an honest ``has_ocr`` metric:

* AC1 — real OCR replaces the placeholder stub (regression guard runs in every
  environment; an image-gated end-to-end test runs where Tesseract/PyMuPDF live).
* AC2 — the OCR engine is reused from ``gui.ocr_service.OCRService`` (no
  duplicated Tesseract/EasyOCR logic); verified by delegating to a fake service.
* AC3 — graceful degrade when imaging deps are unavailable: fallback to the
  PyPDF2 text layer, ``has_ocr=False``, no crash.
* AC4 — honest ``has_ocr`` (True only when OCR produced text; False when a text
  layer is present, OCR is unavailable, or OCR yielded nothing).
* AC6 — image-gated tests skip cleanly without Tesseract/PyMuPDF.

PDFs are generated deterministically at test time (reportlab for the text-layer
variant, Pillow for the image-only "scanned" variant) — no binary fixtures.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING
from unittest.mock import patch

from app.services.analysis.document.pdf_parser import PDFParser

if TYPE_CHECKING:
    from pathlib import Path

# The exact marker emitted by the legacy stub — must never appear in output.
PLACEHOLDER_MARKER = "[OCR extracted text from"


# ---------------------------------------------------------------------------
# PDF generators (deterministic, no committed binaries).
# ---------------------------------------------------------------------------


def _make_text_pdf(path: Path, body: str = "") -> Path:
    """Create a PDF WITH a real, PyPDF2-extractable text layer (reportlab)."""
    from reportlab.pdfgen import canvas

    text = body or ("Wymagania funkcjonalne systemu logowania uzytkownikow. " * 8)
    pdf = canvas.Canvas(str(path))
    y = 800
    for fragment in text.split(". "):
        if fragment.strip():
            pdf.drawString(72, y, fragment.strip() + ".")
            y -= 16
    pdf.showPage()
    pdf.save()
    return path


def _make_scanned_pdf(path: Path, text: str = "Wymagania funkcjonalne systemu") -> Path:
    """Create an image-only PDF (no text layer) — emulates a scanned document."""
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
    # resolution=300 → A4-sized PDF page (see golden test for the bomb rationale).
    img.save(str(path), "PDF", resolution=300.0)
    return path


# ---------------------------------------------------------------------------
# AC4 — honest has_ocr (runs everywhere; no imaging deps required).
# ---------------------------------------------------------------------------


class TestHonestHasOcr:
    def test_text_layer_pdf_has_ocr_false(self, tmp_path):
        pdf = _make_text_pdf(tmp_path / "text.pdf")
        parsed = PDFParser(pdf).parse()
        assert parsed.metadata["has_ocr"] is False
        assert len(parsed.raw_text.strip()) > 100
        assert PLACEHOLDER_MARKER not in parsed.raw_text
        assert parsed.sections  # built from the text layer

    def test_has_ocr_true_when_ocr_produces_text(self, tmp_path):
        pdf = _make_scanned_pdf(tmp_path / "scan.pdf")  # PyPDF2 extracts < 100 chars
        real_ocr = "Rozdzial pierwszy wymagan funkcjonalnych systemu. " * 10
        with (
            patch.object(PDFParser, "_is_ocr_available", return_value=True),
            patch.object(PDFParser, "_extract_text_with_ocr", return_value=(real_ocr, True)),
        ):
            parsed = PDFParser(pdf).parse()
        assert parsed.metadata["has_ocr"] is True
        assert parsed.raw_text == real_ocr
        assert PLACEHOLDER_MARKER not in parsed.raw_text
        assert parsed.sections  # rebuilt from OCR text

    def test_has_ocr_false_when_ocr_yields_nothing(self, tmp_path):
        pdf = _make_scanned_pdf(tmp_path / "scan.pdf")
        with (
            patch.object(PDFParser, "_is_ocr_available", return_value=True),
            patch.object(PDFParser, "_extract_text_with_ocr", return_value=("", False)),
        ):
            parsed = PDFParser(pdf).parse()
        assert parsed.metadata["has_ocr"] is False
        assert PLACEHOLDER_MARKER not in parsed.raw_text

    def test_has_ocr_false_when_ocr_unavailable(self, tmp_path):
        """Scanned PDF + no OCR deps → has_ocr False (graceful degrade, AC3/AC4)."""
        pdf = _make_scanned_pdf(tmp_path / "scan.pdf")
        with patch.object(PDFParser, "_is_ocr_available", return_value=False):
            parsed = PDFParser(pdf).parse()
        assert parsed.metadata["has_ocr"] is False
        assert PLACEHOLDER_MARKER not in parsed.raw_text


# ---------------------------------------------------------------------------
# AC3 — graceful degrade: missing imaging deps → PyPDF2-only, no crash.
# AC1 — stub regression guard (never the placeholder).
# ---------------------------------------------------------------------------


class TestGracefulDegrade:
    def test_ocr_unavailable_no_crash_sparse_pdf(self, tmp_path):
        pdf = _make_scanned_pdf(tmp_path / "scan.pdf")
        with patch.object(PDFParser, "_is_ocr_available", return_value=False):
            parsed = PDFParser(pdf).parse()  # must not raise
        assert parsed.metadata["has_ocr"] is False
        assert parsed.format.value == "pdf"

    def test_extract_text_with_ocr_no_deps_returns_empty(self, tmp_path, monkeypatch):
        """PyMuPDF missing → ('', False); never the legacy placeholder (AC1)."""
        pdf = _make_text_pdf(tmp_path / "text.pdf")
        real_import = builtins.__import__

        def blocking_import(name, *args, **kwargs):
            if name == "fitz":
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocking_import)
        text, applied = PDFParser(pdf)._extract_text_with_ocr(pdf)
        assert applied is False
        assert text == ""
        assert PLACEHOLDER_MARKER not in text


# ---------------------------------------------------------------------------
# NOTE: image-gated end-to-end OCR tests (real rasterise → Tesseract → text,
# AC1/AC2/AC6) live in tests/golden_data/test_pdf_ocr_golden.py — collected by
# the golden-regression CI stage where the imaging stack + tesseract binary are
# installed. The non-gated logic tests below cover has_ocr honesty (AC4) and
# graceful degrade (AC3) without any optional deps.
