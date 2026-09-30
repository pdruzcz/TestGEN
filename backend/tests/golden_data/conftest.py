"""Golden-data loaders and fixtures — Epic 3, Story 3.14.

Auto-discovers the curated golden datasets that live next to this file:

- ``uml/<diagram_type>/*.puml`` paired with ``*_ground_truth.json`` —
  PlantUML diagrams with frozen expected element/relationship/flow counts.
- ``uml/visual/*.svg`` paired with ``*_ground_truth.json`` — Tier 2 visual
  UML (SVG) parsed via ``VisualUMLParser.parse_svg`` (Story 3.14 closure,
  AC2); the SVG vector path needs only ``defusedxml`` and is always on.
- ``gui/<category>/*_ground_truth.json`` — expected component inventories for
  representative GUI screens (PNG fixtures intentionally omitted; the imaging
  stack is optional, so these tests assert on the curated ground truth only).
- ``visual_regression/*_ground_truth.json`` — baseline/comparison component
  lists with the expected :class:`ComparisonStatus` and change types, exercised
  through the pure-Python semantic-diff path (no imaging deps required).

The fixtures are intentionally tolerant: if a directory is empty the suite
simply yields nothing, so adding a new sample file is enough to extend coverage
without touching the test code.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

GOLDEN_ROOT = Path(__file__).parent
UML_ROOT = GOLDEN_ROOT / "uml"
GUI_ROOT = GOLDEN_ROOT / "gui"
VISUAL_ROOT = GOLDEN_ROOT / "visual_regression"


@dataclass(frozen=True)
class GoldenUMLSample:
    """A PlantUML diagram paired with its frozen expected counts."""

    name: str
    diagram_type: str
    content: str
    expected: dict
    path: Path

    @property
    def id(self) -> str:
        return f"{self.diagram_type}/{self.name}"


@dataclass(frozen=True)
class GoldenVisualUMLSample:
    """A visual (SVG) UML diagram paired with its frozen expected counts.

    Tier 2 path (Story 3.1b): parsed via ``VisualUMLParser.parse_svg`` and the
    resulting model always carries ``source = ocr`` plus a confidence score.
    PDF/raster variants are image-gated (optional CV/OCR deps), so only the
    text/vector SVG path — which needs just ``defusedxml`` — is part of the
    always-on golden regression (Story 3.14 closure, AC2).
    """

    name: str
    diagram_type: str
    svg_content: str
    expected: dict
    path: Path

    @property
    def id(self) -> str:
        return f"visual/{self.name}"


@dataclass(frozen=True)
class GoldenGUISample:
    """Expected component inventory for a representative GUI screen."""

    name: str
    category: str
    expected_components: list[dict]
    description: str
    path: Path
    # Optional synthetic screenshot rendered from the inventory (Story 3.14
    # closure, AC3). Present when ``scripts/generate_gui_png.py`` has been run;
    # the image-gated accuracy test only activates when cv2/numpy are installed.
    png_path: Path | None = None

    @property
    def expected_count(self) -> int:
        return len(self.expected_components)

    @property
    def id(self) -> str:
        return f"{self.category}/{self.name}"


@dataclass(frozen=True)
class GoldenVisualPair:
    """A baseline/comparison component pair with its expected verdict."""

    name: str
    baseline_components: list[dict] = field(default_factory=list)
    comparison_components: list[dict] = field(default_factory=list)
    pixel_pct: float = 0.0
    expected_status: str = "match"
    expected_change_types: list[str] = field(default_factory=list)
    description: str = ""
    path: Path | None = None
    # Optional baseline/comparison screenshots (Story 3.14 closure, AC3) for the
    # image-gated pixel-diff path; the semantic-diff verdict is asserted without
    # them. Present when ``scripts/generate_gui_png.py`` has been run.
    baseline_png_path: Path | None = None
    comparison_png_path: Path | None = None


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_uml_samples() -> list[GoldenUMLSample]:
    samples: list[GoldenUMLSample] = []
    if not UML_ROOT.exists():
        return samples
    for path in sorted([*UML_ROOT.rglob("*.puml"), *UML_ROOT.rglob("*.xmi")]):
        ground_truth = path.with_name(f"{path.stem}_ground_truth.json")
        if not ground_truth.exists():
            continue
        expected = _load_json(ground_truth)
        samples.append(
            GoldenUMLSample(
                name=path.stem,
                diagram_type=expected.get("diagram_type", path.parent.name),
                content=path.read_text(encoding="utf-8"),
                expected=expected,
                path=path,
            )
        )
    return samples


def discover_uml_visual_samples() -> list[GoldenVisualUMLSample]:
    """SVG golden samples for the Tier 2 visual parser path (Story 3.1b).

    Routed through ``VisualUMLParser.parse_svg`` (``_parse_visual`` entry), not
    ``_parse_content``. Like the text path, the discovery is tolerant: an empty
    ``uml/visual/`` directory yields no samples.
    """
    samples: list[GoldenVisualUMLSample] = []
    visual_root = UML_ROOT / "visual"
    if not visual_root.exists():
        return samples
    for svg in sorted(visual_root.glob("*.svg")):
        ground_truth = svg.with_name(f"{svg.stem}_ground_truth.json")
        if not ground_truth.exists():
            continue
        expected = _load_json(ground_truth)
        samples.append(
            GoldenVisualUMLSample(
                name=svg.stem,
                diagram_type=expected.get("diagram_type", "class"),
                svg_content=svg.read_text(encoding="utf-8"),
                expected=expected,
                path=svg,
            )
        )
    return samples


def discover_gui_samples() -> list[GoldenGUISample]:
    samples: list[GoldenGUISample] = []
    if not GUI_ROOT.exists():
        return samples
    for gt in sorted(GUI_ROOT.rglob("*_ground_truth.json")):
        data = _load_json(gt)
        name = gt.stem.replace("_ground_truth", "")
        png = gt.with_name(f"{name}.png")
        samples.append(
            GoldenGUISample(
                name=name,
                category=data.get("category", gt.parent.name),
                expected_components=data.get("expected_components", []),
                description=data.get("description", ""),
                path=gt,
                png_path=png if png.exists() else None,
            )
        )
    return samples


def discover_visual_pairs() -> list[GoldenVisualPair]:
    pairs: list[GoldenVisualPair] = []
    if not VISUAL_ROOT.exists():
        return pairs
    for gt in sorted(VISUAL_ROOT.rglob("*_ground_truth.json")):
        data = _load_json(gt)
        name = gt.stem.replace("_ground_truth", "")
        base_png = gt.with_name(f"{name}_baseline.png")
        comp_png = gt.with_name(f"{name}_comparison.png")
        pairs.append(
            GoldenVisualPair(
                name=name,
                baseline_components=data.get("baseline_components", []),
                comparison_components=data.get("comparison_components", []),
                pixel_pct=float(data.get("pixel_pct", 0.0)),
                expected_status=data.get("expected_status", "match"),
                expected_change_types=data.get("expected_change_types", []),
                description=data.get("description", ""),
                path=gt,
                baseline_png_path=base_png if base_png.exists() else None,
                comparison_png_path=comp_png if comp_png.exists() else None,
            )
        )
    return pairs


@pytest.fixture(scope="session")
def golden_uml_diagrams() -> list[GoldenUMLSample]:
    return discover_uml_samples()


@pytest.fixture(scope="session")
def golden_uml_by_type() -> dict[str, list[GoldenUMLSample]]:
    grouped: dict[str, list[GoldenUMLSample]] = {}
    for sample in discover_uml_samples():
        grouped.setdefault(sample.diagram_type, []).append(sample)
    return grouped


@pytest.fixture(scope="session")
def golden_uml_visual_samples() -> list[GoldenVisualUMLSample]:
    return discover_uml_visual_samples()


@pytest.fixture(scope="session")
def golden_gui_screenshots() -> list[GoldenGUISample]:
    return discover_gui_samples()


@pytest.fixture(scope="session")
def golden_gui_by_category() -> dict[str, list[GoldenGUISample]]:
    grouped: dict[str, list[GoldenGUISample]] = {}
    for sample in discover_gui_samples():
        grouped.setdefault(sample.category, []).append(sample)
    return grouped


@pytest.fixture(scope="session")
def golden_visual_regression_pairs() -> list[GoldenVisualPair]:
    return discover_visual_pairs()


# ── Documentation-module golden data (Epic 2, Story 2.11) ────────────────────
#
# Loader i harness mieszkają w ``doc_samples.py`` (importowalnym z nazwy).
# Tutaj tylko sesyjna fixture dla zgodności z konwencją Epic 3.

from tests.golden_data.doc_samples import (  # noqa: E402
    GoldenDocSample,
    discover_doc_samples,
)


@pytest.fixture(scope="session")
def golden_doc_samples() -> list[GoldenDocSample]:
    return discover_doc_samples()
