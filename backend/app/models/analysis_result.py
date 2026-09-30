"""AnalysisResult model — stores analysis run outputs."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class EngineMode(StrEnum):
    NATIVE = "native"
    LLM = "llm"
    HYBRID = "hybrid"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    PARTIAL_FAILURE = "partial_failure"


class AnalysisResult(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "analysis_results"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    engine_mode: Mapped[EngineMode] = mapped_column(
        Enum(EngineMode, name="analysis_engine_mode", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        default=EngineMode.HYBRID,
    )
    module: Mapped[str] = mapped_column(String(100))
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, name="analysis_status", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        default=AnalysisStatus.PENDING,
    )
    result_data: Mapped[dict | None] = mapped_column(JSONB, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    project = relationship("Project", lazy="raise")
    source_file = relationship("SourceFile", lazy="raise")

    def __repr__(self) -> str:
        try:
            return f"<AnalysisResult id={self.id} status={self.status.value} module={self.module!r}>"
        except Exception:
            return "<AnalysisResult (detached)>"
