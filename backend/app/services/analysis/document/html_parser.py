"""HTML document parser.

Extracts text, structure (headers, paragraphs, tables) from HTML files.
"""

import re
from pathlib import Path
from typing import cast

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError(
        "beautifulsoup4 is required for HTML parsing. "
        "Install with: pip install beautifulsoup4"
    )

from app.services.analysis.document.base_parser import (
    BaseDocumentParser,
    DocumentFormat,
    DocumentSection,
    ParsedDocument,
    TableData,
)


class HTMLParser(BaseDocumentParser):
    """Parser for HTML documents.

    Handles:
    - Heading elements (h1-h6)
    - Paragraphs and text content
    - Tables with headers and rows
    - Lists (ordered and unordered)
    - Links and images
    """

    def parse(self) -> ParsedDocument:
        """Parse HTML document."""
        html_content = self.file_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Extract sections based on headings
        sections: list[DocumentSection] = []
        section_counter = 0

        current_section: DocumentSection | None = None
        current_content: list[str] = []

        # Find all elements in document order
        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "ul", "ol"]):
            tag_name = element.name

            if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                # Save previous section
                if current_section and current_content:
                    current_section.content = "\n".join(current_content).strip()
                    sections.append(current_section)
                    section_counter += 1
                    current_content = []

                # Create new section
                level = int(tag_name[1])
                title = element.get_text().strip()
                current_section = DocumentSection(
                    section_id=self._generate_section_id(title, section_counter),
                    title=title,
                    level=level,
                    content="",  # Will be filled when next section starts
                )
            elif current_section is not None:
                # Add content to current section
                if tag_name == "p":
                    current_content.append(element.get_text().strip())
                elif tag_name in ["ul", "ol"]:
                    list_items = [li.get_text().strip() for li in element.find_all("li", recursive=False)]
                    current_content.append("\n".join(f"- {item}" for item in list_items))

        # Don't forget the last section
        if current_section and current_content:
            current_section.content = "\n".join(current_content).strip()
            sections.append(current_section)

        # Extract tables
        tables = self._extract_tables(soup)

        # Get raw text (all text content)
        raw_text = soup.get_text(separator="\n", strip=True)

        return ParsedDocument(
            filename=self.file_path.name,
            format=DocumentFormat.HTML,
            raw_text=raw_text,
            sections=sections,
            tables=tables,
            metadata={
                "element_count": len(soup.find_all()),
            },
        )

    def _extract_tables(self, soup) -> list[TableData]:
        """Extract tables from HTML."""
        tables: list[TableData] = []

        for table_idx, table in enumerate(soup.find_all("table")):
            headers: list[str] = []
            rows: list[list[str]] = []

            # Find headers in thead or first row of tbody
            thead = table.find("thead")
            if thead:
                headers = [th.get_text().strip() for th in thead.find_all("th")]

            # Find rows in tbody
            tbody = table.find("tbody") or table
            for tr in tbody.find_all("tr"):
                row_data: list[str] = []
                for cell in tr.find_all(["td", "th"]):
                    row_data.append(cell.get_text().strip())

                if row_data and not headers:  # First row without thead might be headers
                    headers = row_data
                elif row_data and len(row_data) == len(headers):
                    rows.append(row_data)

            if headers and rows:
                tables.append(
                    TableData(
                        table_id=f"table-{table_idx}",
                        headers=headers,
                        rows=rows,
                        source_section_id="",
                    )
                )

        return tables
