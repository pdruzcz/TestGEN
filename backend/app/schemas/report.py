"""Report Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.report import ReportFormat


class ReportCreate(BaseModel):
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=500)
    format: ReportFormat = ReportFormat.JSON
    content: dict[str, Any] | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be blank")
        return stripped


class ReportUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    content: dict[str, Any] | None = None
    file_url: str | None = Field(None, max_length=1000)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    title: str
    format: str
    content: dict[str, Any] | None = None
    file_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
