"""Visual regression models — Epic 3, Story 3.10.

Persists the result of comparing two GUI screenshots (baseline vs comparison):
the pixel-diff percentage, the per-component semantic delta, the classified
changes and an optional generated diff-image. Tenant scope is enforced at the DB
level via RLS, analogous to ``gui_screenshots``.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ComparisonStatus(StrEnum):
    """Overall outcome of a visual regression comparison."""

    MATCH = "match"
    MINOR_DIFF = "minor_diff"
    MAJOR_DIFF = "major_diff"
    ERROR = "error"


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(enum_cls, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e])


class VisualRegressionResult(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "visual_regression_results"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    baseline_screenshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gui_screenshots.id", ondelete="CASCADE"),
        index=True,
    )
    comparison_screenshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gui_screenshots.id", ondelete="CASCADE"),
        index=True,
    )
    pixel_diff_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_diff: Mapped[list | None] = mapped_column(JSONB, default=None)
    changes: Mapped[list | None] = mapped_column(JSONB, default=None)
    diff_image_key: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[ComparisonStatus] = mapped_column(
        _enum_col(ComparisonStatus, "comparison_status"),
        default=ComparisonStatus.MATCH,
        index=True,
    )
    warnings: Mapped[list | None] = mapped_column(JSONB, default=None)

    baseline_screenshot = relationship(
        "GUIScreenshot", foreign_keys=[baseline_screenshot_id], lazy="raise"
    )
    comparison_screenshot = relationship(
        "GUIScreenshot", foreign_keys=[comparison_screenshot_id], lazy="raise"
    )

    def __repr__(self) -> str:
        try:
            return (
                f"<VisualRegressionResult id={self.id} "
                f"status={self.status.value} pixel_diff={self.pixel_diff_percentage:.2f}>"
            )
        except Exception:
            return "<VisualRegressionResult (detached)>"
