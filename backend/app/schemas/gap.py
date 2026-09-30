"""Pydantic schemas for functional gap analysis — Epic 5, Story 5.1."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GapAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_ids: list[uuid.UUID] = Field(default_factory=list)
    engine_mode: Literal["native", "llm", "hybrid"] = "native"


class GapFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: str | None = None
    code_entity_id: str | None = None
    gap_type: str
    description: str
    requirement_text: str | None = None
    code_reference: str | None = None
    match_score: float
    match_method: str | None = None
    context: dict | None = None
    severity: str
    skeleton_code: str | None = None
    skeleton_language: str | None = None
    created_at: datetime


class GapFindingFilter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    gap_type: str | None = None
    min_score: float = 0.0
    severity: str | None = None
    match_method: str | None = None


class GapAnalysisSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_requirements: int = 0
    total_code_entities: int = 0
    missing_count: int = 0
    different_count: int = 0
    extra_count: int = 0
    inconsistent_count: int = 0
    avg_match_score: float = 0.0
    coverage_percentage: float = 0.0


class GapAnalysisTriggerResponse(BaseModel):
    task_id: str
    status: str = "pending"


class GapFindingsListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    findings: list[GapFindingResponse]
    total: int
    page: int
    size: int
    summary: GapAnalysisSummary


# ── Compliance schemas (Story 5.3) ────────────────────────────────────────────


class ComplianceScoreResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    score: float
    total_findings: int
    breakdown: dict[str, int] = Field(default_factory=dict)


class ModuleScoreResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_path: str
    score: float
    total_findings: int
    breakdown: dict[str, int] = Field(default_factory=dict)


class FunctionScoreResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code_entity_id: str
    score: float
    total_findings: int
    breakdown: dict[str, int] = Field(default_factory=dict)
    file_path: str | None = None
    entity_name: str | None = None


class ComplianceReportResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project_score: ComplianceScoreResponse
    module_scores: list[ModuleScoreResponse]
    function_scores: list[FunctionScoreResponse]


# ── Code error schemas (Story 5.4) ───────────────────────────────────────────


class CodeErrorScanRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    categories: list[Literal["syntax", "logic", "semantic", "conformance", "dead_code"]] = Field(
        default_factory=lambda: [
            "syntax",
            "logic",
            "semantic",
            "conformance",
            "dead_code",
        ],
    )


class CodeErrorScanResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str
    status: str = "pending"


class CodeErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source_file_id: uuid.UUID | None = None
    category: str
    message: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    severity: str
    rule_id: str | None = None
    suggestion: str | None = None
    context: dict | None = None
    status: str = "open"
    fingerprint: str | None = None
    created_at: datetime


class CodeErrorStatusUpdateRequest(BaseModel):
    """Triage update (AC4) — mirrors the security finding workflow."""

    model_config = ConfigDict(extra="ignore")

    status: Literal["open", "false_positive"]


class CodeErrorSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_errors: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)


class CodeErrorsListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    errors: list[CodeErrorResponse]
    total: int
    page: int
    size: int
    summary: CodeErrorSummary


# ── Recommendation schemas (Story 5.5) ───────────────────────────────────────


class RecommendationGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sources: list[Literal["gap_finding", "code_error"]] = Field(
        default_factory=lambda: ["gap_finding", "code_error"],
    )


class RecommendationGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str
    status: str = "pending"


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    gap_finding_id: uuid.UUID | None = None
    code_error_id: uuid.UUID | None = None
    title: str
    description: str
    priority: str
    confidence: float
    source_type: str
    source_ref: str | None = None
    suggestion: str | None = None
    context: dict | None = None
    created_at: datetime


class RecommendationSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total: int = 0
    by_priority: dict[str, int] = Field(default_factory=dict)
    avg_confidence: float = 0.0
    low_confidence_count: int = 0


class RecommendationsListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    recommendations: list[RecommendationResponse]
    total: int
    page: int
    size: int
    summary: RecommendationSummary


# ── Skeleton schemas (Story 5.6) ─────────────────────────────────────────────


class SkeletonGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: Literal["python", "typescript", "java", "csharp"] = "python"


class SkeletonResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    finding_id: uuid.UUID
    skeleton_code: str
    language: str
    function_name: str
    error: str | None = None


# ── Version comparison schemas (Story 5.7) ───────────────────────────────────


class ComplianceSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    analysis_id: uuid.UUID | None = None
    score: float
    total_findings: int
    missing_count: int
    different_count: int
    extra_count: int
    inconsistent_count: int
    avg_match_score: float
    coverage_percentage: float
    label: str | None = None
    notes: str | None = None
    created_at: datetime


class SnapshotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    notes: str | None = None


class FindingDiffResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str
    status: str
    gap_type: str
    v1_severity: str | None = None
    v2_severity: str | None = None
    v1_score: float | None = None
    v2_score: float | None = None
    requirement_text: str | None = None


class SnapshotDiffResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    v1_score: float
    v2_score: float
    score_delta: float
    direction: str
    v1_total: int
    v2_total: int
    total_delta: int
    missing_delta: int = 0
    different_delta: int = 0
    extra_delta: int = 0
    inconsistent_delta: int = 0
    coverage_delta: float = 0.0
    avg_match_score_delta: float = 0.0


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    v1_snapshot: ComplianceSnapshotResponse
    v2_snapshot: ComplianceSnapshotResponse
    snapshot_diff: SnapshotDiffResponse
    finding_diffs: list[FindingDiffResponse]
    summary: dict[str, int]


class TrendPointResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    snapshot_id: str
    timestamp: str | None = None
    score: float
    total_findings: int
    missing: int
    different: int
    extra: int
    inconsistent: int
    coverage: float
    label: str | None = None


class TrendResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    points: list[TrendPointResponse]
