"""AnalysisResult Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.analysis_result import AnalysisStatus, EngineMode


class AnalysisResultCreate(BaseModel):
    project_id: uuid.UUID
    engine_mode: EngineMode = EngineMode.HYBRID
    module: str = Field(min_length=1, max_length=100)


class AnalysisResultUpdate(BaseModel):
    status: AnalysisStatus | None = None
    result_data: dict[str, Any] | None = None
    duration_ms: int | None = None


class AnalysisResultResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    engine_mode: str
    module: str
    status: str
    result_data: dict[str, Any] | None = None
    duration_ms: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
