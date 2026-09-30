"""Markdown document parser.

Extracts text, structure (headers, code blocks, tables) from Markdown files.
"""

import re
from pathlib import Path

from app.services.analysis.document.base_parser import (
    BaseDocumentParser,
    DocumentFormat,
    DocumentSection,
    ParsedDocument,
    TableData,
)


class MarkdownParser(BaseDocumentParser):
    """Parser for Markdown (.md) documents.

    Handles:
    - ATX-style headers (# ## ###)
    - Setext-style headers (underlines)
    - Code blocks (``` and indented)
    - Tables (GitHub-flavored)
    - Lists (ordered and unordered)
    - Links and images
    """

    def parse(self) -> ParsedDocument:
        """Parse Markdown document."""
        content = self.file_path.read_text(encoding="utf-8")

        # Split into lines
        lines = content.split("\n")

        sections: list[DocumentSection] = []
        tables: list[TableData] = []

        # Parse structure
        sections = self._parse_markdown_structure(lines)

        # Extract tables
        tables = self._extract_markdown_tables(lines)

        return ParsedDocument(
            filename=self.file_path.name,
            format=DocumentFormat.MARKDOWN,
            raw_text=content,
            sections=sections,
            tables=tables,
            metadata={
                "line_count": len(lines),
            },
        )

    def _parse_markdown_structure(self, lines: list[str]) -> list[DocumentSection]:
        """Parse Markdown structure into sections."""
        sections: list[DocumentSection] = []
        section_counter = 0

        current_title = "Document"
        current_level = 1
        current_content: list[str] = []
        in_code_block = False
        code_block_fence = ""

        for line in lines:
            # Check for code block fence
            if line.startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    code_block_fence = line[3:]
                    current_content.append(line)
                    continue
                elif line[3:].startswith(code_block_fence):
                    in_code_block = False
                    current_content.append(line)
                    continue

            if in_code_block:
                current_content.append(line)
                continue

            # Check for ATX-style header
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
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

                hashes = header_match.group(1)
                current_title = header_match.group(2).strip()
                current_level = len(hashes)
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
                )
            )

        return sections

    def _extract_markdown_tables(self, lines: list[str]) -> list[TableData]:
        """Extract GitHub-flavored Markdown tables."""
        tables: list[TableData] = []
        table_counter = 0
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # Detect table header (must contain |)
            if "|" in line and not line.startswith("|"):
                # Not a GFM table (must start with |)
                i += 1
                continue

            if "|" in line:
                # Parse table
                headers = [h.strip() for h in line.split("|") if h.strip()]

                # Next line should be separator
                i += 1
                if i >= len(lines):
                    break

                separator = lines[i].strip()
                if not separator.startswith("|") or not separator.endswith("|"):
                    # Not a valid table
                    i += 1
                    continue

                # Parse rows
                rows: list[list[str]] = []
                i += 1
                while i < len(lines):
                    row_line = lines[i].strip()
                    if not row_line or "|" not in row_line:
                        break

                    row_data = [cell.strip() for cell in row_line.split("|") if cell.strip()]
                    if row_data:
                        rows.append(row_data)
                    i += 1

                if headers and rows:
                    tables.append(
                        TableData(
                            table_id=f"table-{table_counter}",
                            headers=headers,
                            rows=rows,
                            source_section_id="",
                        )
                    )
                    table_counter += 1
            else:
                i += 1

        return tables
