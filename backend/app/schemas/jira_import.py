"""Schematy importu wymagań z Jiry — Epic 8, Story 8.12.

Nazwa pliku to ``jira_import``, a nie ``import`` ze story: ``import`` jest
słowem kluczowym Pythona, więc moduł o tej nazwie dałoby się zaimportować
wyłącznie okrężnie.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.jira_import import SUPPORTED_ISSUE_TYPES, JiraImportStatus


class JiraProjectOption(BaseModel):
    key: str
    name: str


class JiraProjectListResponse(BaseModel):
    items: list[JiraProjectOption]
    total: int


class JiraImportRequest(BaseModel):
    """Zakres importu (AC5)."""

    jira_project_key: str = Field(min_length=1, max_length=64)
    issue_types: list[str] = Field(default_factory=lambda: list(SUPPORTED_ISSUE_TYPES))
    # Podana data zastępuje znacznik ostatniego importu — pozwala pobrać
    # zgłoszenia starsze niż ostatni przebieg, np. po zmianie zakresu.
    updated_after: datetime | None = None
    # Pełny import ignoruje znacznik ostatniego przebiegu i pobiera wszystko.
    full_reimport: bool = False


class JiraImportAcceptedResponse(BaseModel):
    import_id: uuid.UUID
    task_id: str | None = None
    status: str = "accepted"
    status_url: str | None = None


class JiraImportStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    integration_id: uuid.UUID
    jira_project_key: str
    issue_types: list[str]
    status: JiraImportStatus
    last_import_at: datetime | None = None
    total_imported: int = 0
    total_attachments: int = 0
    total_skipped: int = 0
    last_error: str | None = None
    task_id: str | None = None
    document_file_id: uuid.UUID | None = None
    created_at: datetime | None = None
