"""Import wymagań z Jiry — Epic 8, Story 8.12.

Jeden wiersz na parę *projekt TestGEN ↔ projekt Jiry*. Trzyma znacznik
ostatniego udanego importu, bo od niego zależy kolejny: import przyrostowy
pyta Jirę o zgłoszenia zmienione po tej dacie, zamiast ściągać wszystko
za każdym razem.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class JiraImportStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Typy zgłoszeń, które umiemy przełożyć na wymagania (AC2). Inne są pomijane:
# zadanie techniczne albo zgłoszenie serwisowe nie opisuje zachowania systemu.
SUPPORTED_ISSUE_TYPES = ("Story", "Epic", "Bug", "Sub-task")


class JiraImport(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Stan importu z jednego projektu Jiry do jednego projektu TestGEN."""

    __tablename__ = "jira_imports"
    __table_args__ = (
        # Jeden wiersz na parę projektów: drugi gubiłby znacznik
        # ostatniego importu i przyrostowy przestałby być przyrostowy.
        UniqueConstraint("project_id", "jira_project_key", name="uq_jira_imports_project_key"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_configs.id", ondelete="CASCADE"),
        index=True,
    )
    jira_project_key: Mapped[str] = mapped_column(String(64), index=True)
    issue_types: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)

    status: Mapped[JiraImportStatus] = mapped_column(
        Enum(JiraImportStatus, name="jira_import_status", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        default=JiraImportStatus.PENDING,
        index=True,
    )
    # Znacznik ostatniego **udanego** importu — nieudany go nie przesuwa,
    # inaczej zgłoszenia z przerwanego przebiegu zniknęłyby z następnego.
    last_import_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    total_imported: Mapped[int] = mapped_column(Integer, default=0)
    total_attachments: Mapped[int] = mapped_column(Integer, default=0)
    total_skipped: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    task_id: Mapped[str | None] = mapped_column(String(64), default=None)
    # Dokument-kontener, pod którym żyją zaimportowane wymagania. Wymagania
    # w TestGEN wiszą przy pliku źródłowym, więc import zakłada jeden
    # syntetyczny „dokument" na projekt Jiry.
    document_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id", ondelete="SET NULL"),
        default=None,
    )
