"""Golden tests for gap analysis — Epic 5, Story 5.11.

Runs ComparatorService on hand-crafted code+documentation pairs spanning
Python, TypeScript, Java and C#. Validates:

- Recall ≥ 75% (correctly identifies implemented requirements)
- Compliance accuracy ≥ 80% (gap-count classification matches expected within tolerance)

Golden data lives under tests/golden_data/gap_analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.analysis.gap_analyzer import CodeEntity
from app.services.gap_analysis.comparator import (
    ComparatorService,
    RequirementData,
)

GOLDEN_DIR = Path(__file__).parent.parent / "golden_data" / "gap_analysis"

RECALL_THRESHOLD = 0.75  # AC1: minimum recall
MISSING_COUNT_TOLERANCE = 1  # AC2: |actual_missing - expected_missing| ≤ 1
COMPLIANCE_ACCURACY_THRESHOLD = 0.80  # AC2: minimum compliance accuracy


def _load_golden_cases() -> list[tuple[str, dict]]:
    """Load every JSON golden case file in the golden data dir."""
    cases = []
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        cases.append((data["name"], data))
    return cases


GOLDEN_CASES = _load_golden_cases()


def _to_requirements(data: dict) -> list[RequirementData]:
    return [
        RequirementData(
            req_id=r["req_id"],
            text=r["text"],
            category=r.get("category", ""),
            priority=r.get("priority", "medium"),
        )
        for r in data["requirements"]
    ]


def _to_code_entities(data: dict) -> list[CodeEntity]:
    return [
        CodeEntity(
            entity_id=ce["entity_id"],
            name=ce["name"],
            type=ce["type"],
            file_path=ce["file_path"],
            line_number=ce["line_number"],
            language=ce["language"],
            docstring=ce.get("docstring"),
        )
        for ce in data["code_entities"]
    ]


def _compute_recall(findings: list, expected: dict) -> float:
    """Recall: fraction of expected missing reqs correctly flagged as missing.

    Also accounts for expected-implemented reqs not being flagged missing.
    """
    expected_missing = set(expected.get("missing_req_ids", []))
    expected_implemented = set(expected.get("implemented_req_ids", []))

    flagged_missing = {
        f.requirement_id for f in findings
        if f.gap_type == "missing" and f.requirement_id
    }

    tp = len(expected_missing & flagged_missing)
    fn = len(expected_missing - flagged_missing)
    tn = len(expected_implemented - flagged_missing)
    fp = len(expected_implemented & flagged_missing)

    denom = tp + fn + tn + fp
    if denom == 0:
        return 1.0
    return (tp + tn) / denom


def _missing_count_within_tolerance(findings: list, expected: dict) -> bool:
    """Compliance accuracy: |actual_missing - expected_missing| ≤ tolerance."""
    expected_missing_n = len(expected.get("missing_req_ids", []))
    actual_missing_n = sum(
        1 for f in findings if f.gap_type == "missing" and f.requirement_id
    )
    return abs(actual_missing_n - expected_missing_n) <= MISSING_COUNT_TOLERANCE


# ── Per-case tests ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("case_name,case_data", GOLDEN_CASES, ids=[c[0] for c in GOLDEN_CASES])
class TestGoldenGapAnalysis:
    """Parametrized test that runs every golden pair through ComparatorService."""

    def test_runs_without_error(self, case_name: str, case_data: dict):
        reqs = _to_requirements(case_data)
        codes = _to_code_entities(case_data)
        service = ComparatorService()
        findings, summary = service.compare(reqs, codes)
        assert isinstance(findings, list)
        assert summary.total_requirements == len(reqs)

    def test_recall_above_threshold(self, case_name: str, case_data: dict):
        reqs = _to_requirements(case_data)
        codes = _to_code_entities(case_data)
        service = ComparatorService()
        findings, _ = service.compare(reqs, codes)

        recall = _compute_recall(findings, case_data["expected"])
        assert recall >= RECALL_THRESHOLD, (
            f"{case_name}: recall {recall:.2f} below threshold {RECALL_THRESHOLD} "
            f"(flagged_missing={[f.requirement_id for f in findings if f.gap_type == 'missing']})"
        )

    def test_missing_count_within_tolerance(self, case_name: str, case_data: dict):
        """AC2 per-case: missing count must be within ±1 of expected."""
        reqs = _to_requirements(case_data)
        codes = _to_code_entities(case_data)
        service = ComparatorService()
        findings, _ = service.compare(reqs, codes)

        assert _missing_count_within_tolerance(findings, case_data["expected"]), (
            f"{case_name}: missing count diverges from expected by >{MISSING_COUNT_TOLERANCE}"
        )


# ── Aggregate metrics ────────────────────────────────────────────────────────


class TestGoldenAggregate:
    """Aggregate metrics across all golden cases (AC1 + AC2)."""

    def test_at_least_10_golden_cases(self):
        assert len(GOLDEN_CASES) >= 10, (
            f"Expected ≥10 golden cases, found {len(GOLDEN_CASES)}"
        )

    def test_covers_multiple_languages(self):
        languages = {c["language"] for _, c in GOLDEN_CASES}
        assert languages >= {"python", "typescript"}, (
            f"Expected at least Python + TypeScript, got {languages}"
        )
        assert len(languages) >= 3, (
            f"Expected ≥3 languages, got {sorted(languages)}"
        )

    def test_average_recall_above_threshold(self):
        service = ComparatorService()
        recalls: list[float] = []
        for _, case_data in GOLDEN_CASES:
            reqs = _to_requirements(case_data)
            codes = _to_code_entities(case_data)
            findings, _ = service.compare(reqs, codes)
            recalls.append(_compute_recall(findings, case_data["expected"]))

        avg_recall = sum(recalls) / len(recalls)
        assert avg_recall >= RECALL_THRESHOLD, (
            f"Average recall {avg_recall:.2f} below {RECALL_THRESHOLD}; "
            f"per-case: {[f'{r:.2f}' for r in recalls]}"
        )

    def test_compliance_accuracy_above_threshold(self):
        """AC2: ≥80% of golden cases must have missing count within tolerance."""
        service = ComparatorService()
        hits = 0
        total = 0
        for _, case_data in GOLDEN_CASES:
            reqs = _to_requirements(case_data)
            codes = _to_code_entities(case_data)
            findings, _ = service.compare(reqs, codes)
            if _missing_count_within_tolerance(findings, case_data["expected"]):
                hits += 1
            total += 1

        accuracy = hits / total
        assert accuracy >= COMPLIANCE_ACCURACY_THRESHOLD, (
            f"Compliance accuracy {accuracy:.2f} below {COMPLIANCE_ACCURACY_THRESHOLD} "
            f"({hits}/{total} within missing-count tolerance ±{MISSING_COUNT_TOLERANCE})"
        )
