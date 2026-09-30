"""SourceFile model — code uploads and git-cloned files attached to a project.

Tenant scope is enforced at the DB level via RLS. No soft-delete: rows are
hard-deleted by the Celery cleanup task once `is_cleaned_up = True`.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class FileCategory(StrEnum):
    """Source file category for analysis routing."""

    CODE = "code"
    DOCUMENTATION = "documentation"
    UML = "uml"
    GUI = "gui"
    GUI_DOM = "gui_dom"
    # Story 1.6-zakańczenie: config/fixture data (composer.json, package.json, …).
    # Available to autodetection (FrameworkDetector), but NOT AST-parsed (CODE)
    # and NOT sent to the E2 documentation parser (DOCUMENTATION).
    DATA = "data"


class DocumentFormat(StrEnum):
    """Documentation file formats."""

    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "md"
    HTML = "html"
    TXT = "txt"


class FileProcessingStatus(StrEnum):
    """Universal processing status for ALL source files.

    Applies to code (preprocessing), documentation (parsing), and any
    future file types.  The status tracks the file-level processing
    lifecycle; analysis-level status lives in ``AnalysisResult``.
    """

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SourceFile(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "source_files"
    __table_args__ = (
        UniqueConstraint("project_id", "storage_key", name="uq_source_files_project_storage_key"),
        # Partial unique index — only enforces uniqueness for active files.
        # Allows re-uploading the same content after soft-delete.
        Index(
            "uq_source_files_project_hash",
            "project_id",
            "sha256_hash",
            unique=True,
            postgresql_where=text("NOT is_cleaned_up"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(500))
    original_path: Mapped[str | None] = mapped_column(String(1000), default=None)
    storage_key: Mapped[str] = mapped_column(String(1000))
    file_size: Mapped[int] = mapped_column()  # bytes
    mime_type: Mapped[str | None] = mapped_column(String(100), default=None)
    sha256_hash: Mapped[str] = mapped_column(String(64))
    detected_language: Mapped[str | None] = mapped_column(String(50), default=None, index=True)
    detected_framework: Mapped[str | None] = mapped_column(String(100), default=None)
    requires_manual_classification: Mapped[bool] = mapped_column(Boolean, default=False)
    loc_count: Mapped[int] = mapped_column(Integer, default=0)
    is_cleaned_up: Mapped[bool] = mapped_column(default=False)

    # Epic 2: Documentation analysis fields
    file_category: Mapped[FileCategory] = mapped_column(
        Enum(FileCategory, name="file_category", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        default=FileCategory.CODE,
        index=True,
    )
    doc_format: Mapped[DocumentFormat | None] = mapped_column(
        Enum(DocumentFormat, name="document_format", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        default=None,
    )
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)  # For PDF documents

    # Processing lifecycle — universal for all file categories
    processing_status: Mapped[FileProcessingStatus] = mapped_column(
        Enum(
            FileProcessingStatus,
            name="file_processing_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=FileProcessingStatus.UPLOADED,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    project = relationship("Project", lazy="raise")

    def __repr__(self) -> str:
        try:
            return (
                f"<SourceFile id={self.id} filename={self.filename!r} "
                f"category={self.file_category.value} size={self.file_size} "
                f"cleaned_up={self.is_cleaned_up}>"
            )
        except Exception:
            return "<SourceFile (detached)>"
