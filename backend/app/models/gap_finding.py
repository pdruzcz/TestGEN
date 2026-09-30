"""Functional gap analysis models — Epic 5, Story 5.1.

Stores the result of comparing documentation requirements against code
entities (from Epic 1 AST parser). Each row represents one identified gap
(missing implementation, divergence, extra code, or logical inconsistency)
with fuzzy-match metadata (score, method) and severity.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class GapType(StrEnum):
    """Four types of functional gaps between documentation and code."""

    MISSING = "missing"           # requirement without implementation
    DIFFERENT = "different"       # implementation diverges from specification
    EXTRA = "extra"               # code without documentation counterpart
    INCONSISTENT = "inconsistent"  # logical contradiction


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(enum_cls, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e])


class GapFinding(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """One identified functional gap between a requirement and code."""

    __tablename__ = "gap_findings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    requirement_id: Mapped[str | None] = mapped_column(String(200), default=None)
    code_entity_id: Mapped[str | None] = mapped_column(String(200), default=None)
    gap_type: Mapped[GapType] = mapped_column(
        _enum_col(GapType, "gap_type"),
        index=True,
    )
    description: Mapped[str] = mapped_column(Text)
    requirement_text: Mapped[str | None] = mapped_column(Text, default=None)
    code_reference: Mapped[str | None] = mapped_column(String(500), default=None)
    match_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    match_method: Mapped[str | None] = mapped_column(String(30), default=None)
    context: Mapped[dict | None] = mapped_column(JSONB, default=None)
    severity: Mapped[str] = mapped_column(String(10), default="warning")
    source: Mapped[str] = mapped_column(String(10), default="native")
    skeleton_code: Mapped[str | None] = mapped_column(Text, default=None)
    skeleton_language: Mapped[str | None] = mapped_column(String(20), default=None)
