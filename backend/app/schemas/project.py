"""Project-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    language_hint: str | None = Field(None, max_length=50)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Project name cannot be blank")
        return stripped

    @field_validator("description")
    @classmethod
    def description_strip(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped or None
        return v

    @field_validator("language_hint")
    @classmethod
    def language_hint_strip(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            return stripped or None
        return v


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    language_hint: str | None = Field(None, max_length=50)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Project name cannot be blank")
            return stripped
        return v


class ProjectResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    language_hint: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int
