"""Recommendation models — Epic 5, Story 5.5.

Stores actionable recommendations generated from gap findings and code errors.
Each row has a priority (P1–P4), confidence score (0–1), and an optional
suggestion / fix description.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class RecommendationPriority(StrEnum):
    """Priority levels — P1 (urgent) to P4 (low)."""

    P1 = "P1"   # inconsistent / missing+critical — fix immediately
    P2 = "P2"   # different / logic errors — fix soon
    P3 = "P3"   # semantic / conformance — schedule
    P4 = "P4"   # extra / info — optional


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
    )


class Recommendation(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """One actionable recommendation derived from analysis findings."""

    __tablename__ = "recommendations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    gap_finding_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gap_findings.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    code_error_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("code_errors.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[RecommendationPriority] = mapped_column(
        _enum_col(RecommendationPriority, "recommendation_priority"),
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    source_type: Mapped[str] = mapped_column(String(30), default="gap_finding")
    source_ref: Mapped[str | None] = mapped_column(String(500), default=None)
    suggestion: Mapped[str | None] = mapped_column(Text, default=None)
    context: Mapped[dict | None] = mapped_column(JSONB, default=None)
