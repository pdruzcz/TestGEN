"""Document parsers module for Epic 2 documentation analysis.

Exports all document parsers and provides factory function to get the appropriate
parser based on file format.
"""

from pathlib import Path
from typing import cast

from app.schemas.document import DocumentStructure
from app.services.analysis.document.base_parser import (
    BaseDocumentParser,
    DocumentFormat,
    ParsedDocument,
)
from app.services.analysis.document.classifier import classify_document
from app.services.analysis.document.docx_parser import DOCXParser
from app.services.analysis.document.glossary_extractor import extract_glossary
from app.services.analysis.document.html_parser import HTMLParser
from app.services.analysis.document.inconsistency_detector import detect_inconsistencies
from app.services.analysis.document.markdown_parser import MarkdownParser
from app.services.analysis.document.pdf_parser import PDFParser
from app.services.analysis.document.preprocessing import preprocess_document
from app.services.analysis.document.requirement_extractor import extract_requirements
from app.services.analysis.document.txt_parser import TXTParser

__all__ = [
    "BaseDocumentParser",
    "DocumentFormat",
    "ParsedDocument",
    "PDFParser",
    "DOCXParser",
    "MarkdownParser",
    "HTMLParser",
    "TXTParser",
    "get_document_parser",
    "preprocess_document",
    "parse_and_preprocess_document",
    "classify_document",
    "extract_requirements",
    "extract_glossary",
    "detect_inconsistencies",
]


# File extension to parser mapping
_PARSER_MAP: dict[str, type[BaseDocumentParser]] = {
    ".pdf": PDFParser,
    ".docx": DOCXParser,
    ".md": MarkdownParser,
    ".markdown": MarkdownParser,
    ".html": HTMLParser,
    ".htm": HTMLParser,
    ".txt": TXTParser,
}


def get_document_parser(file_path: str | Path) -> BaseDocumentParser:
    """Factory function to get the appropriate document parser.

    Args:
        file_path: Path to the document file.

    Returns:
        Instance of the appropriate document parser.

    Raises:
        ValueError: If file format is not supported.
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    parser_class = _PARSER_MAP.get(extension)
    if parser_class is None:
        supported = ", ".join(_PARSER_MAP.keys())
        raise ValueError(
            f"Unsupported file format: {extension}. "
            f"Supported formats: {supported}"
        )

    return parser_class(file_path)


def parse_document(file_path: str | Path) -> ParsedDocument:
    """Convenience function to parse a document.

    Args:
        file_path: Path to the document file.

    Returns:
        ParsedDocument with extracted text and structure.

    Raises:
        ValueError: If file format is not supported.
        FileNotFoundError: If file doesn't exist.
    """
    parser = get_document_parser(file_path)
    return parser.parse()


def parse_and_preprocess_document(file_path: str | Path) -> DocumentStructure:
    """Parse and preprocess a document in one call.

    This is the main entry point for document analysis pipeline.

    Args:
        file_path: Path to the document file.

    Returns:
        DocumentStructure with cleaned hierarchical sections and tables.

    Raises:
        ValueError: If file format is not supported.
        FileNotFoundError: If file doesn't exist.
    """
    parsed = parse_document(file_path)
    return preprocess_document(parsed)
