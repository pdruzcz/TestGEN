"""Pydantic schemas for the UML module (Epic 3)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.uml_diagram import DiagramType, UMLDiagramStatus, UMLFormat, UMLModelSource

# Re-export enums for API consumers.
UMLFormatEnum = UMLFormat
DiagramTypeEnum = DiagramType
AnalysisStatusEnum = UMLDiagramStatus


class UMLDiagramResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    format: UMLFormat
    diagram_type: DiagramType | None = None
    status: UMLDiagramStatus
    file_size: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UMLDiagramListResponse(BaseModel):
    diagrams: list[UMLDiagramResponse]
    total: int


class UMLUploadItem(BaseModel):
    diagram_id: uuid.UUID | None = None
    filename: str
    format: UMLFormat | None = None
    status: str  # "accepted" | "rejected"
    task_id: str | None = None
    rejection_reason: str | None = None


class UMLUploadResponse(BaseModel):
    project_id: uuid.UUID
    accepted: list[UMLUploadItem]
    rejected: list[UMLUploadItem]
    total_accepted: int
    total_rejected: int


class UMLParseResponse(BaseModel):
    diagram_id: uuid.UUID
    diagram_type: DiagramType | None = None
    participants: list | None = None
    elements: list | None = None
    relationships: list | None = None
    fragments: list | None = None
    flows: list | None = None
    source: UMLModelSource | None = None
    confidence: float | None = None


class UMLDiagramDetailResponse(BaseModel):
    diagram: UMLDiagramResponse
    parsed_model: UMLParseResponse | None = None


class UMLParseRequest(BaseModel):
    diagram_id: uuid.UUID


class UMLParseTaskResponse(BaseModel):
    diagram_id: uuid.UUID
    task_id: str | None = None
    status: str


class SequenceModelResponse(BaseModel):
    diagram_id: uuid.UUID
    participants: list | None = None
    messages: list | None = None
    fragments: list | None = None
    test_paths: list | None = None


class ClassModelResponse(BaseModel):
    diagram_id: uuid.UUID
    classes: list | None = None
    interfaces: list | None = None
    enumerations: list | None = None
    relationships: list | None = None
    packages: list | None = None


class DiagramCodeComparisonResponse(BaseModel):
    diagram_id: uuid.UUID
    matching_classes: list
    diagram_only_classes: list[str]
    code_only_classes: list[str]
    discrepancies: list
