"""Integration models.

Epic 5 (5.8/5.9): konfiguracja trackerów (Jira, Azure DevOps) i logi synchronizacji;
poświadczenia szyfrowane Fernetem.

Epic 8 (8.1/8.2): podłączone repozytoria GitHub/GitLab (``scm_integrations``)
i zdarzenia z ich webhooków (``integration_events``); tokeny OAuth szyfrowane
AES-256-GCM pod kluczem wyprowadzonym z tenanta.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class IntegrationProvider(StrEnum):
    JIRA = "jira"
    AZURE_DEVOPS = "azure_devops"
    # Systemy zarządzania testami (Epic 8, Stories 8.8/8.9) — konfiguracja
    # per projekt, bo identyfikator projektu docelowego różni się między
    # projektami TestGEN.
    TESTRAIL = "testrail"
    XRAY = "xray"
    ZEPHYR = "zephyr"


class SyncStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class IntegrationConfig(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Configuration for an external integration (Jira / Azure DevOps)."""

    __tablename__ = "integration_configs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        Enum(IntegrationProvider, name="integration_provider", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        index=True,
    )
    base_url: Mapped[str] = mapped_column(String(500))
    # Encrypted credentials — Fernet token containing email:api_token
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    settings: Mapped[dict | None] = mapped_column(JSONB, default=None)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)


class IntegrationSyncLog(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Log entry for a single integration sync operation."""

    __tablename__ = "integration_sync_logs"

    integration_config_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_configs.id", ondelete="CASCADE"),
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    sync_type: Mapped[str] = mapped_column(String(50))  # gap_findings, recommendations
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        default=SyncStatus.PENDING,
    )
    items_total: Mapped[int] = mapped_column(Integer, default=0)
    items_synced: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[dict | None] = mapped_column(JSONB, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None,
    )


# ── Epic 8, Stories 8.1/8.2: integracje z hostingiem kodu (GitHub/GitLab) ────
#
# Odrębna tabela od ``integration_configs`` (Jira/ADO): tamte są per projekt
# i trzymają poświadczenia użytkownika, te są per repozytorium i noszą token
# OAuth, identyfikator webhooka po stronie dostawcy oraz jego sekret.


class ScmProvider(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"


class ScmEventType(StrEnum):
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    MERGE_REQUEST = "merge_request"


class ScmEventStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScmIntegration(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Podłączone repozytorium — token OAuth i webhook u dostawcy.

    ``repo_full_name`` jest unikalny w obrębie dostawcy globalnie, a nie per
    tenant: webhook przychodzi bez kontekstu tenanta i jedyne, co niesie, to
    nazwa repozytorium — dwa tenanty podłączające to samo repo dałyby
    niejednoznaczne trasowanie zdarzeń.
    """

    __tablename__ = "scm_integrations"
    __table_args__ = (
        UniqueConstraint("provider", "repo_full_name", name="uq_scm_integrations_provider_repo"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    # Projekt zasilany przez webhooki; tworzony leniwie przy pierwszym zdarzeniu.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    provider: Mapped[ScmProvider] = mapped_column(
        Enum(ScmProvider, name="scm_provider", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        index=True,
    )
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    repo_url: Mapped[str] = mapped_column(String(500))
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    # AES-256-GCM pod kluczem wyprowadzonym z tenanta (core.encryption).
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    # Identyfikator i sekret webhooka u dostawcy; None dopóki rejestracja
    # nie przejdzie (np. brak uprawnień admina do repo).
    hook_id: Mapped[str | None] = mapped_column(String(100), default=None)
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    config: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

    def __repr__(self) -> str:
        try:
            return f"<ScmIntegration {self.provider.value}:{self.repo_full_name}>"
        except Exception:
            return "<ScmIntegration (detached)>"


class IntegrationEvent(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Pojedyncze zdarzenie z webhooka — ślad audytowy i stan przetwarzania."""

    __tablename__ = "integration_events"

    integration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scm_integrations.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[ScmEventType] = mapped_column(
        Enum(ScmEventType, name="scm_event_type", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        index=True,
    )
    action: Mapped[str | None] = mapped_column(String(50), default=None)
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    branch: Mapped[str | None] = mapped_column(String(255), default=None)
    base_branch: Mapped[str | None] = mapped_column(String(255), default=None)
    commit_sha: Mapped[str | None] = mapped_column(String(40), default=None)
    pr_number: Mapped[int | None] = mapped_column(Integer, default=None)
    status: Mapped[ScmEventStatus] = mapped_column(
        Enum(ScmEventStatus, name="scm_event_status", native_enum=True,
             values_callable=lambda e: [m.value for m in e]),
        default=ScmEventStatus.PENDING,
        index=True,
    )
    task_id: Mapped[str | None] = mapped_column(String(255), default=None)
    # Surowy payload obcięty do istotnych pól — pełne body GitHuba bywa
    # wielomegabajtowe, a do diagnostyki wystarczy nagłówek zdarzenia.
    payload: Mapped[dict | None] = mapped_column(JSONB, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None,
    )

    def __repr__(self) -> str:
        try:
            return f"<IntegrationEvent {self.event_type.value} {self.repo_full_name} {self.status.value}>"
        except Exception:
            return "<IntegrationEvent (detached)>"
