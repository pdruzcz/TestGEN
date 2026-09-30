"""Unit tests for Story 3.15 TraceabilityService coverage + summary logic.

These exercise the pure helpers (element normalisation, deterministic UML
element ids) and the aggregation logic (``get_summary`` / ``_breakdown``) with a
mocked DB session, without requiring a live Postgres.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.models.traceability import CoverageStatus
from app.models.uml_diagram import DiagramType, UMLModelSource
from app.services.analysis.traceability_service import (
    TraceabilityService,
    _element_name,
    _element_type,
    _uml_element_id,
)


def _row(source_type="uml", element_type="use_case", status=CoverageStatus.COVERED):
    return SimpleNamespace(
        source_type=source_type,
        source_element_type=element_type,
        coverage_status=status,
    )


def _db_returning(rows):
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    db.execute = AsyncMock(return_value=result)
    return db


class TestHelpers:
    def test_element_name_prefers_name_then_label(self):
        assert _element_name({"name": "Login"}) == "Login"
        assert _element_name({"label": "Submit"}) == "Submit"
        assert _element_name({}) == "unnamed"

    def test_element_type_canonicalises_via_map(self):
        assert _element_type({"type": "usecase"}, "element") == "use_case"
        assert _element_type({"element_type": "interface"}, "element") == "class"
        # Unknown token falls through unchanged.
        assert _element_type({"type": "weird"}, "element") == "weird"

    # --- AC1: element_kind is read (post-3-1b consistency) ----------------
    def test_element_type_reads_element_kind_first(self):
        # XMI/PlantUML structural class carries element_kind, no element_type.
        assert _element_type({"element_kind": "class"}, "element") == "class"
        # interface / enum collapse to the class-like canonical type.
        assert _element_type({"element_kind": "interface"}, "element") == "class"
        assert _element_type({"element_kind": "enum"}, "element") == "class"

    def test_element_type_class_consistent_across_sources(self):
        # The same logical class — once from OCR (element_type), once from XMI
        # (element_kind) — MUST canonicalise identically (AC1 asymmetry fix).
        ocr_class = {"element_type": "class"}
        xmi_class = {"element_kind": "class"}
        assert _element_type(ocr_class, "element") == _element_type(xmi_class, "element") == "class"
        # Pre-fix the XMI class fell back to the default ("element"); assert it
        # no longer does.
        assert _element_type(xmi_class, "element") != "element"

    def test_element_type_element_kind_takes_precedence_over_visual_token(self):
        # If both are present (defensive), the structural discriminator wins.
        assert _element_type({"element_kind": "class", "element_type": "node"}, "element") == "class"

    # --- AC2: visual tokens decision/node mapped + category disambiguation
    def test_element_type_maps_visual_decision(self):
        assert _element_type({"element_type": "decision"}, "element") == "activity"

    def test_element_type_node_disambiguates_by_category(self):
        assert _element_type({"element_type": "node"}, "element", category="activity") == "activity"
        assert _element_type({"element_type": "node"}, "element", category="state_machine") == "state"
        # Without category context the generic "node" token is left intact.
        assert _element_type({"element_type": "node"}, "element") == "node"

    def test_uml_element_id_is_deterministic(self):
        diagram = uuid.uuid4()
        a = _uml_element_id(diagram, "use_case", "Login", 0)
        b = _uml_element_id(diagram, "use_case", "Login", 0)
        c = _uml_element_id(diagram, "use_case", "Login", 1)
        assert a == b
        assert a != c


class TestSummary:
    async def test_summary_percentages_and_breakdown(self):
        rows = [
            _row("uml", "use_case", CoverageStatus.COVERED),
            _row("uml", "use_case", CoverageStatus.UNCOVERED),
            _row("gui", "button", CoverageStatus.PARTIAL),
        ]
        service = TraceabilityService(_db_returning(rows))
        summary = await service.get_summary(uuid.uuid4())

        assert summary.uml_total == 2
        assert summary.gui_total == 1
        # 1 of 2 uml rows is non-uncovered → 50%.
        assert summary.uml_coverage_pct == 50.0
        # gui partial counts as tested → 100%.
        assert summary.gui_coverage_pct == 100.0
        # 1 covered of 3 total → 33.3% code coverage.
        assert summary.code_coverage_pct == 33.3

        uml_breakdown = summary.breakdown_per_uml_type
        assert len(uml_breakdown) == 1
        assert uml_breakdown[0].key == "use_case"
        assert uml_breakdown[0].total == 2
        assert uml_breakdown[0].covered == 1
        assert uml_breakdown[0].uncovered == 1

    async def test_summary_empty_project(self):
        service = TraceabilityService(_db_returning([]))
        summary = await service.get_summary(uuid.uuid4())
        assert summary.uml_total == 0
        assert summary.uml_coverage_pct == 0.0
        assert summary.code_coverage_pct == 0.0
        assert summary.breakdown_per_uml_type == []


class TestBreakdown:
    def test_breakdown_groups_by_element_type(self):
        rows = [
            _row("uml", "use_case", CoverageStatus.COVERED),
            _row("uml", "actor", CoverageStatus.UNCOVERED),
            _row("uml", "actor", CoverageStatus.PARTIAL),
        ]
        result = TraceabilityService._breakdown(rows, uuid.uuid4(), by="diagram")
        by_key = {b.key: b for b in result}
        assert by_key["actor"].total == 2
        assert by_key["actor"].partial == 1
        assert by_key["actor"].uncovered == 1
        assert by_key["use_case"].covered == 1


def _uml_db_returning(rows):
    """Mock DB whose execute().all() yields (diagram_id, diagram_type, parsed) tuples."""
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    db.execute = AsyncMock(return_value=result)
    return db


class TestProvenance:
    """AC3: parsed.source/confidence are carried onto collected UML elements."""

    async def test_ocr_source_and_confidence_threaded_onto_elements(self):
        parsed = SimpleNamespace(
            source=UMLModelSource.OCR,
            confidence=0.42,
            participants=[{"name": "Alice"}],
            elements=[{"element_kind": "class", "name": "Foo"}],
        )
        db = _uml_db_returning([(uuid.uuid4(), DiagramType.CLASS, parsed)])
        elements = await TraceabilityService(db)._collect_uml_elements(uuid.uuid4())

        assert elements, "expected collected elements"
        for el in elements:
            assert el.source == "ocr"
            assert el.confidence == 0.42

    async def test_structural_source_is_parser_with_null_confidence(self):
        parsed = SimpleNamespace(
            source=UMLModelSource.PARSER,
            confidence=None,
            participants=[],
            elements=[{"element_kind": "class", "name": "Bar"}],
        )
        db = _uml_db_returning([(uuid.uuid4(), DiagramType.CLASS, parsed)])
        elements = await TraceabilityService(db)._collect_uml_elements(uuid.uuid4())

        assert elements
        el = elements[0]
        assert el.source == "parser"
        assert el.confidence is None

    async def test_missing_source_yields_none(self):
        # A parsed model with no recorded source (defensive) → source None.
        parsed = SimpleNamespace(
            source=None,
            confidence=None,
            participants=[{"name": "X"}],
            elements=[],
        )
        db = _uml_db_returning([(uuid.uuid4(), DiagramType.SEQUENCE, parsed)])
        elements = await TraceabilityService(db)._collect_uml_elements(uuid.uuid4())
        assert elements[0].source is None
        assert elements[0].confidence is None
