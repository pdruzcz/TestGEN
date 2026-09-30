"""Klucze API do automatyzacji — Epic 8, Story 8.6.

Klucz ma postać ``tgn_`` + 64 znaki hex i jest pokazywany użytkownikowi
**tylko raz**, przy utworzeniu. W bazie trzymamy wyłącznie SHA-256 hash
(AC1) — klucze API nie są hasłami, więc Argon2id byłby tu zbędnym kosztem
przy każdym requeście. ``key_prefix`` (pierwsze 8 znaków) służy do
rozpoznania klucza na liście.

Stan klucza jest pochodną dwóch pól: ``revoked_at`` (odwołanie ręczne,
soft delete) i ``expires_at`` (wygaśnięcie). Właściwość ``status`` łączy
je w jedną etykietę dla UI, a ``is_active`` rozstrzyga dostęp (AC4).
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ApiKeyScope(StrEnum):
    READ_ONLY = "read_only"
    FULL_ACCESS = "full_access"


class ApiKeyStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ApiKey(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Klucz API tenanta — uwierzytelnianie bezhasłowe dla CI/CD i skryptów."""

    __tablename__ = "api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    # Pierwsze 8 znaków klucza (``tgn_`` + 4 hex) — identyfikacja na liście.
    key_prefix: Mapped[str] = mapped_column(String(8))
    # SHA-256 pełnego klucza, hex — jedyna forma klucza w bazie.
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    scope: Mapped[ApiKeyScope] = mapped_column(
        Enum(
            ApiKeyScope,
            name="api_key_scope",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ApiKeyScope.READ_ONLY,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        expires_at = self.expires_at
        if expires_at.tzinfo is None:  # kolumna TIMESTAMPTZ, ale SQLite w testach oddaje naive
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at <= datetime.now(UTC)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and not self.is_expired

    @property
    def status(self) -> ApiKeyStatus:
        if self.revoked_at is not None:
            return ApiKeyStatus.REVOKED
        if self.is_expired:
            return ApiKeyStatus.EXPIRED
        return ApiKeyStatus.ACTIVE

    def __repr__(self) -> str:
        try:
            return f"<ApiKey {self.key_prefix}… name={self.name!r} scope={self.scope.value}>"
        except Exception:
            return "<ApiKey (detached)>"
