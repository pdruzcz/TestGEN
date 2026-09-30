"""Unit tests for GapClassifier — Epic 5, Story 5.2.

Tests classification into 4 gap types (missing, different, extra, inconsistent),
context building with excerpts, severity assignment, and per-type summary.
"""

import pytest

from app.services.analysis.gap_analyzer import CodeEntity
from app.services.gap_analysis.classification_rules import (
    DIVERGENT_THRESHOLD,
    MISSING_THRESHOLD,
)
from app.services.gap_analysis.classifier import (
    EntityMapping,
    GapClassifier,
    TypeSummary,
)
from app.services.gap_analysis.comparator import RequirementData


# ── Helpers ──────────────────────────────────────────────────────────────────


def _entity(
    name: str,
    etype: str = "function",
    file_path: str = "src/app.py",
    line_number: int = 10,
    docstring: str | None = None,
) -> CodeEntity:
    return CodeEntity(
        entity_id=f"eid-{name}",
        name=name,
        type=etype,
        file_path=file_path,
        line_number=line_number,
        language="python",
        docstring=docstring,
    )


def _req(req_id: str, text: str, priority: str = "medium") -> RequirementData:
    return RequirementData(req_id=req_id, text=text, priority=priority)


# ── Missing classification ───────────────────────────────────────────────────


class TestClassifyMissing:
    def test_no_match_classifies_missing(self):
        cls = GapClassifier()
        req = _req("R1", "unique unknown feature zzz")
        mappings = [EntityMapping(requirement=req, best_entity=None, best_score=0.0)]
        findings, summary = cls.classify(mappings, [req], [])

        assert len(findings) == 1
        assert findings[0].gap_type == "missing"
        assert findings[0].code_entity_id is None

    def test_low_score_classifies_missing(self):
        cls = GapClassifier()
        req = _req("R1", "unique unknown feature zzz")
        entity = _entity("something_else")
        mappings = [EntityMapping(requirement=req, best_entity=entity, best_score=10.0)]
        findings, summary = cls.classify(mappings, [req], [entity])

        assert findings[0].gap_type == "missing"

    def test_missing_high_priority_is_critical(self):
        cls = GapClassifier()
        req = _req("R1", "critical security feature", priority="high")
        mappings = [EntityMapping(requirement=req, best_entity=None, best_score=0.0)]
        findings, summary = cls.classify(mappings, [req], [])

        assert findings[0].gap_type == "missing"
        assert findings[0].severity == "critical"

    def test_missing_medium_priority_is_warning(self):
        cls = GapClassifier()
        req = _req("R1", "some feature", priority="medium")
        mappings = [EntityMapping(requirement=req, best_entity=None, best_score=0.0)]
        findings, summary = cls.classify(mappings, [req], [])

        assert findings[0].severity == "warning"


# ── Different classification ─────────────────────────────────────────────────


class TestClassifyDifferent:
    def test_partial_match_classifies_different(self):
        cls = GapClassifier()
        req = _req("R1", "authenticate user with OAuth2")
        entity = _entity("auth", docstring="basic login form")
        score = (MISSING_THRESHOLD + DIVERGENT_THRESHOLD) / 2  # ~50
        mappings = [EntityMapping(requirement=req, best_entity=entity, best_score=score)]
        findings, summary = cls.classify(mappings, [req], [entity])

        different = [f for f in findings if f.gap_type == "different"]
        assert len(different) == 1
        assert different[0].code_entity_id == "eid-auth"

    def test_different_has_warning_severity(self):
        cls = GapClassifier()
        req = _req("R1", "authenticate user with OAuth2")
        entity = _entity("auth", docstring="basic login form")
        score = 50.0
        mappings = [EntityMapping(requirement=req, best_entity=entity, best_score=score)]
        findings, summary = cls.classify(mappings, [req], [entity])

        different = [f for f in findings if f.gap_type == "different"]
        assert different[0].severity == "warning"


# ── Extra classification ─────────────────────────────────────────────────────


class TestClassifyExtra:
    def test_code_without_requirement_is_extra(self):
        cls = GapClassifier()
        req = _req("R1", "authenticate user login password")
        entity_match = _entity("authenticate", docstring="authenticate user login password")
        entity_extra = _entity("generate_invoice_pdf")

        mappings = [
            EntityMapping(requirement=req, best_entity=entity_match, best_score=85.0),
        ]
        findings, summary = cls.classify(mappings, [req], [entity_match, entity_extra])

        extras = [f for f in findings if f.gap_type == "extra"]
        assert len(extras) == 1
        assert extras[0].code_entity_id == "eid-generate_invoice_pdf"
        assert extras[0].severity == "info"

    def test_excluded_patterns_skip_extra(self):
        cls = GapClassifier()
        req = _req("R1", "authenticate user login authentication")
        entity_match = _entity("authenticate", docstring="authenticate user login authentication")

        entities = [
            entity_match,
            _entity("test_authentication"),
            _entity("__init__"),
            _entity("conftest_setup"),
        ]
        mappings = [
            EntityMapping(requirement=req, best_entity=entity_match, best_score=85.0),
        ]
        findings, summary = cls.classify(mappings, [req], entities)

        extras = [f for f in findings if f.gap_type == "extra"]
        assert len(extras) == 0

    def test_extra_context_has_docstring(self):
        cls = GapClassifier()
        req = _req("R1", "authenticate user")
        entity_match = _entity("authenticate", docstring="authenticate user")
        entity_extra = _entity("generate_report", docstring="Generate PDF report from data")

        mappings = [
            EntityMapping(requirement=req, best_entity=entity_match, best_score=85.0),
        ]
        findings, summary = cls.classify(mappings, [req], [entity_match, entity_extra])

        extras = [f for f in findings if f.gap_type == "extra"]
        assert "docstring" in extras[0].context


# ── Inconsistent classification ──────────────────────────────────────────────


class TestClassifyInconsistent:
    def test_entity_mapped_to_multiple_requirements_with_spread(self):
        """When one entity is best match for 2+ reqs with large score spread."""
        cls = GapClassifier()
        entity = _entity("shared_handler")
        req1 = _req("R1", "handle user login")
        req2 = _req("R2", "generate financial report completely different thing")

        # R1 matches entity well, R2 matches partially → big score spread (>= 40)
        # Both must be >= MISSING_THRESHOLD (30) to be considered real mappings
        mappings = [
            EntityMapping(requirement=req1, best_entity=entity, best_score=80.0),
            EntityMapping(requirement=req2, best_entity=entity, best_score=35.0),
        ]
        all_scores = {
            "R1": {"eid-shared_handler": 80.0},
            "R2": {"eid-shared_handler": 35.0},
        }
        findings, summary = cls.classify(mappings, [req1, req2], [entity], all_scores)

        inconsistent = [f for f in findings if f.gap_type == "inconsistent"]
        assert len(inconsistent) >= 1
        assert all(f.severity == "critical" for f in inconsistent)


# ── Context building ─────────────────────────────────────────────────────────


class TestContextBuilding:
    def test_missing_context_has_excerpt(self):
        cls = GapClassifier()
        long_text = "A" * 200
        req = _req("R1", long_text)
        mappings = [EntityMapping(requirement=req, best_entity=None, best_score=0.0)]
        findings, summary = cls.classify(mappings, [req], [])

        assert "requirement_excerpt" in findings[0].context
        assert len(findings[0].context["requirement_excerpt"]) <= 150

    def test_different_context_has_code_excerpt(self):
        cls = GapClassifier()
        req = _req("R1", "authenticate user")
        entity = _entity("auth", docstring="A" * 200)
        score = 50.0
        mappings = [EntityMapping(requirement=req, best_entity=entity, best_score=score)]
        findings, summary = cls.classify(mappings, [req], [entity])

        different = [f for f in findings if f.gap_type == "different"]
        assert "code_excerpt" in different[0].context
        assert len(different[0].context["code_excerpt"]) <= 150


# ── Summary ──────────────────────────────────────────────────────────────────


class TestTypeSummary:
    def test_summary_has_all_types(self):
        cls = GapClassifier()
        findings, summary = cls.classify([], [], [])

        assert "missing" in summary
        assert "different" in summary
        assert "extra" in summary
        assert "inconsistent" in summary

    def test_summary_counts_match_findings(self):
        cls = GapClassifier()
        req1 = _req("R1", "unique unknown zzz1")
        req2 = _req("R2", "unique unknown zzz2")
        mappings = [
            EntityMapping(requirement=req1, best_entity=None, best_score=0.0),
            EntityMapping(requirement=req2, best_entity=None, best_score=0.0),
        ]
        findings, summary = cls.classify(mappings, [req1, req2], [])

        assert summary["missing"].count == 2
        assert summary["missing"].percentage == 100.0

    def test_summary_percentage_calculation(self):
        cls = GapClassifier()
        req = _req("R1", "authenticate user login password")
        entity_match = _entity("authenticate", docstring="authenticate user login password")
        entity_extra = _entity("unused_function")

        mappings = [
            EntityMapping(requirement=req, best_entity=entity_match, best_score=85.0),
        ]
        findings, summary = cls.classify(mappings, [req], [entity_match, entity_extra])

        # 1 missing (0), 0 different (0), 1 extra → total = 1
        assert summary["extra"].count == 1
        assert summary["extra"].percentage == 100.0
