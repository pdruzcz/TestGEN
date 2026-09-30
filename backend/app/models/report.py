"""Report model — generated reports from analysis results."""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ReportFormat(StrEnum):
    PDF = "pdf"
    HTML = "html"
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    YAML = "yaml"


class Report(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "reports"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500))
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format", native_enum=True, values_callable=lambda e: [m.value for m in e]),
    )
    content: Mapped[dict | None] = mapped_column(JSONB, default=None)
    file_url: Mapped[str | None] = mapped_column(String(1000), default=None)

    project = relationship("Project", lazy="raise")

    def __repr__(self) -> str:
        try:
            return f"<Report id={self.id} title={self.title!r} format={self.format.value}>"
        except Exception:
            return "<Report (detached)>"
