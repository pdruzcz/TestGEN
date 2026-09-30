"""Pydantic schemas for preprocessing endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

ALLOWED_LANGUAGES = frozenset(
    {
        "python",
        "java",
        "javascript",
        "typescript",
        "csharp",
        "cpp",
        "go",
        "ruby",
        "php",
        "swift",
        "kotlin",
    }
)


class LanguageCount(BaseModel):
    language: str
    count: int = Field(ge=0)
    loc: int = Field(ge=0)


class UnknownFileResponse(BaseModel):
    filename: str
    file_id: uuid.UUID

    model_config = {"from_attributes": True}


class PreprocessingReportResponse(BaseModel):
    project_id: uuid.UUID
    languages: list[LanguageCount]
    detected_frameworks: list[str]
    total_loc: int = Field(ge=0)
    unknown_files: list[UnknownFileResponse]
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SourceFileUpdate(BaseModel):
    detected_language: str | None = Field(None, max_length=50)
    detected_framework: str | None = Field(None, max_length=100)

    @field_validator("detected_language")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if v not in ALLOWED_LANGUAGES:
                raise ValueError(f"Unsupported language: {v}. Allowed: {sorted(ALLOWED_LANGUAGES)}")
        return v

    @field_validator("detected_framework")
    @classmethod
    def validate_framework(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Framework cannot be blank")
        return v
