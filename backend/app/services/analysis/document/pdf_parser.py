"""PDF document parser.

Extracts text, structure, and tables from PDF files using PyPDF2.
For scanned PDFs (no text layer), falls back to real OCR: PyMuPDF rasterises
each page and the shared ``OCRService`` (Tesseract → EasyOCR), reused from the
GUI module, extracts the text. Imaging deps are optional — when missing the
parser degrades gracefully to the PyPDF2 text layer (``has_ocr=False``).
"""

import io
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from PyPDF2 import PdfReader
except ImportError:
    raise ImportError(
        "PyPDF2 is required for PDF parsing. Install with: pip install PyPDF2",
    ) from None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    # OCR is optional - will be handled gracefully
    pytesseract = None
    Image = None

from app.services.analysis.document.base_parser import (  # noqa: E402
    BaseDocumentParser,
    DocumentFormat,
    DocumentSection,
    ParsedDocument,
    TableData,
)


class PDFParser(BaseDocumentParser):
    """Parser for PDF documents.

    Handles:
    - Standard PDFs with extractable text
    - Multi-page PDFs (up to 500 pages)
    - Scanned PDFs via OCR (Tesseract)

    Limitations:
    - OCR quality depends on image resolution
    - Complex layouts may have extraction errors
    """

    MAX_PAGES = 500

    def parse(self) -> ParsedDocument:
        """Parse PDF document."""
        reader = PdfReader(str(self.file_path))

        # Validate page count
        page_count = len(reader.pages)
        if page_count > self.MAX_PAGES:
            raise ValueError(f"PDF exceeds maximum page count ({self.MAX_PAGES}). Found {page_count} pages.")

        # Extract text and metadata
        text_parts: list[str] = []
        sections: list[DocumentSection] = []
        tables: list[TableData] = []

        for page_num, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()
            text_parts.append(page_text)

            # Extract sections from page text
            page_sections = self._extract_sections_from_text(page_text, page_num)
            sections.extend(page_sections)

        raw_text = "\n\n".join(text_parts)

        # Check if OCR is needed (very little text extracted)
        has_ocr = False
        if len(raw_text.strip()) < 100 and page_count > 0:
            if self._is_ocr_available():
                # Real OCR for scanned documents (reuses the GUI OCR engine)
                ocr_text, ocr_applied = self._extract_text_with_ocr(self.file_path)
                if ocr_applied and ocr_text.strip():
                    raw_text = ocr_text
                    # Re-extract sections from the OCR text
                    sections = self._extract_sections_from_text(raw_text, None)
                    has_ocr = True
                else:
                    logger.warning("OCR PDF nie wyodrębnił tekstu — pozostawiono warstwę tekstową PyPDF2.")
            else:
                logger.warning("OCR niedostępny (PyMuPDF/Tesseract) — zwrócono tylko warstwę tekstową PyPDF2.")

        return ParsedDocument(
            filename=self.file_path.name,
            format=DocumentFormat.PDF,
            raw_text=raw_text,
            sections=sections,
            tables=tables,
            metadata={
                "page_count": page_count,
                "has_ocr": has_ocr,
            },
        )

    def _extract_sections_from_text(self, text: str, page_number: int | None) -> list[DocumentSection]:
        """Extract document sections from raw text using heuristics.

        Looks for:
        - All caps lines (potential headers)
        - Numbered patterns (1., 2., 1.1, 1.2)
        - Roman numerals (I., II., III.)
        """
        sections: list[DocumentSection] = []
        lines = text.split("\n")

        current_content: list[str] = []
        current_title = "Untitled"
        current_level = 1
        section_counter = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect headers
            level = self._detect_header_level(line)
            if level > 0:
                # Save previous section
                if current_content:
                    sections.append(
                        DocumentSection(
                            section_id=self._generate_section_id(current_title, section_counter),
                            title=current_title,
                            level=current_level,
                            content="\n".join(current_content).strip(),
                            page_number=page_number,
                        )
                    )
                    section_counter += 1
                    current_content = []

                current_title = line
                current_level = level
            else:
                current_content.append(line)

        # Don't forget the last section
        if current_content:
            sections.append(
                DocumentSection(
                    section_id=self._generate_section_id(current_title, section_counter),
                    title=current_title,
                    level=current_level,
                    content="\n".join(current_content).strip(),
                    page_number=page_number,
                )
            )

        return sections

    def _detect_header_level(self, line: str) -> int:
        """Detect if line is a header and return its level (1-6).

        Returns 0 if not a header.
        """
        # All caps with minimal punctuation = likely H1
        if line.isupper() and len(line) < 100 and not re.search(r"[.,;:]", line):
            return 1

        # Numbered patterns
        if re.match(r"^Chapter \d+", line, re.IGNORECASE):
            return 1
        if re.match(r"^\d+\.\s+[A-Z]", line):
            return 2
        if re.match(r"^\d+\.\d+\s+", line):
            return 3
        if re.match(r"^\d+\.\d+\.\d+\s+", line):
            return 4
        if re.match(r"^\d+\.\d+\.\d+\.\d+\s+", line):
            return 5

        # Roman numerals
        if re.match(r"^(IV|III|II|I|VIII|VII|VI|V|IX|X)\.\s+", line):
            return 1

        return 0

    def _is_ocr_available(self) -> bool:
        """Check if PDF rasterisation + OCR libraries are available.

        Requires PyMuPDF (``fitz``) to rasterise pages, Pillow to decode the
        pixmap, and the Tesseract binding as the primary OCR engine. When any is
        missing the scanned-PDF path degrades gracefully to the PyPDF2 layer.
        """
        try:
            import fitz  # noqa: F401 -- PyMuPDF availability probe
        except ImportError:
            return False
        return pytesseract is not None and Image is not None

    def _extract_text_with_ocr(self, pdf_path: Path) -> tuple[str, bool]:
        """Extract text from a scanned PDF via OCR. Returns ``(text, ocr_applied)``.

        Rasterises each page with PyMuPDF (300 DPI) and feeds the decoded image
        to the shared :class:`~app.services.analysis.gui.ocr_service.OCRService`
        (Tesseract → EasyOCR), reused from the GUI module — no duplicated OCR
        logic. ``ocr_applied`` is ``True`` only when at least one page yielded
        OCR text, so :meth:`parse` can report an honest ``has_ocr`` (AC4).

        Imaging deps missing → ``("", False)`` and the caller falls back to the
        PyPDF2 text layer (AC3, graceful degrade).
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("PyMuPDF (fitz) niedostępny — OCR PDF pominięty.")
            return "", False

        from app.services.analysis.gui.ocr_service import OCRService

        ocr = OCRService()
        text_parts: list[str] = []
        ocr_applied = False
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as exc:  # pragma: no cover - depends on PyMuPDF
            logger.warning("Otwarcie PDF do OCR nie powiodło się: %s", exc)
            return "", False
        try:
            for page in doc:
                pix = page.get_pixmap(dpi=300)
                image = Image.open(io.BytesIO(pix.tobytes("png")))
                blocks, _warnings = ocr.extract_text(image)
                page_text = " ".join(block.text for block in blocks).strip()
                if page_text:
                    ocr_applied = True
                text_parts.append(page_text)
        finally:
            doc.close()
        return "\n\n".join(text_parts), ocr_applied
