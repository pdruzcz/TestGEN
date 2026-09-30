"""Security scanning models — Epic 4, Story 4.1.

Central data model for the security module. ``SecurityScan`` tracks one scan run
(SAST / taint / dependency / config / DAST) and ``SecurityFinding`` stores each
detected vulnerability. Both share the multi-tenant mixins; tenant isolation is
enforced at the DB level via RLS, analogous to ``analysis_results``.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ScanType(StrEnum):
    SAST = "sast"
    TAINT = "taint"
    DEPENDENCY = "dependency"
    CONFIG = "config"
    DAST = "dast"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AnalysisSource(StrEnum):
    NATIVE = "native"
    LLM = "llm"
    HYBRID = "hybrid"


class FindingStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    FIXED = "fixed"
    FALSE_POSITIVE = "false_positive"


class ScanStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(enum_cls, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e])


class SecurityScan(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "security_scans"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    scan_type: Mapped[ScanType] = mapped_column(_enum_col(ScanType, "scan_type"), index=True)
    engine_mode: Mapped[str] = mapped_column(String(20), default="native")
    status: Mapped[ScanStatus] = mapped_column(
        _enum_col(ScanStatus, "scan_status"),
        default=ScanStatus.PENDING,
        index=True,
    )
    task_id: Mapped[str | None] = mapped_column(String(100), default=None)
    target_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    # Free-form per-scan payload (e.g. generated SBOM for dependency scans).
    scan_metadata: Mapped[dict | None] = mapped_column(JSONB, default=None)

    project = relationship("Project", lazy="raise")

    def __repr__(self) -> str:
        try:
            return (
                f"<SecurityScan id={self.id} type={self.scan_type.value} "
                f"status={self.status.value} findings={self.findings_count}>"
            )
        except Exception:
            return "<SecurityScan (detached)>"


class SecurityFinding(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "security_findings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("security_scans.id", ondelete="CASCADE"),
        index=True,
    )
    scan_type: Mapped[ScanType] = mapped_column(_enum_col(ScanType, "scan_type"), index=True)
    vulnerability_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[Severity] = mapped_column(_enum_col(Severity, "severity"), index=True)
    cwe_id: Mapped[str | None] = mapped_column(String(20), default=None)
    owasp_category: Mapped[str | None] = mapped_column(String(100), default=None)
    file_path: Mapped[str | None] = mapped_column(String(1000), default=None)
    line_start: Mapped[int | None] = mapped_column(Integer, default=None)
    line_end: Mapped[int | None] = mapped_column(Integer, default=None)
    code_snippet: Mapped[str | None] = mapped_column(Text, default=None)
    description: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0-1.0
    source: Mapped[AnalysisSource] = mapped_column(
        _enum_col(AnalysisSource, "analysis_source"),
        default=AnalysisSource.NATIVE,
    )
    status: Mapped[FindingStatus] = mapped_column(
        _enum_col(FindingStatus, "finding_status"),
        default=FindingStatus.OPEN,
        index=True,
    )
    taint_path: Mapped[dict | None] = mapped_column(JSONB, default=None)
    recommendation: Mapped[str | None] = mapped_column(Text, default=None)
    finding_metadata: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Risk engine fields (Story 4.8).
    cvss_score: Mapped[float | None] = mapped_column(Float, default=None)
    cvss_vector: Mapped[str | None] = mapped_column(String(100), default=None)
    priority: Mapped[int | None] = mapped_column(Integer, default=None)  # 1 = highest
    effort: Mapped[str | None] = mapped_column(String(10), default=None)  # low/medium/high
    escalation_reason: Mapped[str | None] = mapped_column(Text, default=None)
    # Proof-of-concept fields (Story 4.10) — safe, non-destructive demonstrations.
    poc_payload: Mapped[str | None] = mapped_column(Text, default=None)
    poc_steps: Mapped[dict | None] = mapped_column(JSONB, default=None)
    poc_expected_effect: Mapped[str | None] = mapped_column(Text, default=None)

    project = relationship("Project", lazy="raise")
    scan = relationship("SecurityScan", lazy="raise")

    def __repr__(self) -> str:
        try:
            return (
                f"<SecurityFinding {self.vulnerability_type} "
                f"severity={self.severity.value} file={self.file_path}:{self.line_start}>"
            )
        except Exception:
            return "<SecurityFinding (detached)>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "scan_id": str(self.scan_id),
            "scan_type": self.scan_type.value if self.scan_type else None,
            "vulnerability_type": self.vulnerability_type,
            "severity": self.severity.value if self.severity else None,
            "cwe_id": self.cwe_id,
            "owasp_category": self.owasp_category,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "code_snippet": self.code_snippet,
            "description": self.description,
            "confidence": self.confidence,
            "source": self.source.value if self.source else None,
            "status": self.status.value if self.status else None,
            "taint_path": self.taint_path,
            "recommendation": self.recommendation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CVEDatabase(Base, UUIDMixin, TimestampMixin):
    """Local cache of CVE entries (shared across tenants).

    Populated from external databases (NVD/OSV/Snyk) by the dependency scanner
    (Story 4.4) and refreshed by the CVE auto-update pipeline (Story 4.12). Not
    tenant-scoped — vulnerability data is public reference data.
    """

    __tablename__ = "cve_database"

    cve_id: Mapped[str] = mapped_column(String(40), index=True)
    package_name: Mapped[str] = mapped_column(String(255), index=True)
    ecosystem: Mapped[str] = mapped_column(String(40), index=True)
    cvss_score: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[Severity] = mapped_column(_enum_col(Severity, "severity"))
    description: Mapped[str] = mapped_column(Text, default="")
    affected_versions: Mapped[str | None] = mapped_column(String(500), default=None)
    fixed_version: Mapped[str | None] = mapped_column(String(100), default=None)
    published_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    source_db: Mapped[str] = mapped_column(String(20), default="osv")  # nvd / osv / snyk

    def __repr__(self) -> str:
        return f"<CVEDatabase {self.cve_id} {self.package_name} cvss={self.cvss_score}>"


class CVEUpdateLog(Base, UUIDMixin, TimestampMixin):
    """Audit log of CVE auto-update pipeline runs (Story 4.12).

    One row per pipeline execution. Powers the admin dashboard: last update time,
    new/updated CVE counts, per-source status and any errors. Not tenant-scoped —
    the pipeline is a platform-wide background job.
    """

    __tablename__ = "cve_update_logs"

    status: Mapped[str] = mapped_column(String(20), default="running")  # running/completed/failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    total_new: Mapped[int] = mapped_column(Integer, default=0)
    total_updated: Mapped[int] = mapped_column(Integer, default=0)
    affected_projects: Mapped[int] = mapped_column(Integer, default=0)
    sources_status: Mapped[dict | None] = mapped_column(JSONB, default=None)
    errors: Mapped[list | None] = mapped_column(JSONB, default=None)

    def __repr__(self) -> str:
        return f"<CVEUpdateLog {self.status} new={self.total_new} updated={self.total_updated}>"
