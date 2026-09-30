"""Unit tests for the inconsistency detector — Story 2.7 closure.

Covers:
- AC1: contradiction detection with FIXED regex patterns. The prior patterns
  ``(r"musi\\sfować", r"nie\\s+może\\s+fzać")`` were typos that never matched,
  so the must/cannot contradiction type was silently dead. This is the keystone
  regression (subtask 5.1).
- AC1: terminology / missing_reference / duplicate detection (subtask 5.2).
- AC5: persistence helpers ``inconsistencies_to_result_data`` /
  ``from_result_data`` round-trip with the ``status`` field (subtask 5.3).
"""

from __future__ import annotations

from app.schemas.document import DocumentStructure, SectionStructure
from app.services.analysis.document.inconsistency_detector import (
    Inconsistency,
    InconsistencyDetector,
    detect_inconsistencies,
    from_result_data,
    inconsistencies_to_result_data,
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
    """Minimal document structure (terminology detection accepts any doc)."""
    return DocumentStructure(sections=[_section("s1", "Wymagania", "Treść")])


def _req(
    req_id: str,
    text: str,
    *,
    type_: str = "functional",
    source_section_id: str | None = "s1",
) -> dict:
    """Build an ``ExtractedRequirementSchema`` dict (detector input)."""
    return {
        "req_id": req_id,
        "text": text,
        "type": type_,
        "priority": "medium",
        "source_section_id": source_section_id,
        "confidence": 0.9,
        "extraction_method": "native",
    }


def _types(items: list[Inconsistency]) -> set[str]:
    return {it.type for it in items}


# ── AC1 / 5.1: contradiction detection (FIXED regex) ─────────────────────────


class TestContradictionDetection:
    def test_musi_vs_nie_moze_is_detected(self):
        """Regression (keystone): ``musi X`` vs ``nie może X`` about the same
        topic must register a contradiction. The old typo patterns matched
        nothing, so this used to return zero contradictions."""
        requirements = [
            _req("FR-1", "System Logowania musi obsługiwać uwierzytelnianie dwupoziomowe."),
            _req("FR-2", "System Logowania nie może obsługiwać uwierzytelniania dwupoziomowego."),
        ]
        items = InconsistencyDetector().detect(_doc(), requirements)

        contradictions = [it for it in items if it.type == "contradiction"]
        assert contradictions, "oczekiwano sprzeczności musi/nie może (regex naprawiony)"
        c = contradictions[0]
        assert c.severity == "critical"
        assert set(c.affected_requirements) == {"FR-1", "FR-2"}
        assert c.suggestion is not None

    def test_musi_vs_nie_moze_symmetric(self):
        """Symmetric: positive (musi) in req2, negative (nie może) in req1 must
        also be detected — the matcher checks both directions."""
        requirements = [
            _req("FR-1", "Moduł Płatności nie może zapisywać danych karty."),
            _req("FR-2", "Moduł Płatności musi zapisywać dane karty."),
        ]
        items = InconsistencyDetector().detect(_doc(), requirements)
        assert "contradiction" in _types(items)

    def test_numeric_max_min_contradiction_still_works(self):
        """Regression: the unchanged max/min numeric pattern must still fire."""
        requirements = [
            _req("FR-1", "Moduł Logowania dopuszcza maksimum 5 prób logowania."),
            _req("FR-2", "Moduł Logowania wymaga minimum 3 prób logowania."),
        ]
        items = InconsistencyDetector().detect(_doc(), requirements)
        assert "contradiction" in _types(items)

    def test_unrelated_musi_vs_nie_moze_not_flagged(self):
        """Negative: ``musi``/``nie może`` about different topics (no shared
        keywords) must NOT be flagged — the similar-keywords guard prevents
        unrelated pairs from becoming false contradictions."""
        requirements = [
            _req("FR-1", "System Płatności musi obsługiwać BLIK."),
            _req("FR-2", "Moduł Powiadomień nie może wysyłać spamu."),
        ]
        items = InconsistencyDetector().detect(_doc(), requirements)
        assert "contradiction" not in _types(items)

    def test_no_contradiction_when_single_requirement(self):
        """A lone ``musi`` requirement has nothing to contradict."""
        requirements = [_req("FR-1", "System Logowania musi obsługiwać sesje.")]
        items = InconsistencyDetector().detect(_doc(), requirements)
        assert "contradiction" not in _types(items)


# ── AC1 / 5.2: the other three types ──────────────────────────────────────────


class TestOtherTypes:
    def test_terminology_detected_when_entity_in_many_reqs(self):
        """>2 requirements referencing the same entity → terminology
        inconsistency (detection logic unchanged in v1)."""
        requirements = [
            _req("FR-1", "Interfejs musi umożliwiać rejestrację Użytkownika."),
            _req("FR-2", "Panel musi pokazywać profil Użytkownika."),
            _req("FR-3", "System musi logować Użytkownika po hasłe."),
        ]
        items = InconsistencyDetector().detect(_doc(), requirements)
        assert "terminology" in _types(items)

    def test_missing_reference_detected(self):
        """A requirement referencing an ID that is not in the requirement set
        → missing_reference inconsistency.

        Note (pre-existing, out of scope per story decision #2): the detector's
        ``reference_pattern.findall`` captures the group prefix only (``FR``),
        not the full ``FR-99`` — detection still fires, which is all AC1/5.2
        asserts here. ``missing_reference`` logic is explicitly unchanged.
        """
        requirements = [
            _req("FR-1", "System realizuje zachowanie FR-99 podczas logowania."),
            _req("FR-2", "System realizuje autoryzację po zalogowaniu."),
        ]
        items = InconsistencyDetector().detect(_doc(), requirements)
        assert "missing_reference" in _types(items)

    def test_duplicate_detected_for_near_identical_reqs(self):
        """Two same-type, near-identical requirements (Jaccard > 0.85) →
        duplicate inconsistency."""
        requirements = [
            _req("FR-1", "System musi logować użytkownika loginem i hasłem."),
            _req("FR-2", "System musi logować użytkownika loginem i hasłem."),
        ]
        items = InconsistencyDetector().detect(_doc(), requirements)
        dups = [it for it in items if it.type == "duplicate"]
        assert dups
        assert set(dups[0].affected_requirements) == {"FR-1", "FR-2"}

    def test_duplicate_not_cross_type(self):
        """Duplicate detection is type-scoped: a functional and a
        non-functional requirement with identical text are not duplicates."""
        requirements = [
            _req("FR-1", "System musi logować użytkownika loginem i hasłem.", type_="functional"),
            _req("NF-1", "System musi logować użytkownika loginem i hasłem.", type_="non-functional"),
        ]
        items = InconsistencyDetector().detect(_doc(), requirements)
        assert "duplicate" not in _types(items)


# ── AC5 / 5.3: persistence helpers + status ───────────────────────────────────


class TestSerialization:
    def test_to_result_data_uses_items_key_and_status_open(self):
        items = InconsistencyDetector().detect(
            _doc(),
            [
                _req("FR-1", "System musi logować użytkownika loginem i hasłem."),
                _req("FR-2", "System musi logować użytkownika loginem i hasłem."),
            ],
        )
        assert items  # sanity: something was detected

        payload = inconsistencies_to_result_data(items)

        assert set(payload.keys()) == {"items"}
        assert len(payload["items"]) == len(items)
        for element in payload["items"]:
            assert set(element.keys()) == {
                "inconsistency_id",
                "type",
                "severity",
                "description",
                "affected_requirements",
                "suggestion",
                "source_section_id",
                "status",
            }
            assert element["status"] == "open"
            assert isinstance(element["affected_requirements"], list)

    def test_round_trip_preserves_all_fields(self):
        items = InconsistencyDetector().detect(
            _doc(),
            [
                _req("FR-1", "System musi logować użytkownika loginem i hasłem."),
                _req("FR-2", "System musi logować użytkownika loginem i hasłem."),
            ],
        )
        payload = inconsistencies_to_result_data(items)
        restored = from_result_data(payload)

        assert restored == payload["items"]

    def test_from_result_data_handles_empty(self):
        assert from_result_data(None) == []
        assert from_result_data({}) == []
        assert from_result_data({"items": []}) == []

    def test_from_result_data_defaults_status_when_missing(self):
        """Legacy payloads written before the workflow status existed must
        normalize to ``status="open"``."""
        legacy = {
            "items": [
                {
                    "inconsistency_id": "inc-1",
                    "type": "duplicate",
                    "severity": "medium",
                    "description": "d",
                    "affected_requirements": ["FR-1", "FR-2"],
                    "suggestion": None,
                    "source_section_id": None,
                }
            ]
        }
        restored = from_result_data(legacy)
        assert len(restored) == 1
        assert restored[0]["status"] == "open"
        assert restored[0]["affected_requirements"] == ["FR-1", "FR-2"]


# ── convenience function ──────────────────────────────────────────────────────


class TestDetectInconsistencies:
    def test_module_function_matches_class(self):
        """``detect_inconsistencies(doc, requirements)`` is the convenience
        entry point used by the pipeline (Task 2)."""
        requirements = [
            _req("FR-1", "System musi logować użytkownika loginem i hasłem."),
            _req("FR-2", "System musi logować użytkownika loginem i hasłem."),
        ]
        assert "duplicate" in _types(detect_inconsistencies(_doc(), requirements))
