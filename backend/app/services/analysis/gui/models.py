"""Internal dataclasses for the GUI analysis pipeline — Story 3.8.

These are framework-agnostic value objects passed between the OCR, component
detection and layout stages. They are intentionally decoupled from the heavy
``cv2`` / ``pytesseract`` dependencies so the pure logic stays unit-testable.
"""

from dataclasses import dataclass, field

from app.models.gui_screenshot import GUIComponentType


@dataclass
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    def contains(self, other: "BBox") -> bool:
        return (
            self.x <= other.x
            and self.y <= other.y
            and self.x2 >= other.x2
            and self.y2 >= other.y2
        )

    def iou(self, other: "BBox") -> float:
        ix1, iy1 = max(self.x, other.x), max(self.y, other.y)
        ix2, iy2 = min(self.x2, other.x2), min(self.y2, other.y2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        union = self.area + other.area - inter
        return inter / union if union else 0.0


@dataclass
class TextBlock:
    text: str
    bbox: BBox
    confidence: float = 0.0


@dataclass
class DetectedComponent:
    component_type: GUIComponentType
    bbox: BBox
    confidence: float
    label: str | None = None
    attributes: dict = field(default_factory=dict)


@dataclass
class LayoutTreeNode:
    type: str
    label: str | None = None
    bbox: BBox | None = None
    children: list["LayoutTreeNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "label": self.label,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class GUIAnalysisOutput:
    text_blocks: list[TextBlock] = field(default_factory=list)
    components: list[DetectedComponent] = field(default_factory=list)
    layout_tree: LayoutTreeNode | None = None
    warnings: list[str] = field(default_factory=list)
    processing_time_ms: int = 0
