"""Konflikty synchronizacji z TMS — Epic 8, Story 8.11 (AC4).

Konflikt zapisujemy nawet wtedy, gdy strategia ``last_write_wins`` od razu
go rozstrzyga. Przegrana wersja to jedyny ślad po danych, które zostały
nadpisane — bez niego analityk nie odtworzy, co zniknęło i dlaczego.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ConflictResolution(StrEnum):
    PENDING = "pending"
    TESTGEN_WINS = "testgen_wins"
    TMS_WINS = "tms_wins"
    MANUAL = "manual"


class SyncConflict(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Jedna kolizja: ten sam przypadek zmieniony po obu stronach."""

    __tablename__ = "sync_conflicts"

    sync_state_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sync_states.id", ondelete="CASCADE"),
        index=True,
    )
    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        index=True,
    )
    # Identyfikator po stronie TMS-a: TestRail adresuje liczbą, Jira kluczem —
    # stąd tekst, a nie liczba.
    tms_test_id: Mapped[str] = mapped_column(String(64))
    testgen_version: Mapped[dict] = mapped_column(JSONB, default=dict)
    tms_version: Mapped[dict] = mapped_column(JSONB, default=dict)
    resolution: Mapped[ConflictResolution] = mapped_column(
        Enum(ConflictResolution, name="sync_conflict_resolution", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        default=ConflictResolution.PENDING,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
