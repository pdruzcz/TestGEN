"""Code error detection models — Epic 5, Story 5.4.

Stores detected code errors (syntax, logic, semantic, conformance, dead_code) per project.
Each row represents one error with location, severity and suggestion.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ErrorCategory(StrEnum):
    """Categories of code errors."""

    SYNTAX = "syntax"  # parse errors, broken syntax
    LOGIC = "logic"  # missing returns, unreachable paths
    SEMANTIC = "semantic"  # type issues, undefined refs, bare except
    CONFORMANCE = "conformance"  # naming, docstring, convention violations
    DEAD_CODE = "dead_code"  # uncalled private/internal code (Story 5.10)


class CodeErrorStatus(StrEnum):
    """Triage status of a code error (Story 5.10, mirrors finding workflows)."""

    OPEN = "open"
    FALSE_POSITIVE = "false_positive"


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
    )


class CodeError(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """One detected code error with location, severity and suggestion."""

    __tablename__ = "code_errors"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    category: Mapped[ErrorCategory] = mapped_column(
        _enum_col(ErrorCategory, "error_category"),
        index=True,
    )
    message: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    line_start: Mapped[int | None] = mapped_column(Integer, default=None)
    line_end: Mapped[int | None] = mapped_column(Integer, default=None)
    severity: Mapped[str] = mapped_column(String(10), default="warning", index=True)
    rule_id: Mapped[str | None] = mapped_column(String(100), default=None)
    suggestion: Mapped[str | None] = mapped_column(Text, default=None)
    context: Mapped[dict | None] = mapped_column(JSONB, default=None)
    # Triage (Story 5.10 / AC4): dismissed findings survive rescans and
    # suppress re-detection of the same code state via the stable key.
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    fingerprint: Mapped[str | None] = mapped_column(String(300), default=None, index=True)
