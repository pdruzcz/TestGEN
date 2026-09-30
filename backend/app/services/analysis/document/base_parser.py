"""Base document parser module.

Provides abstract base class and common utilities for parsing various
document formats (PDF, DOCX, Markdown, HTML, TXT) for Epic 2 documentation
analysis.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class DocumentFormat(StrEnum):
    """Supported documentation file formats."""
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "md"
    HTML = "html"
    TXT = "txt"


@dataclass
class DocumentSection:
    """Represents a section within a parsed document."""
    section_id: str
    title: str
    level: int  # 1-6 (H1-H6)
    content: str
    parent_section_id: str | None = None
    children: list["DocumentSection"] = field(default_factory=list)
    page_number: int | None = None
    char_location: dict[str, int] | None = None  # {"start": 0, "end": 100}


@dataclass
class TableData:
    """Represents a table extracted from a document."""
    table_id: str
    headers: list[str]
    rows: list[list[str]]
    source_section_id: str
    page_number: int | None = None


@dataclass
class ParsedDocument:
    """Result of document parsing."""
    filename: str
    format: DocumentFormat
    raw_text: str
    sections: list[DocumentSection] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_section_by_id(self, section_id: str) -> DocumentSection | None:
        """Find a section by ID recursively."""
        for section in self.sections:
            if section.section_id == section_id:
                return section
            if found := self._find_child_section(section, section_id):
                return found
        return None

    def _find_child_section(self, parent: DocumentSection, section_id: str) -> DocumentSection | None:
        """Helper to recursively find child section."""
        for child in parent.children:
            if child.section_id == section_id:
                return child
            if found := self._find_child_section(child, section_id):
                return found
        return None


class BaseDocumentParser(ABC):
    """Abstract base class for document parsers.

    All document parsers must inherit from this class and implement
    the parse() method to return a ParsedDocument.
    """

    def __init__(self, file_path: str | Path):
        """Initialize parser with file path.

        Args:
            file_path: Path to the document file.
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

    @abstractmethod
    def parse(self) -> ParsedDocument:
        """Parse the document and return structured data.

        Returns:
            ParsedDocument with extracted text, sections, and tables.

        Raises:
            NotImplementedError: Subclass must implement.
        """
        raise NotImplementedError("Subclass must implement parse()")

    def _generate_section_id(self, title: str, index: int) -> str:
        """Generate a unique section ID from title and index."""
        # Sanitize title for ID: lowercase, replace spaces with hyphens, remove special chars
        sanitized = title.lower().strip()
        sanitized = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in sanitized)
        sanitized = sanitized[:50]  # Limit length
        return f"{sanitized}-{index}"

    def _extract_page_number(self, metadata: dict[str, Any]) -> int | None:
        """Extract page number from metadata if available."""
        return metadata.get("page_number")
