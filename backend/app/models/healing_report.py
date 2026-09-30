"""Healing models — Epic 1, Story 1.51.

Self-healing of broken UI-test locators between two GUI/code versions (FR69).
A ``HealingReport`` aggregates the per-locator ``HealingItem`` results of one
healing run; each item records the old → new locator, the strategy, a
confidence score and the healing method (native / llm / hybrid).  Tenant
isolation via RLS, analogous to ``recommendations`` / ``gap_findings``.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class HealingStatus(StrEnum):
    """Lifecycle of a healing run (report) and of a single locator item."""

    PENDING = "pending"
    HEALED = "healed"  # repaired, confidence >= threshold
    NEEDS_REVIEW = "needs_review"  # confidence < threshold
    FAILED = "failed"  # no candidate found
    REJECTED = "rejected"  # user rejected the proposed fix


class LocatorStrategy(StrEnum):
    """Locator strategies, ordered stable -> brittle (healing preference)."""

    DATA_TESTID = "data-testid"
    ROLE_NAME = "role+name"
    ARIA_LABEL = "aria-label"
    ID = "id"
    CSS = "css"
    XPATH = "xpath"


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
    )


class HealingReport(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """One self-healing run over a project between two versions."""

    __tablename__ = "healing_reports"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    version_a: Mapped[str] = mapped_column(String(255))
    version_b: Mapped[str] = mapped_column(String(255))
    status: Mapped[HealingStatus] = mapped_column(
        _enum_col(HealingStatus, "healing_status"),
        default=HealingStatus.PENDING,
        index=True,
    )
    # JSONB: {total, healthy, healed, needs_review, failed, avg_confidence, duration_s}
    stats: Mapped[dict | None] = mapped_column(JSONB, default=None)

    items: Mapped[list["HealingItem"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        try:
            return f"<HealingReport id={self.id} project_id={self.project_id} status={self.status!r}>"
        except Exception:
            return "<HealingReport (detached)>"


class HealingItem(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """One broken locator and its proposed (or accepted) replacement."""

    __tablename__ = "healing_items"

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("healing_reports.id", ondelete="CASCADE"),
        index=True,
    )
    test_code_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_codes.id", ondelete="CASCADE"),
        index=True,
    )
    old_locator: Mapped[str] = mapped_column(Text)
    old_strategy: Mapped[LocatorStrategy] = mapped_column(
        _enum_col(LocatorStrategy, "locator_strategy"),
    )
    new_locator: Mapped[str | None] = mapped_column(Text, default=None)
    new_strategy: Mapped[LocatorStrategy | None] = mapped_column(
        _enum_col(LocatorStrategy, "locator_strategy"),
        default=None,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    healing_method: Mapped[str] = mapped_column(String(30), default="native")
    status: Mapped[HealingStatus] = mapped_column(
        _enum_col(HealingStatus, "healing_status"),
        default=HealingStatus.PENDING,
        index=True,
    )
    diff_preview: Mapped[str | None] = mapped_column(Text, default=None)

    report: Mapped["HealingReport"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        try:
            return (
                f"<HealingItem id={self.id} report_id={self.report_id} "
                f"status={self.status!r} confidence={self.confidence}>"
            )
        except Exception:
            return "<HealingItem (detached)>"
