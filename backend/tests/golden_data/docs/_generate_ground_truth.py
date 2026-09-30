"""Konsolidator ground-truth dla próbek dokumentacji — Story 2.11.

Czyta zamrożone wyjście natywnego pipeline (``_probe_out.json``) i emituje pliki
``<name>_ground_truth.json`` obok każdej próbki. Ground truth łączy:

* **intencję** (typ dokumentu, czy zawiera celowe niespójności) — autorską, oraz
* **zamrożone liczebności/teksty** z faktycznego wyjścia serwisów
  (klasyfikacja, wymagania, niespójności, glosariusz).

Testy golden (``test_document_*_golden.py``) operują na tych plikach: asercje
typu dokumentu, recall/precision ekstrakcji (dopasowanie znormalizowanego tekstu)
oraz obecność wykrywalnych typów niespójności (``duplicate``/``missing_reference``)
wyłącznie w próbkach rozbieżnych.

Uruchomienie (po ``_probe_out.json`` z ``_probe_json``)::

    cd backend
    python -m tests.golden_data.docs._generate_ground_truth

Skrypt konserwacyjny — regeneruje GT po celowej zmianie próbek lub serwisów.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent

# Intencje autorskie: które próbki mają celowe, wykrywalne niespójności.
HAS_DISCREPANCY = {
    "srs/srs_platnosci.docx",
    "brd/brd_system_logowania.pdf",
    "frd/frd_modul_uzytkownikow.pdf",
    "manual/podrecznik_operatora.md",
    "brd/brd_platnosci.docx",
}

# Konserwatywny próg pewności klasyfikacji (actuals mają margines).
MIN_CONFIDENCE = {
    "specyfikacja_wymagań": 50.0,
    "instrukcja_techniczna": 40.0,
    "podręcznik_użytkownika": 10.0,
}

DETECTABLE_TYPES = {"duplicate", "missing_reference"}


KNOWN_CATEGORIES = {"srs", "brd", "frd", "manual", "instruction"}


def build() -> None:
    probe = json.loads((Path.cwd() / "_probe_out.json").read_text(encoding="utf-8"))
    for rel, data in probe.items():
        sample_path = OUT / rel
        # Guard: tylko próbki w znanych kategoriach (pomija pliki top-level typu README).
        if sample_path.parent.name not in KNOWN_CATEGORIES:
            continue
        stem = sample_path.stem  # np. srs_system_logowania
        category = sample_path.parent.name  # srs/brd/frd/manual/instruction
        cls = data["classification"]
        reqs = data["requirements"]
        incs = data["inconsistencies"]
        terms = data["glossary"]

        detectable = [i["type"] for i in incs if i["type"] in DETECTABLE_TYPES]
        # Terminologia to szum detektora (kapitalizowane "System"/"Użytkownik" w 3+
        # wymaganiach) — celowo NIE traktujemy jej jako sygnału rozbieżności.

        gt = {
            "name": stem,
            "doc_category": category,
            "format": data["format"],
            "language": "pl",
            "has_intentional_discrepancies": rel in HAS_DISCREPANCY,
            "expected_classification": {
                "doc_type": cls["doc_type"],
                "min_confidence": MIN_CONFIDENCE.get(cls["doc_type"], 10.0),
            },
            "expected_requirements": {
                "min_count": len(reqs),
                "expected_texts": [r["text"] for r in reqs],
            },
            "expected_inconsistencies": {
                # Wykrywalne typy (duplicate/missing_reference) występują TYLKO
                # w próbkach rozbieżnych; w spójnych jest ich 0.
                "detectable_types": sorted(set(detectable)),
                "min_detectable_count": len(detectable),
            },
            "expected_glossary": {
                "min_terms": len(terms),
                "expected_terms": [t["term"] for t in terms],
            },
        }
        out_path = sample_path.with_name(f"{stem}_ground_truth.json")
        out_path.write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  GT: {out_path.relative_to(OUT)}  (reqs={len(reqs)}, incs={len(detectable)} wykrywalne)")


if __name__ == "__main__":
    build()
    print("Gotowe — ground-truth wygenerowany.")
