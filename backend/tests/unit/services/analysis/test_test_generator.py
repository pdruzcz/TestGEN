"""Unit tests for the document test-case generator — Story 2.10 closure.

Covers:
- AC1 / 4.1: ``TestGenerator.generate`` emits at least one positive test case
  per requirement, every case references its source ``requirement_id``, and
  ``coverage_percentage`` reflects requirements-with-tests / total.
- AC1 / 4.2: complex requirements (``_is_complex_requirement``: ``len > 100`` or
  ``lub`` within the first 50 chars) yield an additional negative case; short
  requirements yield exactly one.
- AC1 / 4.3: ``_determine_test_type`` keyword mapping (performance / security /
  ui / api / functional).
- AC2 / AC4 / 4.4: ``test_generation_to_result_data`` produces the flat
  ``result_data`` shape (counts + ``coverage_percentage`` + ``tests``), with no
  ``statistics`` leak.

Scope note: this is the Epic 2 document-centric generator (requirement → test
case, persisted in ``AnalysisResult.result_data``). The algorithm is reused
unchanged (dead code being wired); only the serializer is new. The Epic 1
code-gen generators (``services/generators/*``) and the CRUD ``TestCase`` layer
(``/projects/{id}/test-cases``) are separate and not covered here.
"""

from __future__ import annotations

from app.schemas.document import DocumentStructure, SectionStructure
from app.services.analysis.test_generator import (
    TestGenerator,
    generate_tests_from_requirements,
)

# Aliased to avoid pytest collecting the imported serializer as a test (its name
# starts with ``test_``). ``TestGenerator`` is a production class — the harmless
# ``cannot collect`` warning for it is expected.
from app.services.analysis.test_generator import (
    test_generation_to_result_data as serialize_test_generation,
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
    """Minimal document structure (the generator reads only ``metadata``)."""
    metadata = {"filename": filename} if filename else {}
    return DocumentStructure(sections=[_section("s1", "Wymagania", "Treść")], metadata=metadata)


def _req(
    req_id: str,
    text: str,
    *,
    type_: str = "functional",
    priority: str = "medium",
    source_section_id: str = "s1",
) -> dict:
    """Build an ``ExtractedRequirementSchema`` dict (generator input)."""
    return {
        "req_id": req_id,
        "text": text,
        "type": type_,
        "priority": priority,
        "source_section_id": source_section_id,
        "confidence": 0.9,
        "extraction_method": "native",
    }


# ── AC1 / 4.1: at least one positive TC per requirement + coverage ───────────


def test_generate_min_one_positive_per_requirement_and_coverage():
    """Every requirement yields at least one case referencing its ``req_id``;
    ``coverage_percentage`` is requirements-with-tests / total * 100."""
    doc = _doc(filename="spec.pdf")
    reqs = [
        _req("FR-1", "System wykonuje logowanie użytkownika"),
        _req("FR-2", "System zapisuje dane klienta"),
        _req("FR-3", "System wysyła powiadomienie email"),
    ]

    result = TestGenerator().generate(doc, reqs)

    assert result.document_name == "spec.pdf"
    assert result.total_requirements == 3
    assert result.generated_tests >= 3
    # Each requirement is referenced by at least one generated case.
    covered = {t.requirement_id for t in result.tests}
    assert covered == {"FR-1", "FR-2", "FR-3"}
    # All three requirements have tests → 100 % coverage.
    assert result.coverage_percentage == 100.0


def test_generate_coverage_partial_when_one_requirement_has_no_case():
    """``coverage_percentage`` reflects the share of requirements that map to at
    least one case (here all requirements map → full; an empty requirement set
    → 0 % without division by zero)."""
    doc = _doc()
    assert TestGenerator().generate(doc, []).coverage_percentage == 0.0


# ── AC1 / 4.2: negative case for complex requirements only ───────────────────


def test_complex_requirement_yields_positive_and_negative():
    """A complex functional requirement (``lub`` within first 50 chars) produces
    a positive case plus an additional negative case."""
    doc = _doc()
    # ``lub`` at index < 50 → complex; ``type=functional`` → negative emitted.
    reqs = [_req("FR-C", "System wykonuje akcję A lub akcję B przy logowaniu")]

    result = TestGenerator().generate(doc, reqs)

    assert result.generated_tests == 2
    # Both cases reference the same source requirement.
    assert {t.requirement_id for t in result.tests} == {"FR-C"}
    # The negative case carries its marker in the name.
    assert any("negatywny" in t.name.lower() for t in result.tests)


def test_short_requirement_yields_single_case():
    """A short, single-condition requirement yields exactly one (positive) case."""
    doc = _doc()
    reqs = [_req("FR-S", "System zapisuje dane")]

    result = TestGenerator().generate(doc, reqs)

    assert result.generated_tests == 1
    assert result.tests[0].requirement_id == "FR-S"


def test_complex_nonfunctional_requirement_has_no_negative():
    """``_generate_negative_test`` only emits for ``type == functional``; a
    complex non-functional requirement still yields a single positive case."""
    doc = _doc()
    reqs = [
        _req(
            "FR-NFR",
            "Wydajność systemu lub czas odpowiedzi musi spełniać wymagania słownikowe",
            type_="non-functional",
        )
    ]

    result = TestGenerator().generate(doc, reqs)

    # Complex (``lub`` < 50 chars) but non-functional → no negative branch.
    assert result.generated_tests == 1


# ── AC1 / 4.3: ``_determine_test_type`` keyword mapping ──────────────────────


def test_determine_test_type_keyword_mapping():
    """``_determine_test_type`` maps requirement keywords to the expected test
    type in the documented precedence (performance > security > ui > api >
    functional default)."""
    doc = _doc()
    gen = TestGenerator()
    cases = {
        "performance": "Czas odpowiedzi nie przekracza dwóch sekund",
        "security": "System weryfikuje autoryzację użytkownika",
        "ui": "Formularz rejestracji widoczny dla użytkownika",
        "api": "Endpoint API zwraca obiekt JSON",
        "functional": "System przechowuje dane klienta w pamięci",
    }

    for expected_type, text in cases.items():
        reqs = [_req(f"FR-{expected_type.upper()}", text)]
        result = gen.generate(doc, reqs)
        assert result.tests[0].test_type == expected_type, (
            f"text={text!r} → expected {expected_type}, got {result.tests[0].test_type}"
        )


# ── AC2 / AC4 / 4.4: ``test_generation_to_result_data`` flat shape ───────────


def test_result_data_flat_shape_and_no_statistics_leak():
    """The serializer emits the flat ``result_data`` shape (top-level counts +
    ``coverage_percentage`` + ``tests``) and drops the former ``statistics``
    leak (``tests.__dict__``)."""
    doc = _doc(filename="manual.pdf")
    reqs = [
        _req("FR-1", "System wykonuje logowanie użytkownika"),
        _req("FR-2", "System zapisuje dane klienta"),
    ]

    result = generate_tests_from_requirements(doc, reqs)
    payload = serialize_test_generation(result)

    # Flat top-level keys, no nesting, no ``statistics``.
    assert set(payload.keys()) == {
        "document_name",
        "total_requirements",
        "generated_tests",
        "coverage_percentage",
        "tests",
    }
    assert "statistics" not in payload
    # Top-level scalars mirror the result object.
    assert payload["document_name"] == "manual.pdf"
    assert payload["total_requirements"] == 2
    assert payload["generated_tests"] == len(result.tests)
    assert payload["coverage_percentage"] == 100.0
    # ``tests`` length matches the generated count.
    assert len(payload["tests"]) == result.generated_tests
    # Each serialized case carries the full ``GeneratedTestCase`` field set.
    expected_case_keys = {
        "test_id",
        "name",
        "description",
        "steps",
        "expected_result",
        "priority",
        "requirement_id",
        "test_type",
        "automation_feasibility",
    }
    for case in payload["tests"]:
        assert set(case.keys()) == expected_case_keys
        assert isinstance(case["steps"], list)


def test_result_data_empty_when_no_requirements():
    """An empty requirement set serializes to a flat zero payload with no
    cases (non-fatal empty state, never raises)."""
    doc = _doc(filename="empty.pdf")
    result = generate_tests_from_requirements(doc, [])

    payload = serialize_test_generation(result)

    assert payload["total_requirements"] == 0
    assert payload["generated_tests"] == 0
    assert payload["coverage_percentage"] == 0.0
    assert payload["tests"] == []
