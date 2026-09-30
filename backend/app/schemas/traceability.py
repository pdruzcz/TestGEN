"""Pydantic schemas for the traceability matrix — Epic 3, Story 3.15."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TraceabilityEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: str
    source_element_id: uuid.UUID
    source_element_type: str
    source_element_name: str
    source: str | None = Field(
        default=None,
        description="Provenance: 'parser' (structural XMI/PlantUML) or 'ocr' (visual/OCR path). "
        "NULL for GUI components.",
    )
    confidence: float | None = Field(
        default=None,
        description="OCR confidence (0.0-1.0) when source='ocr'; NULL for structural parses and GUI.",
    )
    source_diagram_id: uuid.UUID | None = None
    source_screenshot_id: uuid.UUID | None = None
    linked_flow_id: uuid.UUID | None = None
    linked_gherkin_id: uuid.UUID | None = None
    test_case_id: uuid.UUID | None = Field(
        default=None,
        description="Always NULL on this pipeline: TestCase binds to analysis_results, not to "
        "UML/GUI source elements. The test artefact is linked_gherkin_id.",
    )
    code_reference: str | None = Field(
        default=None,
        description="Name of the linked APPROVED Gherkin feature — a BDD scenario name, NOT a "
        "path to generated/compiled test code.",
    )
    code_framework: str | None = Field(
        default=None,
        description="'gherkin/bdd' when an APPROVED Gherkin scenario is linked. This labels the "
        "scenario format; it does not imply executable test code was generated.",
    )
    coverage_status: str = Field(
        description="covered | partial | uncovered. 'covered' = an APPROVED Gherkin scenario is "
        "linked (proxy for an accepted test, not generated test code).",
    )
    created_at: datetime | None = None


class CoverageBreakdown(BaseModel):
    """Coverage counts for one diagram type or GUI category."""

    key: str
    total: int
    covered: int
    partial: int
    uncovered: int


class TraceabilitySummaryOut(BaseModel):
    uml_total: int = 0
    gui_total: int = 0
    uml_coverage_pct: float = 0.0
    gui_coverage_pct: float = 0.0
    code_coverage_pct: float = Field(
        default=0.0,
        description="Share of source elements with an APPROVED Gherkin scenario linked — a proxy "
        "for 'accepted test', not for generated/compiled test code.",
    )
    breakdown_per_uml_type: list[CoverageBreakdown] = Field(default_factory=list)
    breakdown_per_gui_category: list[CoverageBreakdown] = Field(default_factory=list)


class TraceabilityMatrixOut(BaseModel):
    elements: list[TraceabilityEntryOut]
    summary: TraceabilitySummaryOut
    total: int
    page: int
    page_size: int


class TraceabilityBuildResponse(BaseModel):
    task_id: str | None = None
    status: str = "pending"


class TraceabilityExportQuery(BaseModel):
    format: Literal["csv", "xlsx", "json", "pdf"] = "csv"
