"""TestCase Pydantic schemas - Story 1.31

Extended schemas for test case CRUD and execution tracking.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.test_case import (
    GenerationEngine,
    TestCaseStatus,
    TestPriority,
    TestType,
)


class TestCaseCreate(BaseModel):
    analysis_result_id: uuid.UUID
    source_file_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: TestPriority = TestPriority.MEDIUM
    type: TestType = TestType.UNIT
    framework: str | None = None
    language: str | None = None
    generation_engine: GenerationEngine = GenerationEngine.NATIVE
    source_function: str | None = None
    source_class: str | None = None
    source_endpoint: str | None = None
    test_code: str | None = None
    imports: str | None = None
    setup_code: str | None = None
    teardown_code: str | None = None
    preconditions: dict[str, Any] | None = None
    steps: dict[str, Any] | None = None
    expected_result: str | None = None
    test_data: dict[str, Any] | None = None
    scenario_description: str | None = None
    scenario_rationale: str | None = None
    edge_case_description: str | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be blank")
        return stripped


class TestCaseUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    priority: TestPriority | None = None
    type: TestType | None = None
    framework: str | None = None
    test_code: str | None = None
    imports: str | None = None
    setup_code: str | None = None
    teardown_code: str | None = None
    preconditions: dict[str, Any] | None = None
    steps: dict[str, Any] | None = None
    expected_result: str | None = None
    test_data: dict[str, Any] | None = None
    status: TestCaseStatus | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class TestCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    analysis_result_id: uuid.UUID
    source_file_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    priority: str
    type: str
    framework: str | None = None
    language: str | None = None
    generation_engine: str
    source_function: str | None = None
    source_class: str | None = None
    source_endpoint: str | None = None
    test_code: str | None = None
    imports: str | None = None
    setup_code: str | None = None
    teardown_code: str | None = None
    preconditions: dict[str, Any] | None = None
    steps: dict[str, Any] | None = None
    expected_result: str | None = None
    test_data: dict[str, Any] | None = None
    scenario_description: str | None = None
    scenario_rationale: str | None = None
    edge_case_description: str | None = None
    confidence_score: float | None = None
    status: str
    # Powiązanie z TMS (Story 8.11) — puste, gdy przypadek nie był synchronizowany.
    tms_external_id: str | None = None
    tms_synced_at: datetime | None = None
    last_executed_at: datetime | None = None
    last_execution_result: dict[str, Any] | None = None
    execution_count: int
    pass_count: int
    fail_count: int
    is_edited: bool = False
    reviewed_at: datetime | None = None
    reviewed_by: uuid.UUID | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = Field(None, validation_alias="meta")
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StatusCounts(BaseModel):
    """Aggregate counts per test-case status."""

    ready: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    draft: int = 0
    disabled: int = 0


class TestCaseListResponse(BaseModel):
    test_cases: list[TestCaseResponse]
    total: int
    status_counts: StatusCounts = Field(default_factory=StatusCounts)


class TestCaseBulkUpdateRequest(BaseModel):
    """Zbiorcza zmiana statusu/priorytetu (Story 6.5, AC5)."""

    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    status: TestCaseStatus | None = None
    priority: TestPriority | None = None


class TestCaseBulkDeleteRequest(BaseModel):
    """Zbiorcze usuwanie test case'ów (Story 6.5, AC5)."""

    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class BulkActionResponse(BaseModel):
    affected: int


class TestCaseHistoryEntry(BaseModel):
    """Pojedyncza zmiana pola test case'a (Story 6.5, AC7)."""

    changed_at: datetime
    author: str | None = None
    action: str
    field: str
    old_value: str | None = None
    new_value: str | None = None


class TestCaseHistoryResponse(BaseModel):
    entries: list[TestCaseHistoryEntry]
    total: int


class TestCaseExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_case_id: uuid.UUID
    executed_at: datetime
    execution_duration_ms: int | None = None
    status: str
    error_message: str | None = None
    error_stack_trace: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    lines_covered: int | None = None
    branches_covered: int | None = None
    coverage_percentage: float | None = None
    executed_by: str | None = None
    environment: str | None = None
    runner_version: str | None = None
    metadata: dict[str, Any] | None = Field(None, validation_alias="meta")
    created_at: datetime | None = None
