#!/usr/bin/env python
"""Generate synthetic GUI screenshot PNGs from the golden ground truth.

Story 3.14 closure, AC3: the golden GUI dataset carried only frozen component
inventories (JSON) — no images — because the imaging stack (cv2/numpy) is
optional. This script renders a faithful synthetic screenshot for every golden
sample by drawing each ground-truth component as a labelled rectangle at its
frozen bbox, and baseline/comparison PNGs for every visual-regression pair.

The PNGs are deliberately schematic (boxes + labels) rather than photorealistic
mocks: they carry exactly the component geometry the analysers are expected to
recover, so an image-gated test can measure detection accuracy against the same
ground truth the JSON path already asserts. Re-runnable (idempotent).

Run from the backend dir:   python scripts/generate_gui_png.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from PIL import Image, ImageDraw  # noqa: E402

GOLDEN = _BACKEND / "tests" / "golden_data"
_PADDING = 24


def _canvas_size(components: list[dict]) -> tuple[int, int]:
    if not components:
        return (320, 240)
    w = max(c["bbox"]["x"] + c["bbox"]["width"] for c in components) + _PADDING
    h = max(c["bbox"]["y"] + c["bbox"]["height"] for c in components) + _PADDING
    return (w, h)


def _render(components: list[dict]) -> Image.Image:
    w, h = _canvas_size(components)
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    for comp in components:
        b = comp["bbox"]
        x1, y1 = b["x"], b["y"]
        x2, y2 = b["x"] + b["width"], b["y"] + b["height"]
        draw.rectangle([x1, y1, x2, y2], outline="black", width=2)
        label = comp.get("label") or comp.get("component_type", "")
        if label:
            draw.text((x1 + 5, y1 + 4), str(label)[:40], fill="black")
    return img


def _render_gui_screens() -> int:
    count = 0
    for gt in sorted((GOLDEN / "gui").rglob("*_ground_truth.json")):
        data = json.loads(gt.read_text(encoding="utf-8"))
        # Story 3-14b: kategoria ``real`` to zrzuty realnych UI commitowane
        # wprost (scripts/capture_real_ui.js) — generator syntetycznych PNG
        # nie może ich nadpisywać.
        if gt.parent.name == "real" or data.get("category") == "real":
            continue
        components = data.get("expected_components", [])
        if not components:
            continue
        name = gt.stem.removesuffix("_ground_truth")
        out = gt.with_name(f"{name}.png")
        _render(components).save(out)
        count += 1
    return count


def _render_visual_pairs() -> int:
    count = 0
    for gt in sorted((GOLDEN / "visual_regression").rglob("*_ground_truth.json")):
        data = json.loads(gt.read_text(encoding="utf-8"))
        name = gt.stem.removesuffix("_ground_truth")
        for suffix, key in (("baseline", "baseline_components"), ("comparison", "comparison_components")):
            components = data.get(key, [])
            if not components:
                continue
            out = gt.with_name(f"{name}_{suffix}.png")
            _render(components).save(out)
            count += 1
    return count


def main() -> int:
    try:
        gui = _render_gui_screens()
    except ImportError:
        print("Pillow (PIL) is required: pip install pillow", file=sys.stderr)
        return 1
    pairs = _render_visual_pairs()
    print(f"rendered GUI PNGs: {gui}, visual-regression PNGs: {pairs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
