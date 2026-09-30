"""Unit tests for the gap analyzer — Story 2.8 closure.

Covers:
- AC1: name/docstring matching maps requirements onto code entities and
  assigns a status per requirement (subtask 5.1). The native matcher emits
  ``not_implemented`` / ``partial`` / ``implemented``; ``divergent`` is part of
  the data model but is not produced by the v1 name+docstring matcher (semantic
  divergence detection is an out-of-scope follow-up), so it is exercised at the
  report/serialization level.
- AC1/AC2: ``code_entities_from_logic_structures`` converts the Epic 1
  ``logic_structures`` payload into ``CodeEntity`` objects (subtask 5.2).
- AC2/AC4: ``gap_analysis_to_result_data`` / ``from_result_data`` round-trip the
  persisted payload with safe defaults (subtask 5.3).
"""

from __future__ import annotations

from app.schemas.document import DocumentStructure, SectionStructure
from app.services.analysis.gap_analyzer import (
    CodeEntity,
    CoverageReport,
    GapAnalysisResult,
    GapAnalyzer,
    code_entities_from_logic_structures,
    from_result_data,
    gap_analysis_to_result_data,
)


def _section(section_id: str, title: str, content: str = "") -> SectionStructure:
    return SectionStructure(
        section_id=section_id,
        title=title,
        level=1,
        content=content,
        children=[],
    )


def _doc() -> DocumentStructure:
    """Minimal document structure (the matcher does not read section content)."""
    return DocumentStructure(sections=[_section("s1", "Wymagania", "Treść")])


def _req(req_id: str, text: str, *, source_section_id: str = "s1") -> dict:
    """Build an ``ExtractedRequirementSchema`` dict (matcher input)."""
    return {
        "req_id": req_id,
        "text": text,
        "type": "functional",
        "priority": "medium",
        "source_section_id": source_section_id,
        "confidence": 0.9,
        "extraction_method": "native",
    }


def _entity(
    name: str,
    *,
    etype: str = "function",
    docstring: str | None = None,
    file_path: str = "src/app.py",
) -> CodeEntity:
    return CodeEntity(
        entity_id=f"id-{name}",
        name=name,
        type=etype,
        file_path=file_path,
        line_number=10,
        language="python",
        docstring=docstring,
    )


# ── AC1 / 5.1: status assignment via name/docstring matching ─────────────────


class TestStatusAssignment:
    def test_not_implemented_when_no_code_entities(self):
        """A requirement with no matching code entity is ``not_implemented``."""
        analyzer = GapAnalyzer()
        report, items = analyzer.analyze_detailed(
            _doc(),
            [_req("FR-1", "System musi obsługiwać logowanie dwuskładnikowe.")],
            code_entities=[],
        )

        assert len(items) == 1
        assert items[0].status == "not_implemented"
        assert items[0].mapped_entities == []
        assert items[0].confidence == 0.0
        assert report.not_implemented == 1
        assert report.implemented == 0
        assert report.coverage_percentage == 0.0

    def test_partial_for_single_name_match_without_docstring_support(self):
        """A single name match (base confidence 0.7) resolves to ``partial``."""
        analyzer = GapAnalyzer()
        report, items = analyzer.analyze_detailed(
            _doc(),
            [_req("FR-2", "aplikacja musi zapisywać Raport do pliku.")],
            code_entities=[_entity("Raport", docstring="raport eksport danych")],
        )

        assert items[0].status == "partial"
        assert items[0].mapped_entities == ["Raport"]
        assert 0.6 <= items[0].confidence < 0.9
        assert report.partial == 1

    def test_implemented_for_multiple_matches_with_docstring_support(self):
        """Two matches whose docstrings cite the requirement terms (confidence
        >= 0.9) resolve to ``implemented``."""
        analyzer = GapAnalyzer()
        report, items = analyzer.analyze_detailed(
            _doc(),
            [_req("FR-3", "aplikacja musi rysować Panel oraz Nagłówek na ekranie.")],
            code_entities=[
                _entity("Panel", docstring="panel nagłówek widok główny"),
                _entity("Nagłówek", docstring="panel nagłówek tytuł aplikacji"),
            ],
        )

        assert items[0].status == "implemented"
        assert set(items[0].mapped_entities) == {"Panel", "Nagłówek"}
        assert items[0].confidence >= 0.9
        assert report.implemented == 1
        assert report.coverage_percentage == 100.0

    def test_divergent_supported_by_report_and_serialization(self):
        """``divergent`` is part of the model even though the v1 matcher does
        not emit it. ``_build_report`` counts it and serialization preserves
        the status and feeds ``critical_gaps``."""
        analyzer = GapAnalyzer()
        divergent = GapAnalysisResult(
            requirement_id="FR-4",
            requirement_text="System musi szyfrować dane (krytyczne).",
            status="divergent",
            mapped_entities=["CryptoService"],
            issue_description="Rozbieżność między wymaganiem 'FR-4' a implementacją",
            confidence=0.4,
        )

        report = analyzer._build_report([divergent])

        assert report.total_requirements == 1
        assert report.divergent == 1
        # critical: divergent status + critical keyword ("krytyczne")
        assert report.critical_gaps == ["FR-4"]

        payload = gap_analysis_to_result_data(report, [divergent])
        assert payload["summary"]["divergent"] == 1
        assert payload["items"][0]["status"] == "divergent"

        restored = from_result_data(payload)
        assert restored["summary"]["divergent"] == 1
        assert restored["items"][0]["status"] == "divergent"


# ── AC1/AC2 / 5.2: logic_structures → CodeEntity ──────────────────────────────


class TestCodeEntitiesFromLogicStructures:
    def test_empty_when_no_payload(self):
        assert code_entities_from_logic_structures(None) == []
        assert code_entities_from_logic_structures({}) == []

    def test_functions_classes_methods_modules_become_entities(self):
        payload = {
            "functions": [
                {"name": "login", "file_path": "auth.py", "line_number": 12, "docstring": "Log in"},
                {"name": "_helper", "is_class_method": True},
            ],
            "classes": [
                {
                    "name": "UserService",
                    "file_path": "users.py",
                    "line_number": 7,
                    "docstring": "User service",
                    "methods": [{"name": "create", "docstring": "create user"}],
                }
            ],
            "modules": [{"name": "core", "file_path": "core/__init__.py"}],
        }

        entities = code_entities_from_logic_structures(payload)

        by_name = {e.name: e for e in entities}
        assert set(by_name) == {"login", "_helper", "UserService", "create", "core"}

        assert by_name["login"].type == "function"
        assert by_name["login"].file_path == "auth.py"
        assert by_name["login"].docstring == "Log in"

        # is_class_method flags a function as a method
        assert by_name["_helper"].type == "method"

        assert by_name["UserService"].type == "class"
        # class method falls back to the class file_path
        assert by_name["create"].type == "method"
        assert by_name["create"].file_path == "users.py"

        assert by_name["core"].type == "module"

    def test_skips_anonymous_entries(self):
        """Entries without a name are ignored (mirrors the glossary mapper)."""
        entities = code_entities_from_logic_structures({"functions": [{"file_path": "x.py"}, {"name": "ok"}]})
        assert [e.name for e in entities] == ["ok"]


# ── AC2/AC4 / 5.3: persistence round-trip + defaults ─────────────────────────


class TestPersistenceRoundTrip:
    def test_to_result_data_shape(self):
        report = CoverageReport(
            total_requirements=3,
            implemented=1,
            not_implemented=1,
            partial=1,
            divergent=0,
            coverage_percentage=33.3,
            critical_gaps=["FR-9"],
        )
        items = [
            GapAnalysisResult(
                requirement_id="FR-1",
                requirement_text="tekst",
                status="implemented",
                mapped_entities=["A"],
                issue_description=None,
                confidence=0.95,
            )
        ]

        payload = gap_analysis_to_result_data(report, items)

        assert set(payload) == {"summary", "items"}
        assert payload["summary"] == {
            "total_requirements": 3,
            "implemented": 1,
            "not_implemented": 1,
            "partial": 1,
            "divergent": 0,
            "coverage_percentage": 33.3,
            "critical_gaps": ["FR-9"],
        }
        assert payload["items"][0]["mapped_entities"] == ["A"]
        assert payload["items"][0]["issue_description"] is None

    def test_round_trip_preserves_summary_and_items(self):
        report = CoverageReport(
            total_requirements=2,
            implemented=1,
            not_implemented=0,
            partial=0,
            divergent=1,
            coverage_percentage=50.0,
            critical_gaps=["FR-7"],
        )
        items = [
            GapAnalysisResult(
                requirement_id="FR-7",
                requirement_text="tekst",
                status="divergent",
                mapped_entities=["X"],
                issue_description="opis",
                confidence=0.4,
            )
        ]

        restored = from_result_data(gap_analysis_to_result_data(report, items))

        assert restored["summary"]["coverage_percentage"] == 50.0
        assert restored["summary"]["divergent"] == 1
        assert restored["summary"]["critical_gaps"] == ["FR-7"]
        assert len(restored["items"]) == 1
        assert restored["items"][0]["status"] == "divergent"

    def test_from_result_data_defaults_when_missing(self):
        restored = from_result_data(None)
        assert restored["summary"]["coverage_percentage"] == 0.0
        assert restored["summary"]["total_requirements"] == 0
        assert restored["summary"]["critical_gaps"] == []
        assert restored["items"] == []

    def test_from_result_data_fills_partial_summary(self):
        """A payload missing some summary keys gets safe defaults."""
        restored = from_result_data({"summary": {"implemented": 2}, "items": []})
        assert restored["summary"]["implemented"] == 2
        assert restored["summary"]["not_implemented"] == 0
        assert restored["summary"]["coverage_percentage"] == 0.0
