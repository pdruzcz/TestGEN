"""Loader próbek dokumentacji i harness analizy — Epic 2, Story 2.11.

Wydzielony z ``conftest.py``, by testy parametryczne mogły importować funkcje
bezpośrednio (``conftest`` nie jest importowalny z nazwy). Odkrywa próbki
``<name>.<ext>`` + ``<name>_ground_truth.json`` pod ``docs/`` i udostępnia
harness uruchamiający pełną natywną ścieżkę analizy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

GOLDEN_ROOT = Path(__file__).parent
DOCS_ROOT = GOLDEN_ROOT / "docs"

# Wykrywalne typy niespójności. Terminologia jest POMIJANA jako szum detektora
# (kapitalizowane "System"/"Użytkownik" powtarzające się w 3+ wymaganiach).
DETECTABLE_INCONSISTENCY_TYPES = ("duplicate", "missing_reference")


@dataclass(frozen=True)
class GoldenDocSample:
    """Próbka dokumentacji ze zamrożonym ground truth."""

    name: str
    doc_category: str  # srs/brd/frd/manual/instruction
    format: str  # pdf/docx/md/html/txt
    source_path: Path
    ground_truth: dict

    @property
    def id(self) -> str:
        return f"{self.doc_category}/{self.name}"

    @property
    def has_intentional_discrepancies(self) -> bool:
        return bool(self.ground_truth.get("has_intentional_discrepancies"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_doc_samples() -> list[GoldenDocSample]:
    """Odkryj pary ``<name>.<ext>`` + ``<name>_ground_truth.json`` pod ``docs/``."""
    samples: list[GoldenDocSample] = []
    if not DOCS_ROOT.exists():
        return samples
    for gt_file in sorted(DOCS_ROOT.rglob("*_ground_truth.json")):
        data = _load_json(gt_file)
        name = gt_file.stem.removesuffix("_ground_truth")
        fmt = data.get("format", "")
        source = gt_file.with_name(f"{name}.{fmt}")
        if not source.exists():
            continue  # ground truth bez pliku źródłowego — pomiń
        samples.append(
            GoldenDocSample(
                name=name,
                doc_category=data.get("doc_category", gt_file.parent.name),
                format=fmt,
                source_path=source,
                ground_truth=data,
            )
        )
    return samples


def normalize_doc_text(text: str) -> str:
    """Normalizacja tekstu do dopasowania wymagań/terminów (lowercase, whitespace)."""
    return " ".join((text or "").lower().split())


def analyze_document_sample(sample: GoldenDocSample) -> dict:
    """Uruchom pełną natywną ścieżkę na próbce; zwróć wyjścia serwisów.

    Leniwy import — kolekcja testów UML/GUI/visual nieściąga pakietu app.
    """
    from app.services.analysis.document import (
        classify_document,
        detect_inconsistencies,
        extract_glossary,
        extract_requirements,
        parse_and_preprocess_document,
    )
    from app.services.analysis.document.requirement_extractor import convert_to_schema

    doc = parse_and_preprocess_document(sample.source_path)
    requirements = extract_requirements(doc)
    inconsistencies = detect_inconsistencies(doc, [convert_to_schema(r) for r in requirements])
    return {
        "document": doc,
        "classification": classify_document(doc),
        "requirements": requirements,
        "inconsistencies": inconsistencies,
        "glossary": extract_glossary(doc),
    }


def detectable_inconsistencies(analysis: dict) -> list:
    """Filtruj tylko wykrywalne typy niespójności (pomijaj terminologię)."""
    return [i for i in analysis["inconsistencies"] if i.type in DETECTABLE_INCONSISTENCY_TYPES]
