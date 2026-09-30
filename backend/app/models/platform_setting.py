"""Globalna konfiguracja platformy — Epic 6, Story 6.15.

Jeden wiersz na sekcję konfiguracji (``limits``, ``llm``, ``maintenance``,
``feature_flags``).  Tabela jest globalna — nie ma ``tenant_id`` ani RLS,
ponieważ dotyczy całej instalacji i jest dostępna wyłącznie dla administratora.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        try:
            return f"<PlatformSetting key={self.key!r}>"
        except Exception:
            return "<PlatformSetting (detached)>"
