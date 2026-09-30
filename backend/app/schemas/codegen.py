"""Pydantic schemas for test code generation — Epic 3, Story 3.12."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CodeGenRequest(BaseModel):
    """Request to generate test code from selected test cases."""

    test_case_ids: list[uuid.UUID] = Field(default_factory=list)
    framework: Literal[
        "cypress",
        "sikulix",
        "database",
        "phpunit",
        "pest",
        "selenium",
        "playwright",
        "appium",
        "unittest",
        "testng",
        "mstest",
    ] = "cypress"
    base_url: str | None = None
    # Story 1.56: platforma urzadzenia dla Appium (desired capabilities);
    # None → domyslne capabilities Android (UiAutomator2).
    platform: Literal["android", "ios"] | None = None


class CodeGenResponse(BaseModel):
    """Async dispatch response for a code generation task."""

    task_id: str
    status: str


class GeneratedTestCodeOut(BaseModel):
    """Serialized generated test code record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_case_id: uuid.UUID
    framework: str
    language: str
    code: str
    file_path: str | None = None
    # Story 3-13-domknięcie: patterny SikuliX wycięte bbox→PNG (tylko sikulix).
    pattern_images: list[dict[str, Any]] | None = None
    created_at: datetime | None = None


class GeneratedTestCodeListResponse(BaseModel):
    """Paginated list of generated test code records."""

    items: list[GeneratedTestCodeOut]
    total: int
