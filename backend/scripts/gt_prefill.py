#!/usr/bin/env python
"""Generator SZKICÓW ground truth z surowej detekcji — Story 3-14c, T3.

Uruchamia ``GUIAnalyzerOrchestrator`` na PNG i wypisuje szkic pliku GT do
ręcznej korekty. **Wynik detektora nigdy nie staje się GT bez weryfikacji**
(błąd metodologiczny: detektor oceniałby sam siebie - konwencja 3-14b:
surowa detekcja na realnym UI zawyża 2-5x).

Dlatego szkic zapisuje się jako ``<nazwa>_prefill.json`` — przyrostek
CELowo inny niż ``_ground_truth.json``, żeby automatyczny discovery
(``conftest.discover_gui_samples``) go NIE podchwycił. Po kuracji (usuwanie
false-positive'ów OCR, poprawa labeli/bboxów, uzupełnienie `description`)
plik trzeba ręcznie zapisać jako ``<nazwa>_ground_truth.json``.

Uruchomienie (z katalogu backend):
    python scripts/gt_prefill.py                          # cały gui/real
    python scripts/gt_prefill.py tests/golden_data/gui/real/keycloak_login.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ``app`` jest zainstalowane (``pip install -e .``), ale ``tests`` nie jest —
# dodaj katalog backend, żeby importy działały samodzielnie (jak golden_accuracy).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis.gui.orchestrator import GUIAnalyzerOrchestrator

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "tests" / "golden_data" / "gui" / "real"

PREFILL_NOTE = (
    "SZKIC z surowej detekcji (gt_prefill.py) — NIE ZWERYFIKOWANE GT. "
    "Usuń false-positive (typowo fragmenty OCR jako button/checkbox), popraw "
    "label/bbox względem tego, co faktycznie widać na PNG, uzupełnij "
    "description, zapisz jako *_ground_truth.json."
)


def prefill_one(png: Path, orchestrator: GUIAnalyzerOrchestrator) -> dict:
    """Zwraca szkic GT (schema zgodne z *_ground_truth.json) dla jednego PNG."""
    output = orchestrator.analyze(png.read_bytes())
    components = []
    for c in output.components:
        if c.component_type.value == "unknown":
            continue  # „unknown" celowo poza metryką (konwencja story)
        components.append(
            {
                "component_type": c.component_type.value,
                "label": c.label or "",
                "bbox": {
                    "x": int(c.bbox.x),
                    "y": int(c.bbox.y),
                    "width": int(c.bbox.width),
                    "height": int(c.bbox.height),
                },
                "confidence": round(float(c.confidence), 2),
            }
        )
    return {
        "_prefill_note": PREFILL_NOTE,
        "category": "real",
        "description": "",  # kurator uzupełnia (źródło, viewport, stan interakcji)
        "expected_component_count": len(components),
        "expected_components": components,
        "_detector_warnings": output.warnings,
    }


def main(argv: list[str]) -> int:
    targets = argv[1:] or [str(DEFAULT_DIR)]
    pngs: list[Path] = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            pngs.extend(sorted(path.rglob("*.png")))
        elif path.suffix.lower() == ".png":
            pngs.append(path)
        else:
            print(f"pomijam (nie PNG/katalog): {path}", file=sys.stderr)

    if not pngs:
        print("Brak PNG do przetworzenia.", file=sys.stderr)
        return 1

    orchestrator = GUIAnalyzerOrchestrator()
    written, existing_gt, failed = [], [], []
    for png in pngs:
        gt = png.with_name(f"{png.stem}_ground_truth.json")
        if gt.exists():
            existing_gt.append(png.name)
            continue
        try:
            draft = prefill_one(png, orchestrator)
        except Exception as exc:  # detekcja nie może ubić całego przebiegu
            failed.append(f"{png.name}: {exc}")
            continue
        out = png.with_name(f"{png.stem}_prefill.json")
        out.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(out.name)
        print(f"{out.name}: {draft['expected_component_count']} komponentów (szkic)")

    print(f"\nszkice: {len(written)}, z istniejącym GT (pominięte): {len(existing_gt)}")
    if failed:
        print("nieudane:", file=sys.stderr)
        for f in failed:
            print(f"  - {f}", file=sys.stderr)
    print("Pamiętaj: *_prefill.json nie jest GT — po kuracji zapisz jako *_ground_truth.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
