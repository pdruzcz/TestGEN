"""Schematy eksportu raportów — Story 6.7 (FR45)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExportFormat = Literal["pdf", "html", "csv", "xlsx", "json", "yaml"]

ExportStatus = Literal["pending", "done", "error"]


class ReportKpisPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    compliance_score: float | None = None
    coverage_percentage: float | None = None
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    test_cases_total: int = 0
    test_cases_ready: int = 0
    test_cases_passed: int = 0


class ReportFindingPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    source: str = "security"
    title: str = ""
    description: str = ""
    severity: str = "low"
    cwe_id: str | None = None
    cvss_score: float | None = None
    file_path: str | None = None
    line_start: int | None = None
    code_snippet: str | None = None
    language: str | None = None
    recommendation: str | None = None


class ModuleScorePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    file_path: str = ""
    score: float = 0
    total_findings: int = 0


class TrendPointPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    score: float = 0
    timestamp: str | None = None


class ReportPayload(BaseModel):
    """Dane raportu zagregowane przez FE (Story 6.6), snake_case zgodnie z API."""

    model_config = ConfigDict(extra="ignore")

    project_id: str = ""
    generated_at: str = ""
    kpis: ReportKpisPayload = Field(default_factory=ReportKpisPayload)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    module_scores: list[ModuleScorePayload] = Field(default_factory=list)
    trend_points: list[TrendPointPayload] = Field(default_factory=list)
    conclusions: list[str] = Field(default_factory=list)
    findings: list[ReportFindingPayload] = Field(default_factory=list)


class ReportExportRequest(BaseModel):
    format: ExportFormat
    report_type: Literal["executive", "technical", "both"] = "both"
    report: ReportPayload


class ReportExportResponse(BaseModel):
    export_id: str
    status: ExportStatus


class ExportStatusResponse(BaseModel):
    export_id: str
    status: ExportStatus
    export_format: ExportFormat
    filename: str
    error: str | None = None
