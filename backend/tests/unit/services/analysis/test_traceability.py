"""Unit tests for the document traceability matrix — Story 2.9 closure.

Covers:
- AC1: ``generate_traceability_matrix`` maps requirements onto code entities
  (name matching) and assigns a ``coverage_status`` per requirement. The native
  matcher emits ``none`` (no code) / ``partial`` (code only, v1 has no tests) /
  ``full`` (code + tests, constructed). ``test_cases`` is empty in v1 (Story
  2.10 is separate), so ``full`` is only reachable here via an explicit test
  object exercising ``_find_test_cases`` (subtask 4.1).
- AC1: code entities come from Epic 1 ``logic_structures`` via the reused
  ``code_entities_from_logic_structures`` (functions/classes match by name)
  (subtask 4.2).
- AC2/AC4: ``traceability_to_result_data`` produces the flat ``result_data``
  shape (counts + ``coverage_percentage`` + ``entries``) (subtask 4.3).

Scope note: this is the Epic 2 document-centric matrix (requirement ↔ code ↔
test, persisted in ``AnalysisResult.result_data``). It is intentionally separate
from the Epic 3 UML-centric ``TraceabilityService`` (Story 3.15).
"""

from __future__ import annotations

from types import SimpleNamespace

from app.schemas.document import DocumentStructure, SectionStructure
from app.services.analysis.gap_analyzer import code_entities_from_logic_structures
from app.services.analysis.traceability import (
    TraceabilityMatrix,
    TraceabilityMatrixGenerator,
    generate_traceability_matrix,
    traceability_to_result_data,
)


def _section(section_id: str, title: str, content: str = "") -> SectionStructure:
    return SectionStructure(
        section_id=section_id,
        title=title,
        level=1,
        content=content,
        children=[],
    )


def _doc(*, filename: str | None = None) -> DocumentStructure:
    """Minimal document structure (the matcher reads only ``metadata``)."""
    metadata = {"filename": filename} if filename else {}
    return DocumentStructure(sections=[_section("s1", "Wymagania", "Treść")], metadata=metadata)


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


def _code_entity(name: str):
    """A code entity the matcher reads via ``.name`` (mirrors CodeEntity)."""
    return SimpleNamespace(name=name, type="function")


def _test_case(test_id: str, requirement_ids: list[str]):
    """A test case the matcher links via ``.requirement_ids`` (Story 2.10 stub)."""
    return SimpleNamespace(id=test_id, requirement_ids=requirement_ids)


# ── AC1 / 4.1: coverage status assignment (none / partial / full) ─────────────


class TestCoverageStatus:
    def test_none_when_no_matching_code(self):
        """A requirement with no matching code entity (and no tests) → ``none``."""
        matrix = generate_traceability_matrix(
            _doc(),
            [_req("FR-1", "System musi obsługiwać logowanie dwuskładnikowe.")],
            code_entities=[_code_entity("NiezwiązanaNazwa")],
            test_cases=[],
        )

        assert len(matrix.entries) == 1
        assert matrix.entries[0].coverage_status == "none"
        assert matrix.entries[0].code_entities == []
        assert matrix.entries[0].test_cases == []
        assert matrix.no_coverage == 1
        assert matrix.coverage_percentage == 0.0

    def test_partial_for_code_match_without_tests(self):
        """A requirement matched to code but with no tests → ``partial``.

        This is the honest v1 status: document pipeline has no test cases yet
        (Story 2.10 is separate), so any code-matched requirement is ``partial``.
        """
        matrix = generate_traceability_matrix(
            _doc(),
            [_req("FR-2", "System musi wywoływać funkcję login podczas uwierzytelniania.")],
            code_entities=[_code_entity("login")],
            test_cases=[],
        )

        assert matrix.entries[0].coverage_status == "partial"
        assert matrix.entries[0].code_entities == ["login"]
        assert matrix.entries[0].test_cases == []
        assert matrix.partial_coverage == 1

    def test_full_for_code_and_test_match(self):
        """A requirement matched to code AND a linked test case → ``full``.

        ``full`` is only reachable when test cases exist (follow-up after Story
        2.10); here we construct an explicit test object to exercise
        ``_find_test_cases``.
        """
        matrix = generate_traceability_matrix(
            _doc(),
            [_req("FR-3", "aplikacja musi rysować Raport na ekranie.")],
            code_entities=[_code_entity("Raport")],
            test_cases=[_test_case("TC-1", ["FR-3"])],
        )

        assert matrix.entries[0].coverage_status == "full"
        assert matrix.entries[0].code_entities == ["Raport"]
        assert matrix.entries[0].test_cases == ["TC-1"]
        assert matrix.full_coverage == 1
        assert matrix.coverage_percentage == 100.0

    def test_mixed_statuses_aggregate_correctly(self):
        """One of each status → counts and percentage reflect the mix."""
        matrix = generate_traceability_matrix(
            _doc(),
            [
                _req("FR-A", "aplikacja musi rysować Panel na ekranie."),  # code → partial
                _req("FR-B", "System musi wspierać eksport do formatu XYZ."),  # nothing → none
                _req("FR-C", "moduł Nagłówek renderuje tytuł"),  # code + test → full
            ],
            code_entities=[_code_entity("Panel"), _code_entity("Nagłówek")],
            test_cases=[_test_case("TC-C", ["FR-C"])],
        )

        assert matrix.total_requirements == 3
        assert matrix.full_coverage == 1
        assert matrix.partial_coverage == 1
        assert matrix.no_coverage == 1
        # full / total * 100 — the generator returns the raw float (no rounding)
        assert matrix.coverage_percentage == 1 / 3 * 100


# ── AC1 / 4.2: logic_structures → code entities → name matching ───────────────


class TestCodeEntitiesFromLogicStructures:
    def test_functions_and_classes_match_by_name(self):
        """Code entities derived from ``logic_structures`` match requirements by
        name (``code_entities_from_logic_structures`` reuse from Story 2.8)."""
        logic_structures = {
            "functions": [
                {"name": "login", "file_path": "auth.py", "line_number": 12},
            ],
            "classes": [
                {"name": "Raport", "file_path": "reports.py", "line_number": 7},
            ],
            "modules": [{"name": "core", "file_path": "core/__init__.py"}],
        }
        code_entities = code_entities_from_logic_structures(logic_structures)

        matrix = generate_traceability_matrix(
            _doc(),
            [
                _req("FR-1", "System musi używać funkcji login do logowania."),
                _req("FR-2", "aplikacja generuje Raport co noc."),
                _req("FR-3", "Brak jakiejkolwiek implementacji w tekście."),
            ],
            code_entities=code_entities,
            test_cases=[],
        )

        by_id = {e.requirement_id: e for e in matrix.entries}
        assert by_id["FR-1"].coverage_status == "partial"
        assert "login" in by_id["FR-1"].code_entities
        assert by_id["FR-2"].coverage_status == "partial"
        assert "Raport" in by_id["FR-2"].code_entities
        # "core" does not appear in FR-3 text → none
        assert by_id["FR-3"].coverage_status == "none"

    def test_empty_code_entities_resolves_everything_to_none(self):
        """No code analysis available → ``code_entities=[]`` → all ``none``.

        This is the graceful-degradation path (non-fatal, file still READY).
        """
        matrix = generate_traceability_matrix(
            _doc(),
            [_req("FR-1", "cokolwiek"), _req("FR-2", "coś innego")],
            code_entities=code_entities_from_logic_structures(None),
            test_cases=[],
        )

        assert all(e.coverage_status == "none" for e in matrix.entries)
        assert matrix.no_coverage == 2
        assert matrix.coverage_percentage == 0.0


# ── AC2/AC4 / 4.3: flat result_data shape ─────────────────────────────────────


class TestResultDataShape:
    def test_to_result_data_is_flat_with_counts_and_entries(self):
        """The persisted payload is flat (1:1 with the FE interface): top-level
        counts + ``coverage_percentage`` + ``entries`` (no summary/items)."""
        matrix = TraceabilityMatrix(
            document_name="spec.pdf",
            entries=[],  # populated via the generator below
            total_requirements=0,
            full_coverage=0,
            partial_coverage=0,
            no_coverage=0,
            coverage_percentage=0.0,
        )
        # Build a real matrix to assert the serializer mirrors computed fields.
        matrix = generate_traceability_matrix(
            _doc(filename="spec.pdf"),
            [
                _req("FR-1", "funkcja login"),  # partial
                _req("FR-2", "nic"),  # none
            ],
            code_entities=[_code_entity("login")],
            test_cases=[],
        )

        payload = traceability_to_result_data(matrix)

        # Flat shape — no summary/items nesting.
        assert set(payload) == {
            "document_name",
            "total_requirements",
            "full_coverage",
            "partial_coverage",
            "no_coverage",
            "coverage_percentage",
            "entries",
        }
        assert payload["document_name"] == "spec.pdf"
        assert payload["total_requirements"] == 2
        assert payload["full_coverage"] == 0
        assert payload["partial_coverage"] == 1
        assert payload["no_coverage"] == 1
        assert payload["coverage_percentage"] == 0.0

    def test_entries_length_equals_requirement_count_and_keys(self):
        """One entry per requirement; each entry carries the full field set."""
        matrix = generate_traceability_matrix(
            _doc(),
            [_req("FR-1", "x"), _req("FR-2", "y"), _req("FR-3", "login")],
            code_entities=[_code_entity("login")],
            test_cases=[],
        )

        payload = traceability_to_result_data(matrix)

        assert len(payload["entries"]) == 3
        assert payload["entries"][0] == {
            "requirement_id": "FR-1",
            "requirement_text": "x",
            "code_entities": [],
            "test_cases": [],
            "coverage_status": "none",
            "source_section_id": "s1",
        }
        matched = next(e for e in payload["entries"] if e["requirement_id"] == "FR-3")
        assert matched["code_entities"] == ["login"]
        assert matched["coverage_status"] == "partial"

    def test_generator_instance_matches_convenience_function(self):
        """The class and the convenience function produce identical output."""
        doc = _doc()
        reqs = [_req("FR-1", "funkcja login")]
        entities = [_code_entity("login")]

        via_class = TraceabilityMatrixGenerator().generate(doc, reqs, entities, [])
        via_func = generate_traceability_matrix(doc, reqs, entities, [])

        assert traceability_to_result_data(via_class) == traceability_to_result_data(via_func)
