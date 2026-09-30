"""Pydantic schemas for self-healing of UI test locators — Epic 1, Story 1.51."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealRequest(BaseModel):
    """Body of ``POST /projects/{project_id}/tests/heal``."""

    model_config = ConfigDict(extra="ignore")

    version_a: str = Field(..., min_length=1, max_length=255)
    version_b: str = Field(..., min_length=1, max_length=255)

    @model_validator(mode="after")
    def _versions_must_differ(self) -> "HealRequest":
        if self.version_a == self.version_b:
            raise ValueError("version_a and version_b must differ")
        return self


class HealTriggerResponse(BaseModel):
    """202 Accepted response — async healing task launched."""

    model_config = ConfigDict(extra="ignore")

    task_id: str
    report_id: uuid.UUID
    status: str = "pending"


class HealingItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    test_code_id: uuid.UUID
    old_locator: str
    old_strategy: str
    new_locator: str | None = None
    new_strategy: str | None = None
    confidence: float
    healing_method: str
    status: str
    diff_preview: str | None = None
    created_at: datetime


class HealingReportStats(BaseModel):
    """Aggregate metrics for one healing run (mirrors ``HealingReport.stats``)."""

    model_config = ConfigDict(extra="ignore")

    total: int = 0
    healthy: int = 0  # locators whose target still exists (not modified)
    healed: int = 0  # repaired with confidence >= threshold
    needs_review: int = 0  # confidence < threshold
    failed: int = 0  # no candidate found
    rejected: int = 0  # user-rejected
    avg_confidence: float = 0.0
    duration_s: float = 0.0


class HealingReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    version_a: str
    version_b: str
    status: str
    stats: dict | None = None
    created_at: datetime
    items: list[HealingItemResponse] = Field(default_factory=list)


class HealingDecisionRequest(BaseModel):
    """Body of ``POST .../items/{item_id}/decision``."""

    model_config = ConfigDict(extra="ignore")

    action: Literal["accept", "reject"]


class HealingDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_id: uuid.UUID
    status: str
    applied: bool  # True only for an accepted heal applied to TestCode
