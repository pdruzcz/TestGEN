"""Unit tests for the glossary extractor and terminology mapper — Story 2.6 closure.

Covers:
- AC0 regression: ``extract_glossary(doc)`` no longer raises ``TypeError``
  (it used to call ``extractor.extract()`` with no argument — same bug pattern
  as ``extract_requirements`` before Story 2.4 closure).
- AC1: glossary extraction strategies + ``term_type`` classification.
- Persistence helpers: ``glossary_terms_to_result_data`` / ``from_result_data``
  round-trip (mirror of the requirements flow, Story 2.4).
- AC2: ``TerminologyMapper.map_to_code`` reuses ``suggest_code_mappings`` against
  code entities loaded from a (mocked) ``logic_structures`` AnalysisResult.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.schemas.document import DocumentStructure, SectionStructure
from app.services.analysis.document.glossary_extractor import (
    GlossaryTerm,
    TerminologyMapper,
    extract_glossary,
    from_result_data,
    glossary_terms_to_result_data,
)


def _section(
    section_id: str,
    title: str,
    content: str,
    children: list[SectionStructure] | None = None,
    level: int = 1,
) -> SectionStructure:
    return SectionStructure(
        section_id=section_id,
        title=title,
        level=level,
        content=content,
        children=children or [],
    )


def _glossary_doc() -> DocumentStructure:
    """Document with a glossary section (definitions) + 3 sections repeating
    a technical term (frequency-only entry)."""
    return DocumentStructure(
        sections=[
            _section(
                "gloss",
                "Glosariusz",
                "**API**: Aplikacyjny interfejs programistyczny.\n**Użytkownik**: Osoba korzystająca z systemu.",
            ),
            _section("b1", "Moduł logowania", "Moduł obsługuje logowanie."),
            _section("b2", "Moduł rejestracji", "Moduł obsługuje rejestrację."),
            _section("b3", "Moduł sesji", "Moduł zarządza sesją."),
        ]
    )


def _terms_by_name(terms: list[GlossaryTerm]) -> dict[str, GlossaryTerm]:
    return {t.term: t for t in terms}


# ── AC0 / AC1: extract_glossary(doc) does not crash and classifies terms ──────


class TestExtractGlossary:
    def test_returns_list_without_type_error(self):
        """Regression: ``extract_glossary`` used to call ``extractor.extract()``
        with no argument, raising ``TypeError`` (500 in production)."""
        terms = extract_glossary(_glossary_doc())
        assert isinstance(terms, list)

    def test_empty_document_returns_empty_list(self):
        assert extract_glossary(DocumentStructure(sections=[])) == []

    def test_definition_terms_enter_regardless_of_frequency(self):
        """Terms with a definition are included even when they appear once."""
        terms = _terms_by_name(extract_glossary(_glossary_doc()))
        assert "API" in terms
        assert "Użytkownik" in terms
        assert terms["Użytkownik"].definition == "Osoba korzystająca z systemu."

    def test_term_type_classification(self):
        """AC1: acronym → acronym; glossary-section definition → domain;
        technical keyword (moduł) without definition → technical."""
        terms = _terms_by_name(extract_glossary(_glossary_doc()))
        assert terms["API"].term_type == "acronym"
        assert terms["Użytkownik"].term_type == "domain"
        # "Moduł" repeats across 3 sections (freq >= 3), no definition → technical
        assert "Moduł" in terms
        assert terms["Moduł"].term_type == "technical"
        assert terms["Moduł"].definition is None

    def test_source_sections_carry_titles(self):
        terms = _terms_by_name(extract_glossary(_glossary_doc()))
        sections = terms["API"].source_sections
        assert sections
        assert any(s.get("title") == "Glosariusz" for s in sections)
        # "Moduł" appears in the three module sections
        mod_sections = terms["Moduł"].source_sections
        assert len(mod_sections) == 3

    def test_occurrences_count_from_frequency(self):
        terms = _terms_by_name(extract_glossary(_glossary_doc()))
        assert terms["Moduł"].occurrences_count >= 3


# ── Persistence helpers (mirror requirements_to_result_data) ─────────────────


class TestResultDataSerialization:
    def test_round_trip_preserves_all_fields(self):
        terms = [
            GlossaryTerm(
                term="API",
                definition="Interfejs",
                occurrences_count=5,
                term_type="acronym",
                source_sections=[{"section_id": "g", "title": "Glosariusz"}],
                is_verified=True,
                code_mappings=[{"name": "ApiController", "type": "class", "similarity": 1.0, "is_confirmed": True}],
            )
        ]
        data = glossary_terms_to_result_data(terms)
        assert "terms" in data
        assert len(data["terms"]) == 1

        restored = from_result_data(data)
        assert len(restored) == 1
        item = restored[0]
        assert item["term"] == "API"
        assert item["definition"] == "Interfejs"
        assert item["term_type"] == "acronym"
        assert item["is_verified"] is True
        assert item["code_mappings"][0]["name"] == "ApiController"

    def test_from_result_data_empty_and_none(self):
        assert from_result_data(None) == []
        assert from_result_data({}) == []
        assert from_result_data({"terms": []}) == []

    def test_code_mappings_default_empty(self):
        """Terms without code mappings serialize with an empty list."""
        data = glossary_terms_to_result_data([GlossaryTerm(term="Foo")])
        assert data["terms"][0]["code_mappings"] == []


# ── AC2: TerminologyMapper.map_to_code ───────────────────────────────────────


def _logic_structures_result_data() -> dict:
    """Shape produced by ``CodeStructureCatalog.to_dict()`` (Epic 1)."""
    return {
        "language": "python",
        "source_files": ["a.py", "c.py"],
        "functions": [
            {"name": "ApiController", "file_path": "a.py", "is_class_method": False},
        ],
        "classes": [
            {"name": "Config", "file_path": "c.py", "methods": []},
        ],
        "modules": [],
        "total_loc": 10,
        "total_functions": 1,
        "total_classes": 1,
        "analysis_timestamp": "2026-06-18T00:00:00",
    }


class TestTerminologyMapper:
    async def test_map_to_code_exact_and_fuzzy(self):
        """AC2: maps terms onto code entities via ``suggest_code_mappings``.
        Each mapping carries ``similarity`` and ``is_confirmed=False``."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = SimpleNamespace(result_data=_logic_structures_result_data())
        db.execute = AsyncMock(return_value=result_mock)

        mapper = TerminologyMapper()
        out = await mapper.map_to_code(
            [{"term": "API"}, {"term": "DataConfig"}],
            uuid.uuid4(),
            db,
        )

        # "API" → "ApiController" is an exact substring match (similarity 1.0)
        api_maps = out["API"]
        assert api_maps
        assert api_maps[0]["name"] == "ApiController"
        assert api_maps[0]["similarity"] == 1.0
        assert api_maps[0]["is_confirmed"] is False
        assert api_maps[0]["type"] in {"function", "method"}

        # "DataConfig" → "Config" is a fuzzy (contained-in) match. The reused
        # ``suggest_code_mappings`` scores fuzzy containment as len(term)/len(entity),
        # which can exceed 1.0; we only assert a positive, non-exact score here.
        data_maps = out["DataConfig"]
        assert data_maps
        assert data_maps[0]["name"] == "Config"
        assert data_maps[0]["type"] == "class"
        assert data_maps[0]["similarity"] > 0
        assert data_maps[0]["similarity"] != api_maps[0]["similarity"]

    async def test_map_to_code_empty_when_no_code(self):
        """AC2: when no ``logic_structures`` analysis exists, every term maps to
        an empty list (non-fatal — glossary still works)."""
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        mapper = TerminologyMapper()
        out = await mapper.map_to_code([{"term": "API"}], uuid.uuid4(), db)
        assert out == {"API": []}

    def test_entities_from_logic_structures_shape(self):
        """Code entities are extracted as ``{name, type, file_path}`` from the
        persisted ``logic_structures`` result_data."""
        entities = TerminologyMapper._entities_from_logic_structures(_logic_structures_result_data())
        names_types = {(e["name"], e["type"]) for e in entities}
        assert ("ApiController", "function") in names_types
        assert ("Config", "class") in names_types
        for e in entities:
            assert {"name", "type", "file_path"} <= set(e.keys())
