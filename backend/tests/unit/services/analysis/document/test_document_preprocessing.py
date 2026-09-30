"""Unit tests for document preprocessing (Story 2.2 — AC3/AC4).

Covers ``preprocess_document``: pre-order ``position`` assignment, headerless
paragraph segmentation, page_number/section_type propagation, and the empty /
artifacts-only document → ``ValueError`` path that the Celery task turns into a
FAILED file status.
"""

import pytest

from app.services.analysis.document.base_parser import (
    DocumentSection,
    ParsedDocument,
)
from app.services.analysis.document.preprocessing import preprocess_document


def _parsed(raw_text: str = "", sections=None, filename: str = "test.txt") -> ParsedDocument:
    return ParsedDocument(
        filename=filename,
        format="txt",
        raw_text=raw_text,
        sections=sections or [],
    )


def _preorder(sections):
    out = []
    for node in sections:
        out.append(node)
        out.extend(_preorder(node.children))
    return out


class TestPositionAndHierarchy:
    def test_assigns_preorder_positions(self):
        sections = [
            DocumentSection(section_id="s1", title="A", level=1, content="aaa"),
            DocumentSection(section_id="s2", title="B", level=2, content="bbb"),
            DocumentSection(section_id="s3", title="C", level=2, content="ccc"),
            DocumentSection(section_id="s4", title="D", level=1, content="ddd"),
        ]
        doc = preprocess_document(_parsed(sections=sections))

        flat = _preorder(doc.sections)
        assert [s.section_id for s in flat] == ["s1", "s2", "s3", "s4"]
        assert [s.position for s in flat] == [0, 1, 2, 3]

    def test_nests_children_by_level(self):
        sections = [
            DocumentSection(section_id="s1", title="A", level=1, content="aaa"),
            DocumentSection(section_id="s2", title="B", level=2, content="bbb"),
            DocumentSection(section_id="s3", title="C", level=3, content="ccc"),
        ]
        doc = preprocess_document(_parsed(sections=sections))

        assert [s.section_id for s in doc.sections] == ["s1"]
        assert [c.section_id for c in doc.sections[0].children] == ["s2"]
        assert doc.sections[0].children[0].children[0].section_id == "s3"

    def test_carries_page_number_and_section_type(self):
        sections = [DocumentSection(section_id="s1", title="A", level=1, content="x" * 60, page_number=7)]
        doc = preprocess_document(_parsed(sections=sections))

        section = doc.sections[0]
        assert section.page_number == 7
        assert section.section_type == "unclassified"


class TestHeaderlessHeuristic:
    LONG_1 = "Ten akapit ma zdecydowanie wiecej niz piecdziesiat znakow i sekcja."
    LONG_2 = "Drugi akapit, ktory rowniez przekracza limit piecdziesieciu znakow."

    def test_segments_by_paragraphs_over_50_chars(self):
        raw = f"{self.LONG_1}\n\nKrótki.\n\n{self.LONG_2}"
        doc = preprocess_document(_parsed(raw_text=raw, sections=[]))

        assert len(doc.sections) == 2
        assert [s.position for s in doc.sections] == [0, 1]
        assert all(s.level == 0 for s in doc.sections)
        assert all(s.section_type == "unclassified" for s in doc.sections)

    def test_segments_use_section_type_unclassified(self):
        raw = self.LONG_1
        doc = preprocess_document(_parsed(raw_text=raw, sections=[]))

        assert len(doc.sections) == 1
        assert doc.sections[0].section_type == "unclassified"
        assert doc.sections[0].level == 0


class TestEmptyAndArtifacts:
    def test_empty_document_raises(self):
        with pytest.raises(ValueError, match="tekstowej treści"):
            preprocess_document(_parsed(raw_text="", sections=[]))

    def test_short_paragraphs_only_raises(self):
        with pytest.raises(ValueError, match="tekstowej treści"):
            preprocess_document(_parsed(raw_text="Krótki.\n\nTeż krótki.", sections=[]))

    def test_artifacts_only_raises(self):
        # Standalone page numbers, copyright, separators — no real content.
        raw = "12\n© 2024 Acme\n--------------------\nStrona 1"
        with pytest.raises(ValueError, match="tekstowej treści"):
            preprocess_document(_parsed(raw_text=raw, sections=[]))
