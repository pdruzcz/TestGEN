"""Pydantic schemas for the security module — Epic 4, Story 4.1."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScanTypeEnum(StrEnum):
    SAST = "sast"
    TAINT = "taint"
    DEPENDENCY = "dependency"
    CONFIG = "config"
    DAST = "dast"


class SeverityEnum(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AnalysisSourceEnum(StrEnum):
    NATIVE = "native"
    LLM = "llm"
    HYBRID = "hybrid"


class FindingStatusEnum(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    FIXED = "fixed"
    FALSE_POSITIVE = "false_positive"


class DASTAuthConfig(BaseModel):
    auth_type: Literal["form", "token", "basic"]
    login_url: str | None = None
    username_field: str | None = None
    password_field: str | None = None
    token: str | None = None
    username: str | None = None
    password: str | None = None


class SecurityScanRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scan_type: ScanTypeEnum = ScanTypeEnum.SAST
    target_url: str | None = None  # for DAST
    auth_config: DASTAuthConfig | None = None  # for DAST authenticated scans


class SecurityScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: uuid.UUID
    task_id: str | None = None
    status: str
    created_at: datetime | None = None


class SecurityFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_id: uuid.UUID
    scan_type: str
    vulnerability_type: str
    severity: str
    cwe_id: str | None = None
    owasp_category: str | None = None
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    code_snippet: str | None = None
    description: str
    confidence: float
    source: str
    status: str
    taint_path: dict | None = None
    finding_metadata: dict | None = None
    recommendation: str | None = None
    cvss_score: float | None = None
    cvss_vector: str | None = None
    priority: int | None = None
    effort: str | None = None
    escalation_reason: str | None = None
    created_at: datetime | None = None


class SecurityFindingListResponse(BaseModel):
    findings: list[SecurityFindingResponse]
    total: int
    page: int = 1
    page_size: int = 50


class SeverityCounts(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class SecurityScanStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: uuid.UUID
    scan_type: str
    engine_mode: str
    status: str
    findings_count: int = 0
    severity_counts: SeverityCounts = Field(default_factory=SeverityCounts)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None


class SecurityScanListResponse(BaseModel):
    scans: list[SecurityScanStatusResponse]
    total: int


class SecurityReportSummary(BaseModel):
    total_findings: int = 0
    severity_counts: dict[str, int] = Field(default_factory=dict)
    source_counts: dict[str, int] = Field(default_factory=dict)


class SecurityReportResponse(BaseModel):
    summary: SecurityReportSummary
    findings: list[SecurityFindingResponse]
    dedup_count: int = 0
    correlation_count: int = 0


class FindingStatusUpdateRequest(BaseModel):
    status: FindingStatusEnum


class RepairStep(BaseModel):
    finding_id: uuid.UUID
    vulnerability_type: str
    severity: str
    cvss_score: float | None = None
    effort: str | None = None
    priority: int | None = None


class SecurityDashboardResponse(BaseModel):
    cvss_distribution: dict[str, int] = Field(default_factory=dict)
    top_10_findings: list[SecurityFindingResponse] = Field(default_factory=list)
    repair_sequence: list[RepairStep] = Field(default_factory=list)
    total_findings: int = 0


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RecommendationResponse(BaseModel):
    finding_id: uuid.UUID
    problem_description: str
    risk_description: str
    fix_description: str
    fixed_code_snippet: str
    diff: str
    language: str
    engine_source: str


class PoCRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PoCResponse(BaseModel):
    finding_id: uuid.UUID
    payload: str
    reproduction_steps: list[str]
    expected_effect: str
    severity: str
    is_safe: bool
    disclaimer: str
    engine_source: str


class PatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ConflictReportResponse(BaseModel):
    patch_a_id: uuid.UUID
    patch_b_id: uuid.UUID
    overlapping_lines: list[int] = Field(default_factory=list)
    severity: str  # critical (same lines) | warning (adjacent lines)


class PatchResponse(BaseModel):
    finding_id: uuid.UUID
    file_path: str
    patch_content: str
    patch_filename: str
    is_valid: bool
    conflicts: list[ConflictReportResponse] = Field(default_factory=list)


class BatchPatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    finding_ids: list[uuid.UUID] = Field(default_factory=list)


class BatchPatchResponse(BaseModel):
    patches: list[PatchResponse] = Field(default_factory=list)
    conflicts: list[ConflictReportResponse] = Field(default_factory=list)
    total: int = 0


class PatchPreviewResponse(BaseModel):
    finding_id: uuid.UUID
    file_path: str
    patch_content: str
    original_code: str
    fixed_code: str
    is_valid: bool


# ----- CVE pipeline (Story 4.12) -----------------------------------------


class CVESourceStatusResponse(BaseModel):
    source: str
    ok: bool
    fetched: int = 0
    error: str | None = None


class CVEPipelineStatusResponse(BaseModel):
    last_run_at: datetime | None = None
    last_status: str | None = None
    total_new: int = 0
    total_updated: int = 0
    affected_projects: int = 0
    sources_status: dict[str, CVESourceStatusResponse] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    schedule: str = "1. dnia miesiąca o 02:00"


class CVEPipelineLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    total_new: int = 0
    total_updated: int = 0
    affected_projects: int = 0
    sources_status: dict | None = None
    errors: list | None = None


class CVEPipelineLogListResponse(BaseModel):
    logs: list[CVEPipelineLogResponse] = Field(default_factory=list)
    total: int = 0


class CVEPipelineTriggerResponse(BaseModel):
    status: str
    task_id: str | None = None
    message: str


# ----- Dual-path comparison (Story 4.13) ---------------------------------
