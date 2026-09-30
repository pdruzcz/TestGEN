"""DOCX document parser.

Extracts text, structure (headers, lists, tables) from Microsoft Word .docx files.
"""

from pathlib import Path
from typing import cast

try:
    from docx import Document
except ImportError:
    raise ImportError(
        "python-docx is required for DOCX parsing. "
        "Install with: pip install python-docx"
    )

from app.services.analysis.document.base_parser import (
    BaseDocumentParser,
    DocumentFormat,
    DocumentSection,
    ParsedDocument,
    TableData,
)


class DOCXParser(BaseDocumentParser):
    """Parser for Microsoft Word (.docx) documents.

    Handles:
    - Paragraphs and text content
    - Headings (Styles 1-6)
    - Numbered and bulleted lists
    - Tables with headers and rows
    - Images (metadata only)
    """

    def parse(self) -> ParsedDocument:
        """Parse DOCX document."""
        doc = Document(str(self.file_path))

        raw_text_parts: list[str] = []
        sections: list[DocumentSection] = []
        tables: list[TableData] = []
        section_counter = 0

        # Current section being built
        current_title = "Document"
        current_level = 1
        current_content: list[str] = []

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue

            raw_text_parts.append(text)

            # Check for heading
            level = self._get_heading_level(paragraph)
            if level > 0:
                # Save previous section
                if current_content:
                    sections.append(
                        DocumentSection(
                            section_id=self._generate_section_id(current_title, section_counter),
                            title=current_title,
                            level=current_level,
                            content="\n".join(current_content).strip(),
                        )
                    )
                    section_counter += 1
                    current_content = []

                current_title = text
                current_level = level
            else:
                current_content.append(text)

        # Don't forget the last section
        if current_content:
            sections.append(
                DocumentSection(
                    section_id=self._generate_section_id(current_title, section_counter),
                    title=current_title,
                    level=current_level,
                    content="\n".join(current_content).strip(),
                )
            )

        # Extract tables
        for table_idx, table in enumerate(doc.tables):
            table_data = self._extract_table(table, table_idx)
            tables.append(table_data)

        return ParsedDocument(
            filename=self.file_path.name,
            format=DocumentFormat.DOCX,
            raw_text="\n\n".join(raw_text_parts),
            sections=sections,
            tables=tables,
            metadata={
                "paragraph_count": len(doc.paragraphs),
                "table_count": len(doc.tables),
            },
        )

    def _get_heading_level(self, paragraph) -> int:
        """Get heading level from paragraph style.

        Returns 0 if not a heading.
        """
        if paragraph.style.name.startswith("Heading"):
            try:
                level = int(paragraph.style.name.split()[-1])
                return min(max(level, 1), 6)
            except (ValueError, IndexError):
                return 1
        return 0

    def _extract_table(self, table, table_idx: int) -> TableData:
        """Extract table data from docx Table object."""
        headers: list[str] = []
        rows: list[list[str]] = []

        for row_idx, row in enumerate(table.rows):
            row_data: list[str] = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                row_data.append(cell_text)

            if row_idx == 0:
                headers = row_data
            else:
                rows.append(row_data)

        return TableData(
            table_id=f"table-{table_idx}",
            headers=headers,
            rows=rows,
            source_section_id="",  # Will be linked during preprocessing
        )
