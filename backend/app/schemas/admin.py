"""Schematy panelu administracyjnego — Epic 6, Story 6.15."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TenantSummaryResponse(BaseModel):
    """Tenant z metrykami użycia (AC4)."""

    id: uuid.UUID
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime | None = None
    user_count: int = 0
    storage_bytes: int = 0
    project_count: int = 0


class TenantListResponse(BaseModel):
    tenants: list[TenantSummaryResponse]
    total: int


class TenantProjectResponse(BaseModel):
    """Projekt tenanta w widoku cross-tenant (AC5)."""

    id: uuid.UUID
    name: str
    status: str
    created_at: datetime | None = None


class TenantProjectListResponse(BaseModel):
    projects: list[TenantProjectResponse]
    total: int


class AuditLogEntryResponse(BaseModel):
    """Pojedynczy wpis logu audytu (AC6)."""

    id: uuid.UUID
    created_at: datetime
    tenant_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: uuid.UUID
    details: dict | None = None
    ip_address: str | None = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogEntryResponse]
    total: int


class LimitsConfig(BaseModel):
    """Limity domyślne platformy (AC7)."""

    max_file_size_mb: int = Field(100, ge=1, le=5000)
    max_projects_per_tenant: int = Field(50, ge=1, le=10000)
    max_users_per_tenant: int = Field(25, ge=1, le=10000)
    llm_cost_limit_usd: float = Field(100.0, ge=0, le=1_000_000)


class LlmConfig(BaseModel):
    """Ustawienia dostawcy LLM (AC7)."""

    provider: Literal["openai", "anthropic"] = "anthropic"
    model: str = Field("claude-sonnet-4-20250514", min_length=1, max_length=200)
    temperature: float = Field(0.2, ge=0, le=2)
    max_tokens: int = Field(4096, ge=256, le=200000)
    timeout_seconds: int = Field(60, ge=5, le=600)


class MaintenanceConfig(BaseModel):
    """Tryb serwisowy (AC7)."""

    enabled: bool = False
    message: str = Field("", max_length=500)


DEFAULT_FEATURE_FLAGS: dict[str, bool] = {
    "ai_assistant": True,
    "self_healing": True,
    "visual_regression": True,
    "security_scan": True,
}


class PlatformConfigResponse(BaseModel):
    limits: LimitsConfig
    llm: LlmConfig
    maintenance: MaintenanceConfig
    feature_flags: dict[str, bool]


class UpdatePlatformConfigRequest(BaseModel):
    """Aktualizacja częściowa — podane pola są scalane z bieżącą konfiguracją."""

    limits: dict | None = None
    llm: dict | None = None
    maintenance: dict | None = None
    feature_flags: dict[str, bool] | None = None

    def sections(self) -> dict[str, dict]:
        return {name: value for name, value in self.model_dump(exclude_none=True).items()}
