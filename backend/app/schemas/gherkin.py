"""Pydantic schemas for Gherkin/BDD features — Epic 3, Story 3.11."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.gherkin_feature import GherkinStatus


class GherkinGenerateRequest(BaseModel):
    flow_ids: list[uuid.UUID]
    feature_name: str | None = None


class GherkinGenerateTaskResponse(BaseModel):
    task_id: str | None = None
    status: str = "pending"


class GherkinStepOut(BaseModel):
    keyword: str
    text: str


class GherkinScenarioOut(BaseModel):
    name: str
    tags: list[str] = []
    steps: list[GherkinStepOut] = []
    examples_headers: list[str] = []
    examples_rows: list[list[str]] = []


class GherkinFeatureOut(BaseModel):
    id: uuid.UUID
    feature_name: str
    feature_description: str | None = None
    source_flow_id: uuid.UUID | None = None
    scenarios: list[GherkinScenarioOut] = []
    raw_feature: str = ""
    engine_mode: str = "native"
    validation_warnings: list[str] = []
    status: GherkinStatus
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class GherkinFeatureListItem(BaseModel):
    id: uuid.UUID
    feature_name: str
    source_flow_id: uuid.UUID | None = None
    engine_mode: str = "native"
    status: GherkinStatus
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class GherkinFeatureListResponse(BaseModel):
    features: list[GherkinFeatureListItem]
    total: int
