"""Pydantic schemas for GUI screenshot upload + analysis — Epic 3, Story 3.8."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.gui_screenshot import GUIAnalysisStatus, GUIComponentType


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class OCRTextBlock(BaseModel):
    text: str
    bbox: BoundingBox
    confidence: float = 0.0


class GUIComponentOut(BaseModel):
    id: uuid.UUID | None = None
    component_type: GUIComponentType
    label: str | None = None
    bbox: BoundingBox | None = None
    confidence: float = 0.0
    attributes: dict | None = None

    model_config = {"from_attributes": True}


class LayoutNode(BaseModel):
    type: str
    label: str | None = None
    bbox: BoundingBox | None = None
    children: list["LayoutNode"] = []


class GUIScreenshotOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: GUIAnalysisStatus
    screen_sequence: int = 0
    file_size: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class GUIScreenshotListResponse(BaseModel):
    screenshots: list[GUIScreenshotOut]
    total: int


class GUIUploadItem(BaseModel):
    screenshot_id: uuid.UUID | None = None
    filename: str
    status: str  # "accepted" | "rejected"
    task_id: str | None = None
    rejection_reason: str | None = None


class GUIUploadResponse(BaseModel):
    project_id: uuid.UUID
    accepted: list[GUIUploadItem]
    rejected: list[GUIUploadItem]
    total_accepted: int
    total_rejected: int


class GUIAnalyzeRequest(BaseModel):
    screenshot_id: uuid.UUID


class GUIAnalyzeTaskResponse(BaseModel):
    screenshot_id: uuid.UUID | None = None
    task_id: str | None = None
    status: str = "pending"


class GUIAnalysisResponse(BaseModel):
    screenshot_id: uuid.UUID
    status: GUIAnalysisStatus
    ocr_text_blocks: list[OCRTextBlock] = []
    components: list[GUIComponentOut] = []
    layout_tree: LayoutNode | None = None
    warnings: list[str] = []
    processing_time_ms: int = 0


class GUIFlowReconstructionRequest(BaseModel):
    screenshot_ids: list[uuid.UUID] | None = None
    name: str | None = None


class GUIFlowReconstructionTaskResponse(BaseModel):
    task_id: str | None = None
    status: str = "pending"


class VisualRegressionRequest(BaseModel):
    baseline_screenshot_id: uuid.UUID
    comparison_screenshot_id: uuid.UUID
    pixel_threshold: float = 0.02
    generate_test_code: bool = False
    test_framework: str = "playwright"  # playwright | cypress


class ComponentDeltaOut(BaseModel):
    component_type: str
    change_type: str
    severity: str
    description: str
    baseline_bbox: dict | None = None
    comparison_bbox: dict | None = None
    confidence: float = 0.0


class VisualRegressionResponse(BaseModel):
    id: uuid.UUID | None = None
    baseline_screenshot_id: uuid.UUID
    comparison_screenshot_id: uuid.UUID
    pixel_diff_percentage: float
    status: str
    semantic_diff: list[ComponentDeltaOut] = []
    diff_image_url: str | None = None
    test_code: str | None = None
    warnings: list[str] = []
    created_at: datetime | None = None


class VisualRegressionListItem(BaseModel):
    id: uuid.UUID
    baseline_screenshot_id: uuid.UUID
    comparison_screenshot_id: uuid.UUID
    pixel_diff_percentage: float
    status: str
    created_at: datetime | None = None


class VisualRegressionListResponse(BaseModel):
    items: list[VisualRegressionListItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


# ── Story 1.51-zakańczenie: HTML/DOM GUI source + analysis history ────────────


class DOMUploadItem(BaseModel):
    dom_source_id: uuid.UUID | None = None
    filename: str
    status: str  # "accepted" | "rejected"
    task_id: str | None = None
    rejection_reason: str | None = None


class DOMUploadResponse(BaseModel):
    project_id: uuid.UUID
    accepted: list[DOMUploadItem] = []
    rejected: list[DOMUploadItem] = []
    a11y_accepted: bool = False
    total_accepted: int = 0
    total_rejected: int = 0


class GUIAnalysisSummary(BaseModel):
    """One row of the GUI analysis history (screenshot or DOM) — Story 1.51 Part B1."""

    id: uuid.UUID
    source_type: str  # "screenshot" | "dom"
    created_at: datetime | None = None
    version_label: str | None = None
    source_label: str | None = None  # screenshot filename / DOM html filename
    screen_sequence: int | None = None
    component_count: int = 0


class GUIAnalysisListResponse(BaseModel):
    analyses: list[GUIAnalysisSummary] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


LayoutNode.model_rebuild()
