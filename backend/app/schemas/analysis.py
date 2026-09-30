"""Analysis Pydantic schemas — DEMO-001 LLM file analysis + Story 1.9 domain models."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.exceptions import TestGENError


# --- DEMO-001 schemas (existing) ---

class AnalysisResponse(BaseModel):
    analysis: dict[str, Any]
    file_id: uuid.UUID
    project_id: uuid.UUID


class LLMError(TestGENError):
    status_code = 502
    error_type = "llm-error"
    title = "LLM Service Error"


# --- Story 1.9 domain schemas ---

class AnalysisResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    source_file_id: uuid.UUID | None = None
    engine_mode: str
    module: str
    status: str
    result_data: dict[str, Any] | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AnalysisResultCreate(BaseModel):
    project_id: uuid.UUID
    source_file_id: uuid.UUID | None = None
    engine_mode: str = "hybrid"
    module: str
