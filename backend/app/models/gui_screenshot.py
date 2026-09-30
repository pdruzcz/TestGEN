"""GUI screenshot models — Epic 3, Story 3.8: GUI upload + analysis.

Stores uploaded GUI screenshots, the result of their OCR + Computer Vision
analysis (text blocks, layout tree) and the individual detected UI components.
Tenant scope on ``gui_screenshots`` is enforced at the DB level via RLS,
analogous to ``uml_diagrams``.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class GUIComponentType(StrEnum):
    """Categories of UI elements detected on a screenshot."""

    BUTTON = "button"
    INPUT = "input"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    MENU = "menu"
    LINK = "link"
    TABLE = "table"
    FORM = "form"
    MODAL = "modal"
    TAB = "tab"
    UNKNOWN = "unknown"


class GUIAnalysisStatus(StrEnum):
    """Lifecycle status of a screenshot's analysis pipeline."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GUIAnalysisSourceType(StrEnum):
    """Origin of a GUI analysis — Story 1.51-zakańczenie.

    ``screenshot``: CV/OCR pipeline on a raster screenshot (Epic 3, Story 3.8).
    ``dom``: HTML/DOM (+ optional a11y.json) source carrying real locator
    attributes for self-healing (Story 1.51-zakańczenie, Part A).
    """

    SCREENSHOT = "screenshot"
    DOM = "dom"


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(enum_cls, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e])


class GUIScreenshot(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "gui_screenshots"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(500))
    storage_key: Mapped[str] = mapped_column(String(1000))
    screen_sequence: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[GUIAnalysisStatus] = mapped_column(
        _enum_col(GUIAnalysisStatus, "gui_analysis_status"),
        default=GUIAnalysisStatus.PENDING,
        index=True,
    )
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(100), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    project = relationship("Project", lazy="raise")
    analysis_result = relationship(
        "GUIAnalysisResult",
        back_populates="screenshot",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="raise",
    )

    def __repr__(self) -> str:
        try:
            return f"<GUIScreenshot id={self.id} filename={self.filename!r} status={self.status.value}>"
        except Exception:
            return "<GUIScreenshot (detached)>"


class GUIAnalysisResult(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "gui_analysis_results"

    screenshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("gui_screenshots.id", ondelete="CASCADE"),
        index=True,
        default=None,
    )
    source_type: Mapped[GUIAnalysisSourceType] = mapped_column(
        _enum_col(GUIAnalysisSourceType, "gui_analysis_source_type"),
        default=GUIAnalysisSourceType.SCREENSHOT,
        index=True,
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id", ondelete="SET NULL"),
        index=True,
        default=None,
    )
    version_label: Mapped[str | None] = mapped_column(String(100), default=None)
    ocr_text_blocks: Mapped[list | None] = mapped_column(JSONB, default=None)
    layout_tree: Mapped[dict | None] = mapped_column(JSONB, default=None)
    warnings: Mapped[list | None] = mapped_column(JSONB, default=None)
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0)

    screenshot = relationship("GUIScreenshot", back_populates="analysis_result", lazy="raise")
    source_file = relationship("SourceFile", lazy="raise")
    components = relationship(
        "GUIComponent",
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="GUIComponent.sequence",
        lazy="raise",
    )

    def __repr__(self) -> str:
        try:
            return f"<GUIAnalysisResult id={self.id} source={self.source_type.value} screenshot={self.screenshot_id}>"
        except Exception:
            return "<GUIAnalysisResult (detached)>"


class GUIComponent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "gui_components"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gui_analysis_results.id", ondelete="CASCADE"),
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    component_type: Mapped[GUIComponentType] = mapped_column(
        _enum_col(GUIComponentType, "gui_component_type"),
        index=True,
    )
    label: Mapped[str | None] = mapped_column(String(500), default=None)
    bbox: Mapped[dict | None] = mapped_column(JSONB, default=None)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    attributes: Mapped[dict | None] = mapped_column(JSONB, default=None)

    analysis = relationship("GUIAnalysisResult", back_populates="components", lazy="raise")

    def __repr__(self) -> str:
        try:
            return f"<GUIComponent id={self.id} type={self.component_type.value} label={self.label!r}>"
        except Exception:
            return "<GUIComponent (detached)>"
