"""TXT document parser.

Extracts text and structure from plain text files using heuristics.
"""

import re
from pathlib import Path

from app.services.analysis.document.base_parser import (
    BaseDocumentParser,
    DocumentFormat,
    DocumentSection,
    ParsedDocument,
)


class TXTParser(BaseDocumentParser):
    """Parser for plain text (.txt) documents.

    Handles:
    - Heuristic header detection (all caps, numbering)
    - Paragraph and list detection
    - Simple structure extraction

    Limitations:
    - Structure depends on text formatting
    - No rich metadata available
    """

    def parse(self) -> ParsedDocument:
        """Parse TXT document."""
        content = self.file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")

        sections: list[DocumentSection] = []
        section_counter = 0

        current_title = "Document"
        current_level = 1
        current_content: list[str] = []

        for line in lines:
            line = line.rstrip()
            if not line:
                continue

            # Detect headers using heuristics
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
                )
            )

        return ParsedDocument(
            filename=self.file_path.name,
            format=DocumentFormat.TXT,
            raw_text=content,
            sections=sections,
            metadata={
                "line_count": len(lines),
            },
        )

    def _detect_header_level(self, line: str) -> int:
        """Detect if line is a header using heuristics.

        Returns 0 if not a header.
        """
        # All caps with minimal punctuation = likely H1
        if line.isupper() and len(line) < 80:
            word_count = len(line.split())
            if word_count <= 5:  # Short title-like
                return 1

        # Numbered patterns
        if re.match(r"^CHAPTER\s+[IVXLC]+\.", line, re.IGNORECASE):
            return 1
        if re.match(r"^Chapter\s+\d+", line, re.IGNORECASE):
            return 1
        if re.match(r"^\d+\.\s+[A-Z]", line):
            return 2
        if re.match(r"^\d+\.\d+\s+", line):
            return 3
        if re.match(r"^\d+\.\d+\.\d+\s+", line):
            return 4

        # Roman numerals
        if re.match(r"^(IV|III|II|I|VIII|VII|VI|V|IX|X)\.\s+", line):
            return 1

        # Underline detection (Setext-style)
        # This would require looking at next line - simplified for now

        return 0
