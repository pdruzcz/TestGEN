#!/usr/bin/env python
"""UML/GUI golden-dataset accuracy artefact generator + gate (Story 3.14, AC4).

Emits ``test-results/golden-accuracy.json`` documenting per-sample counts vs the
frozen ground truth (PlantUML/XMI) and visual recognition accuracy (SVG). The
exit code is the threshold gate: non-zero if any text sample under-reports
beyond the 10 % tolerance or any SVG sample drops below the 70 % accuracy bar.

Story 3-14c (AC4): the artefact also carries a **per-component-type GUI report**
(``gui_types``) — GT vs detected counts and the detected/GT ratio for each of
the 11 ``GUIComponentType`` values, so NFR-ACC-001 (">80% dla 10 typów") is
evidenced per type, not just globally. GT counts come from the curated ground
truth (always available); detected counts require the imaging stack (cv2) and
are ``null`` when it is absent — the report structure stays stable either way.

The image-gated raster/PDF path (cv2/Tesseract/PyMuPDF) is otherwise intentionally
absent from this always-on artefact — those deps are optional and skipped without
failing the suite (Story 3.14 closure, AC2/AC4).

Run from the backend dir:   python scripts/golden_accuracy.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# ``app`` is an installed package (``pip install -e .``), but ``tests`` is not;
# add the backend root so the golden-data loaders import standalone.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis.uml.orchestrator import UMLParserOrchestrator
from app.services.analysis.uml.visual_parser import VisualUMLParser
from tests.golden_data.conftest import discover_gui_samples, discover_uml_samples, discover_uml_visual_samples

TOLERANCE = 0.10
VISUAL_THRESHOLD = 0.70
_BACKEND = Path(__file__).resolve().parents[1]

_COUNT_KEYS = ("participants", "elements", "relationships", "fragments", "flows")

# 11 typów GUIComponentType objętych metryką NFR-ACC-001 (``unknown`` celowo
# poza metryką — konwencja Story 3-14c).
GUI_TYPE_KEYS = (
    "button",
    "input",
    "dropdown",
    "checkbox",
    "radio",
    "menu",
    "link",
    "table",
    "form",
    "modal",
    "tab",
)


def build_gui_type_report(gt_type_counts: Counter, detected_type_counts: Counter | None = None) -> list[dict]:
    """Zbuduj per-typ raport GUI (Story 3-14c AC4).

    Czysta funkcja (testowalna jednostkowo): ``gt_type_counts`` liczniki GT,
    ``detected_type_counts`` liczniki detekcji (``None`` bez imagingu →
    ``detected_count``/``ratio`` = ``None``, ale wszystkie 11 typów obecne).
    """
    report = []
    for key in GUI_TYPE_KEYS:
        gt = int(gt_type_counts.get(key, 0))
        det = int(detected_type_counts.get(key, 0)) if detected_type_counts is not None else None
        report.append(
            {
                "component_type": key,
                "gt_count": gt,
                "detected_count": det,
                "ratio": round(det / gt, 3) if det is not None and gt else None,
            }
        )
    return report


def _missing_ratio(expected: int, actual: int) -> float:
    if expected <= 0:
        return 0.0
    return max(0, expected - actual) / expected


def _visual_accuracy(model, expected_names: set[str], expected_rels: int) -> float:
    detected = {e["name"] for e in model.elements}
    name_recall = len(detected & expected_names) / len(expected_names) if expected_names else 1.0
    rel_recall = min(len(model.relationships), expected_rels) / expected_rels if expected_rels else 1.0
    return round((name_recall + rel_recall) / 2, 3)


def main() -> int:
    out_dir = _BACKEND / "test-results"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "golden-accuracy.json"

    orch = UMLParserOrchestrator()
    visual = VisualUMLParser()

    text_rows: list[dict] = []
    text_bad: list[str] = []
    for s in discover_uml_samples():
        fmt = orch.detect_format(s.content)
        model = orch._parse_content(s.content, fmt)
        actual = {k: len(getattr(model, k)) for k in _COUNT_KEYS}
        worst = 0.0
        for key, count in actual.items():
            worst = max(worst, _missing_ratio(s.expected[f"expected_{key}_count"], count))
        if worst > TOLERANCE:
            text_bad.append(s.id)
        text_rows.append(
            {
                "id": s.id,
                "format": fmt.value,
                "diagram_type": s.diagram_type,
                "counts": actual,
                "max_missing_ratio": round(worst, 3),
            }
        )

    visual_rows: list[dict] = []
    visual_bad: list[str] = []
    for s in discover_uml_visual_samples():
        model = visual.parse_svg(s.svg_content)
        names = set(s.expected.get("expected_element_names", []))
        rels = s.expected["expected_relationships_count"]
        acc = _visual_accuracy(model, names, rels)
        if acc < VISUAL_THRESHOLD:
            visual_bad.append(s.id)
        visual_rows.append(
            {"id": s.id, "diagram_type": s.diagram_type, "accuracy": acc, "confidence": model.confidence}
        )

    by_type = Counter(r["diagram_type"] for r in text_rows)

    # ── GUI per-typ raport (Story 3-14c, AC4) ──────────────────────────────
    gui_gt_counts: Counter = Counter()
    gui_detected_counts: Counter | None = None
    gui_orch = None
    try:
        import cv2  # noqa: F401

        from app.services.analysis.gui.orchestrator import GUIAnalyzerOrchestrator

        gui_orch = GUIAnalyzerOrchestrator()
        gui_detected_counts = Counter()
    except ImportError:
        pass
    for s in discover_gui_samples():
        for comp in s.expected_components:
            ctype = comp["component_type"]
            if ctype != "unknown":
                gui_gt_counts[ctype] += 1
        if gui_orch is not None and s.png_path is not None:
            detected = gui_orch.analyze(s.png_path.read_bytes()).components
            for comp in detected:
                if comp.component_type.value != "unknown":
                    gui_detected_counts[comp.component_type.value] += 1
    gui_types = build_gui_type_report(gui_gt_counts, gui_detected_counts)

    artefact = {
        "story": "3.14-domkniecie",
        "tolerance": TOLERANCE,
        "visual_threshold": VISUAL_THRESHOLD,
        "summary": {
            "text_samples": len(text_rows),
            "visual_samples": len(visual_rows),
            "text_by_type": dict(by_type),
            "gui_types_with_gt": sum(1 for r in gui_types if r["gt_count"] > 0),
        },
        "text": text_rows,
        "visual": visual_rows,
        "gui_types": gui_types,
        "gate": {
            "text_failures": text_bad,
            "visual_failures": visual_bad,
            "passed": not text_bad and not visual_bad,
        },
    }
    out.write_text(json.dumps(artefact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    rel = out.relative_to(_BACKEND)
    print(f"golden-accuracy.json -> {rel}")
    print(f"  text={len(text_rows)} visual={len(visual_rows)} by_type={dict(by_type)}")
    print("  gui_types: " + ", ".join(f"{r['component_type']}={r['gt_count']}" for r in gui_types))
    if text_bad or visual_bad:
        print(f"  GATE FAILED: text={text_bad} visual={visual_bad}", file=sys.stderr)
        return 1
    print("  GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
