"""Golden: integralność zbioru dokumentacji — Story 2.11 (AC1, AC2).

Waliduje POKRYCIE zbioru (10 próbek, formaty, kategorie, rozkład niespójności
5/5, język polski) — niezależnie od wyjścia serwisów. Bramka strukturalna.
"""

from __future__ import annotations

from collections import Counter

import pytest

from tests.golden_data.doc_samples import DOCS_ROOT, discover_doc_samples

SAMPLES = discover_doc_samples()


@pytest.mark.golden
def test_at_least_10_samples() -> None:
    assert len(SAMPLES) >= 10, f"oczekiwano >=10 próbek, jest {len(SAMPLES)}"


@pytest.mark.golden
def test_format_coverage() -> None:
    counts = Counter(s.format for s in SAMPLES)
    assert counts["pdf"] >= 4, f"PDF >=4, jest {counts['pdf']}"
    assert counts["docx"] >= 3, f"DOCX >=3, jest {counts['docx']}"
    assert counts["md"] >= 2, f"MD >=2, jest {counts['md']}"
    assert counts["html"] >= 1, f"HTML >=1, jest {counts['html']}"


@pytest.mark.golden
def test_category_coverage() -> None:
    counts = Counter(s.doc_category for s in SAMPLES)
    assert counts["srs"] >= 3, f"SRS >=3, jest {counts['srs']}"
    assert counts["brd"] >= 2, f"BRD >=2, jest {counts['brd']}"
    assert counts["frd"] >= 2, f"FRD >=2, jest {counts['frd']}"
    assert counts["manual"] >= 2, f"Manual >=2, jest {counts['manual']}"
    assert counts["instruction"] >= 1, f"Instruction >=1, jest {counts['instruction']}"


@pytest.mark.golden
def test_discrepancy_distribution_5_5() -> None:
    with_disc = [s for s in SAMPLES if s.has_intentional_discrepancies]
    clean = [s for s in SAMPLES if not s.has_intentional_discrepancies]
    assert len(with_disc) >= 5, f"próbki z niespójnościami >=5, jest {len(with_disc)}"
    assert len(clean) >= 5, f"próbki spójne >=5, jest {len(clean)}"


@pytest.mark.golden
def test_all_samples_polish() -> None:
    assert all(s.ground_truth.get("language") == "pl" for s in SAMPLES)


@pytest.mark.golden
def test_all_source_files_exist() -> None:
    missing = [s.id for s in SAMPLES if not s.source_path.exists()]
    assert missing == [], f"brakujące pliki źródłowe: {missing}"


@pytest.mark.golden
def test_no_orphan_ground_truth_files() -> None:
    """Każdy ground-truth JSON ma odpowiadający plik źródłowy (z discovery)."""
    all_gt = sorted(DOCS_ROOT.rglob("*_ground_truth.json")) if DOCS_ROOT.exists() else []
    # wszystkie GT są odkryte (mają źródło) — porównanie liczności.
    assert len(SAMPLES) == len(all_gt), (
        f"odkryto {len(SAMPLES)} próbek, ale jest {len(all_gt)} plików ground_truth (niektóre bez źródła)"
    )
