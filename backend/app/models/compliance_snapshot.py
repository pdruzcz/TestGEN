"""Compliance snapshot model — Epic 5, Story 5.7.

Stores a point-in-time snapshot of compliance metrics for a project.
Created automatically after each gap analysis run, or manually by the user.
Enables version comparison and trend analysis.
"""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ComplianceSnapshot(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """One compliance score snapshot for version comparison."""

    __tablename__ = "compliance_snapshots"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    score: Mapped[float] = mapped_column(Float, default=100.0)
    total_findings: Mapped[int] = mapped_column(Integer, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, default=0)
    different_count: Mapped[int] = mapped_column(Integer, default=0)
    extra_count: Mapped[int] = mapped_column(Integer, default=0)
    inconsistent_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_match_score: Mapped[float] = mapped_column(Float, default=0.0)
    coverage_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    label: Mapped[str | None] = mapped_column(String(200), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
