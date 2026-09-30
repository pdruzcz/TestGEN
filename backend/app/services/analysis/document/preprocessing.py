"""Document preprocessing module for Epic 2.

This module handles text segmentation, cleaning, and table extraction
from parsed documents. It processes ParsedDocument objects and produces
DocumentStructure with hierarchical sections and extracted tables.

Key features:
- Section segmentation with parent-child relationships
- Artifact removal (headers, footers, page numbers, watermarks)
- Polish character normalization
- Table extraction and validation
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass

from app.schemas.document import (
    DocumentStructure,
    SectionStructure,
    TableData,
)
from app.services.analysis.document.base_parser import (
    DocumentSection as ParserSection,
)
from app.services.analysis.document.base_parser import (
    ParsedDocument,
)

# Common artifacts to remove
PAGE_NUMBER_PATTERNS = [
    r"^\s*\d+\s*$",  # Standalone numbers (page numbers)
    r"^-+\s*\d+\s*-+$",  # --- 12 ---
    r"^\d+\s*/\s*\d+",  # 1/10 style page numbers
    r"^Strona\s+\d+",  # "Strona 42"
    r"^Page\s+\d+",  # "Page 42"
    r"^S\.\s*\d+",  # "S. 42"
]

FOOTER_PATTERNS = [
    r"©\s*\d{4}.*$",  # Copyright lines
    r"^\s*Confidential\s*$",  # Confidential markers
    r"^Wersja\s+\d+\.?\d*",  # Version numbers
    r"^Data:\s*\d{4}-\d{2}-\d{2}",  # Date stamps
    r"^\s*_+\s*$",  # Separator lines
    r"^\s*-+\s*$",  # Separator lines
]

WATERMARK_PATTERNS = [
    r"DRAFT\s*$",
    r"CONFIDENTIAL\s*$",
    r"INTERNAL\s+USE\s+ONLY\s*$",
    r"DO\s+NOT\s+DISTRIBUTE\s*$",
]

# Polish character mapping (for fixing encoding issues)
POLISH_CHARS_MAP = {
    "±": "ą",
    "ê": "ę",
    "¶": "ś",
    "³": "ł",
    "¿": "ż",
    "Ÿ": "ź",
    "Æ": "Ą",
    "Ê": "Ę",
    "£": "Ł",
    "¯": "Ż",
    "¬": "Ź",
    "¦": "Ś",
    "†": "Ć",
    "´": "ć",  # noqa: RUF001
    "ñ": "ń",
    "ƒ": "Ń",
}


@dataclass
class PreprocessingStats:
    """Statistics collected during preprocessing."""

    processing_time_ms: int = 0
    artifact_count: int = 0
    polish_char_issues_fixed: int = 0
    sections_count: int = 0
    tables_count: int = 0
    total_characters_before: int = 0
    total_characters_after: int = 0


class DocumentPreprocessor:
    """Main preprocessing class for document structure extraction.

    Takes a ParsedDocument from the parser and produces a cleaned,
    hierarchical DocumentStructure with sections and tables.
    """

    def __init__(self) -> None:
        self.stats = PreprocessingStats()

    def preprocess(self, parsed: ParsedDocument) -> DocumentStructure:
        """Main preprocessing pipeline.

        Args:
            parsed: Raw parsed document from document parser

        Returns:
            DocumentStructure with cleaned sections and tables
        """
        start_time = time.time()

        # Collect raw stats
        self.stats.total_characters_before = len(parsed.raw_text)

        # Build hierarchical structure
        sections = self._build_hierarchy(parsed.sections)

        # AC4: document with no detected headings → segment by paragraphs > 50
        # chars (level 0, section_type="unclassified").
        if not sections:
            sections = self._segment_by_paragraphs(parsed.raw_text)

        # AC4: document empty / only artifacts after cleaning → signal failure.
        # The Celery task catches this and marks the SourceFile as FAILED.
        if not sections:
            raise ValueError("Dokument nie zawiera tekstowej treści")

        self.stats.sections_count = len(sections)

        # Extract and validate tables
        tables = self._extract_tables(parsed)
        self.stats.tables_count = len(tables)

        # Calculate processing time
        self.stats.processing_time_ms = int((time.time() - start_time) * 1000)
        self.stats.total_characters_after = sum(len(s.content) for s in sections)

        # Build metadata
        metadata = {
            "filename": parsed.filename,
            "format": parsed.format,
            "processing_time_ms": self.stats.processing_time_ms,
            "artifact_count": self.stats.artifact_count,
            "polish_char_issues_fixed": self.stats.polish_char_issues_fixed,
            "sections_count": self.stats.sections_count,
            "tables_count": self.stats.tables_count,
            "compression_ratio": (
                self.stats.total_characters_after / self.stats.total_characters_before
                if self.stats.total_characters_before > 0
                else 1.0
            ),
        }

        return DocumentStructure(
            sections=sections,
            tables=tables,
            metadata=metadata,
        )

    def _build_hierarchy(self, sections: list[ParserSection]) -> list[SectionStructure]:
        """Build hierarchical section structure from flat list.

        Uses section levels to determine parent-child relationships.
        Section at level N becomes parent of following sections at level N+1
        until another section at level N or higher is encountered.
        """
        # First, clean all section content
        cleaned_sections: list[ParserSection] = []
        for section in sections:
            cleaned = self._clean_section_content(section.content)
            if cleaned.strip():  # Only keep non-empty sections
                cleaned_sections.append(
                    ParserSection(
                        section_id=section.section_id,
                        title=section.title,
                        level=section.level,
                        content=cleaned,
                        parent_section_id=section.parent_section_id,
                        page_number=section.page_number,
                    )
                )

        # Build hierarchy
        result: list[SectionStructure] = []
        stack: list[tuple[SectionStructure, int]] = []  # (section, level)

        for section in cleaned_sections:
            section_struct = SectionStructure(
                section_id=section.section_id,
                title=self._clean_title(section.title),
                level=section.level,
                content=section.content,
                parent_section_id=section.parent_section_id,
                page_number=section.page_number,
                position=0,
                section_type="unclassified",
                children=[],
            )

            # Pop higher-level sections from stack
            while stack and stack[-1][1] >= section.level:
                stack.pop()

            # Add to parent's children or as root
            if stack:
                stack[-1][0].children.append(section_struct)
            else:
                result.append(section_struct)

            # Push current section
            stack.append((section_struct, section.level))

        # Assign document-order positions (pre-order traversal) — AC3
        self._assign_positions(result)

        return result

    def _assign_positions(self, sections: list[SectionStructure], start: int = 0) -> int:
        """Assign sequential ``position`` in pre-order (document order).

        A parent is numbered before its children, mirroring the order sections
        appear in the source document.
        """
        pos = start
        for section in sections:
            section.position = pos
            pos += 1
            pos = self._assign_positions(section.children, pos)
        return pos

    def _segment_by_paragraphs(self, raw_text: str) -> list[SectionStructure]:
        """Segment headerless text into sections by paragraph (AC4).

        Used when the parser detected no heading structure. Each paragraph
        longer than 50 characters (after artifact cleaning) becomes a level-0
        ``unclassified`` section. Returns an empty list when the text is empty
        or contains only artifacts (caller raises ``ValueError`` in that case).
        """
        if not raw_text or not raw_text.strip():
            return []

        sections: list[SectionStructure] = []
        paragraphs = re.split(r"\n\s*\n", raw_text)

        for paragraph in paragraphs:
            cleaned = self._clean_section_content(paragraph)
            if len(cleaned) > 50:
                sections.append(
                    SectionStructure(
                        section_id=f"unclassified-{len(sections)}",
                        title=f"Sekcja {len(sections) + 1}",
                        level=0,
                        content=cleaned,
                        parent_section_id=None,
                        page_number=None,
                        position=0,
                        section_type="unclassified",
                        children=[],
                    )
                )

        self._assign_positions(sections)
        return sections

    def _clean_section_content(self, content: str) -> str:
        """Clean section content by removing artifacts and normalizing text."""
        if not content:
            return ""

        # Join words split across lines by a trailing hyphen (de-hyphenation)
        content = self._fix_hyphenation(content)

        # Normalize Polish characters
        content = self._normalize_polish_chars(content)

        # Remove artifacts line by line
        lines = content.split("\n")
        cleaned_lines: list[str] = []
        for line in lines:
            cleaned_line = self._remove_artifacts_from_line(line.strip())
            if cleaned_line:
                cleaned_lines.append(cleaned_line)
            else:
                self.stats.artifact_count += 1

        # Remove excessive blank lines
        result = self._remove_excessive_blank_lines("\n".join(cleaned_lines))

        # Clean up whitespace
        result = self._normalize_whitespace(result)

        return result

    def _clean_title(self, title: str) -> str:
        """Clean section title."""
        if not title:
            return "(Bez tytułu)"

        # Remove common artifacts from titles
        title = re.sub(r"^\d+\.?\s*", "", title)  # Remove leading numbers
        title = self._normalize_polish_chars(title)
        title = title.strip()

        # Limit title length
        if len(title) > 100:
            title = title[:97] + "..."

        return title or "(Bez tytułu)"

    def _extract_tables(self, parsed: ParsedDocument) -> list[TableData]:
        """Extract and validate tables from parsed document."""
        tables: list[TableData] = []

        for table in parsed.tables:
            # Skip empty tables
            if not table.rows or not table.headers:
                continue

            # Clean table content
            clean_headers = [self._clean_table_cell(h) for h in table.headers]
            clean_rows = [
                [self._clean_table_cell(cell) for cell in row]
                for row in table.rows
                if any(cell.strip() for cell in row)  # Skip empty rows
            ]

            if not clean_rows:
                continue

            tables.append(
                TableData(
                    table_id=table.table_id,
                    headers=clean_headers,
                    rows=clean_rows,
                    source_section_id=table.source_section_id,
                )
            )

        return tables

    def _clean_table_cell(self, cell: str) -> str:
        """Clean individual table cell content."""
        if not cell:
            return ""

        cell = self._normalize_polish_chars(cell)
        cell = cell.strip()
        # Remove excessive whitespace within cell
        cell = re.sub(r"\s+", " ", cell)
        return cell

    def _remove_artifacts_from_line(self, line: str) -> str:
        """Remove artifacts from a single line."""
        if not line:
            return ""

        # Check against all artifact patterns
        for pattern in PAGE_NUMBER_PATTERNS + FOOTER_PATTERNS + WATERMARK_PATTERNS:
            if re.match(pattern, line, re.IGNORECASE):
                self.stats.artifact_count += 1
                return ""

        # Remove common separators
        if re.match(r"^[_\-]{10,}$", line):
            self.stats.artifact_count += 1
            return ""

        return line

    def _fix_hyphenation(self, text: str) -> str:
        """Join words split across line breaks by a trailing hyphen.

        PDFs and wrapped text often break long words with ``-\\n``; e.g.
        ``"wymaga-\\nnia"`` should become ``"wymagania"`` (not
        ``"wymaga-nia"``). Only matches a hyphen immediately followed by a
        newline to avoid touching legitimate in-line hyphens.
        """
        return re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)

    def _normalize_polish_chars(self, text: str) -> str:
        """Normalize Polish characters in text.

        Fixes common encoding issues where Polish characters
        are represented by incorrect ISO-8859-2 characters.
        """
        result = list(text)
        changes = 0

        for i, char in enumerate(text):
            if char in POLISH_CHARS_MAP:
                result[i] = POLISH_CHARS_MAP[char]
                changes += 1
            # Also handle NFC/NFD normalization
            elif ord(char) > 127:
                normalized = unicodedata.normalize("NFC", char)
                result[i] = normalized

        self.stats.polish_char_issues_fixed += changes
        return "".join(result)

    def _remove_excessive_blank_lines(self, text: str) -> str:
        """Remove excessive blank lines (more than 2 consecutive)."""
        return re.sub(r"\n{3,}", "\n\n", text)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        # Remove leading/trailing whitespace from each line
        lines = text.split("\n")
        lines = [line.strip() for line in lines]
        return "\n".join(lines).strip()


def preprocess_document(parsed: ParsedDocument) -> DocumentStructure:
    """Convenience function to preprocess a parsed document.

    Args:
        parsed: ParsedDocument from document parser

    Returns:
        DocumentStructure with cleaned sections and tables
    """
    preprocessor = DocumentPreprocessor()
    return preprocessor.preprocess(parsed)
