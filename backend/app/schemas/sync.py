"""Schematy dwukierunkowej synchronizacji z TMS — Epic 8, Story 8.11."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.sync_conflict import ConflictResolution
from app.models.sync_state import (
    DEFAULT_INTERVAL_MINUTES,
    MIN_INTERVAL_MINUTES,
    ConflictStrategy,
    SyncDirection,
)


class SyncConfigRequest(BaseModel):
    """Konfiguracja synchronizacji (AC1)."""

    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    # Dolna granica jest wymuszona tu i w serwisie: walidacja schematu chroni
    # API, a serwis — zadania w tle i przyszłe wywołania wewnętrzne.
    interval_minutes: int = Field(
        default=DEFAULT_INTERVAL_MINUTES, ge=MIN_INTERVAL_MINUTES, le=1440
    )
    conflict_strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS


class SyncStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    integration_id: uuid.UUID
    project_id: uuid.UUID
    provider: str
    direction: SyncDirection
    conflict_strategy: ConflictStrategy
    interval_minutes: int
    is_active: bool
    health: str
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    synced_count: int = 0
    pending_conflicts: int = 0
    next_sync_at: datetime | None = None


class SyncRunResponse(BaseModel):
    """Odpowiedź ręcznego wyzwolenia — przebieg idzie w tle (AC5)."""

    sync_state_id: uuid.UUID
    task_id: str | None = None
    status: str = "accepted"
    status_url: str | None = None


class SyncConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sync_state_id: uuid.UUID
    test_case_id: uuid.UUID
    tms_test_id: str
    testgen_version: dict
    tms_version: dict
    resolution: ConflictResolution
    resolved_at: datetime | None = None
    resolved_by: uuid.UUID | None = None
    created_at: datetime | None = None


class SyncConflictListResponse(BaseModel):
    items: list[SyncConflictResponse]
    total: int


class ConflictResolveRequest(BaseModel):
    """Ręczne rozstrzygnięcie konfliktu (AC4).

    ``pending`` jest świadomie poza listą: rozstrzygnięcie nie może cofnąć
    konfliktu do stanu „oczekuje", bo wersja przegrana zostałaby już wtedy
    nadpisana.
    """

    resolution: ConflictResolution = Field(
        description="testgen_wins, tms_wins albo manual",
    )
