"""Powiadomienia in-app — Story 7.11 (AC4).

Model generyczny: ``type`` rozszerzalny poza ``limit_warning`` (progowe
ostrzeżenia zużycia) o ``payment_failed``/``subscription_changed``/
``invoice_ready`` (przyszłe story). Deduplikacja progów — unique
``(tenant_id, type, resource_type, threshold_percentage, billing_period)``:
jedno powiadomienie o danym progu danego zasobu per okres rozliczeniowy
(AC1 „każdy próg tylko RAZ per okres").

``billing_period`` = "YYYY-MM" (okno miesięczne liczników, 7.8).
Atrybut ``meta`` mapowany na kolumnę ``metadata`` — nazwa zarezerwowana
dla SQLAlchemy DeclarativeBase.
"""

import uuid
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class NotificationType(StrEnum):
    LIMIT_WARNING = "limit_warning"
    PAYMENT_FAILED = "payment_failed"
    SUBSCRIPTION_CHANGED = "subscription_changed"
    INVOICE_READY = "invoice_ready"


class NotificationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Notification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        # AC1/AC4: idempotentność progów — NULL-e (typy nieprogowe) nie deduplikują
        # (PostgreSQL traktuje NULL jako różne w unique constraint).
        UniqueConstraint(
            "tenant_id",
            "type",
            "resource_type",
            "threshold_percentage",
            "billing_period",
            name="uq_notifications_dedup",
        ),
        # Szybkie zapytanie o nieprzeczytane (Task 1.3).
        Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
    )
    severity: Mapped[NotificationSeverity] = mapped_column(
        Enum(
            NotificationSeverity,
            name="notification_severity",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
    )
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(String(2000))
    # Dla limit_warning: typ zasobu z CounterType.value (analyses/test_cases/storage_bytes).
    resource_type: Mapped[str | None] = mapped_column(String(100), default=None)
    # BIGINT: dla storage_bytes przenoszą bajty (limit 10 GiB nie mieści się
    # w int32) — patrz migracja 059 i usage_counters.
    current_value: Mapped[int | None] = mapped_column(BigInteger, default=None)
    limit_value: Mapped[int | None] = mapped_column(BigInteger, default=None)
    percentage: Mapped[int | None] = mapped_column(default=None)
    # Klucz deduplikacji (wariant progu: 80/90/100) — tylko limit_warning.
    threshold_percentage: Mapped[int | None] = mapped_column(default=None)
    billing_period: Mapped[str | None] = mapped_column(String(7), default=None)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    cta_url: Mapped[str | None] = mapped_column(String(500), default=None)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)

    def __repr__(self) -> str:
        try:
            return f"<Notification user={self.user_id} type={self.type.value} is_read={self.is_read}>"
        except Exception:
            return "<Notification (detached)>"
