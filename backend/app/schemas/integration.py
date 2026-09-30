"""Pydantic schemas for integration endpoints — Epic 5, Stories 5.8/5.9."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IntegrationConfigRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    provider: Literal["jira", "azure_devops"]
    base_url: str = Field(..., min_length=1, max_length=500)
    email: str = Field(default="", max_length=500)  # Jira uses email; ADO uses PAT only
    api_token: str = Field(..., min_length=1)
    project_key: str = Field(default="", max_length=50)
    issue_type: str = Field(default="Task", max_length=50)
    organization: str = Field(default="", max_length=200)  # Azure DevOps org
    project: str = Field(default="", max_length=200)  # Azure DevOps project name


class IntegrationConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    provider: str
    base_url: str
    settings: dict | None = None
    is_active: bool
    created_at: datetime


class IntegrationTestResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    connected: bool
    message: str = ""


class IntegrationSyncRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sync_type: Literal["gap_findings", "recommendations"] = "gap_findings"


class IntegrationSyncResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str
    status: str = "pending"


class SyncLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    integration_config_id: uuid.UUID
    sync_type: str
    status: str
    items_total: int
    items_synced: int
    errors: dict | None = None
    created_at: datetime
    completed_at: datetime | None = None


class SyncResultResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total: int = 0
    synced: int = 0
    errors: list[dict[str, str]] = Field(default_factory=list)


# ── Epic 8, Story 8.1: integracje SCM (GitHub/GitLab) ───────────────────────


class ScmRepoOption(BaseModel):
    """Repozytorium dostępne dla tokenu — wybór przed podłączeniem (AC1)."""

    full_name: str
    name: str
    private: bool
    default_branch: str
    html_url: str
    clone_url: str
    connected: bool = False


class ConnectRepoRequest(BaseModel):
    """Podłączenie repozytorium GitHub — identyfikatorem jest ``owner/repo``."""

    model_config = ConfigDict(extra="ignore")

    full_name: str = Field(..., min_length=1, max_length=255)


class GitLabProjectOption(BaseModel):
    """Projekt GitLab dostępny dla tokenu (Story 8.2, AC1).

    GitLab adresuje projekty liczbą, więc obok ścieżki niesiemy ``id`` —
    bez niego nie da się wywołać API webhooków ani zmian MR.
    """

    project_id: int
    path_with_namespace: str
    name: str
    visibility: str
    default_branch: str
    web_url: str
    http_url_to_repo: str
    connected: bool = False


class ConnectGitLabProjectRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    project_id: int = Field(..., ge=1)


class ScmIntegrationResponse(BaseModel):
    """Podłączone repozytorium — bez tokenu i bez sekretu webhooka (AC1/AC6)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    repo_full_name: str
    repo_url: str
    default_branch: str
    project_id: uuid.UUID | None = None
    webhook_active: bool = False
    is_active: bool
    created_at: datetime
    # Adres instancji — istotny tylko dla GitLaba (self-hosted), dla GitHuba None.
    gitlab_url: str | None = None


class ScmIntegrationListResponse(BaseModel):
    items: list[ScmIntegrationResponse]
    total: int
    # Gdy false, frontend pokazuje komunikat zamiast przycisku „Połącz".
    provider_configured: bool = True


class IntegrationEventResponse(BaseModel):
    """Zdarzenie webhooka na liście ostatnich aktywności (AC6)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    action: str | None = None
    repo_full_name: str
    branch: str | None = None
    base_branch: str | None = None
    commit_sha: str | None = None
    pr_number: int | None = None
    status: str
    task_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class StatusCheckConfigRequest(BaseModel):
    """Konfiguracja status checków per integracja (Story 8.3, AC3/AC5/AC6)."""

    model_config = ConfigDict(extra="ignore")

    severity_threshold: Literal["critical", "high", "medium"] = "critical"
    # Komentarz z podsumowaniem pod PR/MR — domyślnie włączony (AC5).
    post_comment: bool = True
    # Gdy false, status zostaje zielony mimo znalezisk: zespół chce widzieć
    # liczby, ale nie blokować merge'a (AC3).
    fail_on_threshold: bool = True


class StatusCheckConfigResponse(BaseModel):
    integration_id: uuid.UUID
    severity_threshold: str
    post_comment: bool
    fail_on_threshold: bool
    # Nazwa do wpisania w regułach ochrony gałęzi (AC4).
    status_context: str


class WebhookAckResponse(BaseModel):
    """Potwierdzenie przyjęcia webhooka — GitHub loguje treść odpowiedzi."""

    received: bool = True
    status: str = "accepted"
    event_id: uuid.UUID | None = None
    task_id: str | None = None
    detail: str | None = None


# ── Epic 8, Story 8.4: generator konfiguracji CI/CD ─────────────────────────


class CicdTemplateInfo(BaseModel):
    """Opis platformy CI/CD dostępnej w generatorze (AC5/AC6)."""

    platform: str
    label: str
    filename: str
    language: str
    description: str
    # Jak dodać klucz API w danej platformie — treść różni się per CI.
    secret_hint: str


class CicdTemplateListResponse(BaseModel):
    platforms: list[CicdTemplateInfo]
    available_modules: list[str]
    available_engine_modes: list[str]
    available_thresholds: list[str]
    # Nazwa zmiennej/credentiala z kluczem — jedna dla wszystkich platform.
    api_key_variable: str


class CicdGenerateRequest(BaseModel):
    """Parametry generowanej konfiguracji (AC6)."""

    model_config = ConfigDict(extra="ignore")

    platform: Literal["jenkins", "github_actions", "azure_devops", "gitlab_ci"]
    severity_threshold: Literal["critical", "high", "medium"] = "critical"
    modules: list[str] = Field(default_factory=lambda: ["code_analysis"], min_length=1)
    engine_mode: Literal["native", "llm", "hybrid"] = "native"
    timeout_minutes: int = Field(default=30, ge=1, le=180)


class CicdGenerateResponse(BaseModel):
    platform: str
    filename: str
    language: str
    content: str
    secret_hint: str


class CicdSummaryResponse(BaseModel):
    """Werdykt bramki CI/CD dla projektu (AC1-AC4).

    ``should_fail`` jest policzone po stronie serwera, żeby skrypty w pipeline
    nie musiały powtarzać logiki progów — i żeby nie rozjechała się ona ze
    status checkami na PR (Story 8.3).
    """

    project_id: uuid.UUID
    threshold: str
    counts: dict[str, int]
    total: int
    blocking: int
    should_fail: bool
    state: str
    description: str
