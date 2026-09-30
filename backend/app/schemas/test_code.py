"""TestCode Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TestCodeCreate(BaseModel):
    test_case_id: uuid.UUID
    framework: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1)
    file_path: str | None = Field(None, max_length=1000)


class TestCodeUpdate(BaseModel):
    code: str | None = Field(None, min_length=1)
    file_path: str | None = Field(None, max_length=1000)


class TestCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    test_case_id: uuid.UUID
    framework: str
    language: str
    code: str
    file_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
