"""Task status schemas — polling analysis task progress (Story 1.10, 6.3)."""

from pydantic import BaseModel, Field

from app.core.config import EngineMode
from app.models.test_case import TestFramework

__all__ = [
    "AnalysisAcceptedResponse",
    "AnalysisRequest",
    "CancelTaskResponse",
    "EngineMode",
    "TaskStatusResponse",
]


class AnalysisRequest(BaseModel):
    # Przykład trafia do dokumentacji i do generowanych snippetów (Story 8.5).
    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "example": {
                "modules": ["code_analysis", "security_scan"],
                "engine_mode": "native",
                "test_framework": "pytest",
            }
        },
    }

    modules: list[str] = Field(default_factory=lambda: ["code_analysis"])
    engine_mode: EngineMode | None = Field(
        default=None,
        description="Tryb silnika: native, llm, hybrid. Gdy None — użyj konfiguracji serwera.",
    )
    test_framework: TestFramework | None = Field(
        default=None,
        description=(
            "Framework testowy: pytest, junit, nunit, mocha, cypress, sikulix, "
            "selenium, playwright, appium, phpunit, pest."
        ),
    )
    llm_model: str | None = Field(default=None, description="Model LLM (dla trybów llm/hybrid).")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=200_000)


class AnalysisAcceptedResponse(BaseModel):
    task_id: str
    status: str = "pending"
    status_url: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    current_step: str = ""
    result_url: str | None = None
    error: str | None = None


class CancelTaskResponse(BaseModel):
    task_id: str
    status: str = "cancelled"
