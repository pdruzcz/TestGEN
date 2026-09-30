"""Stan dwukierunkowej synchronizacji z TMS — Epic 8, Story 8.11.

Osobna tabela od ``integration_configs``, mimo że AC1 mówi o zapisie
w ``config`` JSONB: harmonogram musi dać się odpytać indeksem
(„które synchronizacje są zaległe"), a pole JSONB wymagałoby przejrzenia
wszystkich integracji przy każdym przebiegu beat-a.

Jeden wiersz na integrację — kierunek, odstęp i zdrowie należą do pary
*projekt ↔ TMS*, a nie do pojedynczego przebiegu.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin
from app.models.integration import SyncStatus


class SyncDirection(StrEnum):
    PUSH = "push"
    PULL = "pull"
    BIDIRECTIONAL = "bidirectional"


class ConflictStrategy(StrEnum):
    LAST_WRITE_WINS = "last_write_wins"
    MANUAL = "manual"


class SyncHealth(StrEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"


# Minimalny odstęp z AC1. Krótszy nie ma sensu: TestRail i Jira dławią tempo
# żądań, więc pełny przebieg po setce przypadków i tak trwa minuty.
MIN_INTERVAL_MINUTES = 5
DEFAULT_INTERVAL_MINUTES = 15

# Po tylu nieudanych przebiegach z rzędu synchronizacja idzie w stan
# ``degraded`` i Owner dostaje powiadomienie (AC6). Trzy, a nie jeden, bo
# pojedynczy timeout TMS-a zdarza się przy każdym wdrożeniu po ich stronie.
DEGRADED_AFTER_FAILURES = 3


class SyncState(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Konfiguracja i stan synchronizacji jednej integracji TMS."""

    __tablename__ = "sync_states"
    __table_args__ = (
        # Jedna synchronizacja na integrację: dwa wiersze dla tego samego
        # TMS-a ścigałyby się o te same przypadki i produkowały konflikty
        # z niczego.
        UniqueConstraint("integration_id", name="uq_sync_states_integration_id"),
    )

    integration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_configs.id", ondelete="CASCADE"),
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    direction: Mapped[SyncDirection] = mapped_column(
        Enum(SyncDirection, name="sync_direction", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        default=SyncDirection.BIDIRECTIONAL,
    )
    conflict_strategy: Mapped[ConflictStrategy] = mapped_column(
        Enum(ConflictStrategy, name="sync_conflict_strategy", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        default=ConflictStrategy.LAST_WRITE_WINS,
    )
    interval_minutes: Mapped[int] = mapped_column(Integer, default=DEFAULT_INTERVAL_MINUTES)
    is_active: Mapped[bool] = mapped_column(default=False, index=True)

    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_sync_status: Mapped[SyncStatus | None] = mapped_column(
        Enum(SyncStatus, name="sync_status", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        default=None,
    )
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    health: Mapped[SyncHealth] = mapped_column(
        Enum(SyncHealth, name="sync_health", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        default=SyncHealth.ACTIVE,
        index=True,
    )
    # Licznik przypadków objętych ostatnim udanym przebiegiem — pokazywany
    # na ekranie synchronizacji (AC5).
    synced_count: Mapped[int] = mapped_column(Integer, default=0)
    # Zapamiętany dostawca ułatwia listowanie bez dociągania integracji.
    provider: Mapped[str] = mapped_column(String(32), default="testrail")

    @property
    def pushes(self) -> bool:
        return self.direction in (SyncDirection.PUSH, SyncDirection.BIDIRECTIONAL)

    @property
    def pulls(self) -> bool:
        return self.direction in (SyncDirection.PULL, SyncDirection.BIDIRECTIONAL)
