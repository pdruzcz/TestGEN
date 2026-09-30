"""Tenant-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.slugify import is_valid_slug
from app.models.tenant import PlanType


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100)
    nip: str | None = Field(None, max_length=20)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be blank")
        return stripped

    @field_validator("slug")
    @classmethod
    def slug_valid_format(cls, v: str) -> str:
        if not is_valid_slug(v):
            raise ValueError("Slug must contain only lowercase letters, digits, and hyphens (e.g., my-company)")
        return v


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    nip: str | None = Field(None, max_length=20)
    plan: PlanType | None = None
    settings: dict | None = None


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    nip: str | None = None
    plan: str
    is_active: bool
    settings: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
