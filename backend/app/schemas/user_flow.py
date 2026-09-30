"""Pydantic schemas for reconstructed user flows (Epic 3, Story 3.7)."""

import uuid
from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field

from app.models.user_flow import FlowSourceType, FlowStatus


class FlowStepOut(BaseModel):
    id: uuid.UUID | None = None
    sequence: int
    action: str
    actor: str | None = None
    target_element: str | None = None
    expected_result: str | None = None
    source_diagram_id: uuid.UUID | None = None
    source_screenshot_id: uuid.UUID | None = None
    source: str = "native"
    # UML relation / decision metadata (Story 3-11-domknięcie, AC1). Maps from
    # the ORM ``FlowStep.meta`` column; ``relation_type`` / ``parameters`` /
    # ``branch_label`` drive the Gherkin Background / Outline / Scenario mapping.
    # ``AliasChoices`` jest wymagane: atrybut ``metadata`` na ORM FlowStep to
    # rezerwowany ``sqlalchemy.MetaData`` (deklaratywna baza), a nie nasza
    # kolumna — walidacja from_attributes musiałaby czytać ``meta``.
    metadata: dict | None = Field(default=None, validation_alias=AliasChoices("meta", "metadata"))

    model_config = {"from_attributes": True}


class UserFlowOut(BaseModel):
    id: uuid.UUID | None = None
    name: str
    source_type: FlowSourceType
    source_ids: list[str] | None = None
    steps: list[FlowStepOut] = []
    status: FlowStatus
    warnings: list[str] | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserFlowListResponse(BaseModel):
    flows: list[UserFlowOut]
    total: int


class CrossAnalysisRequest(BaseModel):
    diagram_ids: list[uuid.UUID] | None = None


class CrossAnalysisTaskResponse(BaseModel):
    task_id: str | None = None
    status: str = "pending"


class CrossAnalysisResponse(BaseModel):
    user_flows: list[UserFlowOut]
    coverage_warnings: list[str] = []
