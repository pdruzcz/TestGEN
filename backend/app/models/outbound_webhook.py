"""Webhooki wychodzące TestGEN — Epic 8, Story 8.7.

Odwrotność ``scm_integrations`` (8.1/8.2): tam my odbieramy zdarzenia od
GitHuba i GitLaba, tu my je wysyłamy do systemów klienta.

Sekret jest szyfrowany tym samym mechanizmem co tokeny OAuth (AES-256-GCM
pod kluczem wyprowadzonym z tenanta) i nigdy nie wraca w odpowiedzi API —
służy wyłącznie do podpisania payloadu, więc odbiorca ma go u siebie.

Każda próba dostarczenia jest osobnym wierszem ``webhook_deliveries``:
historia prób jest tym, po czym klient diagnozuje własny endpoint, więc
nadpisywanie jednego rekordu zacierałoby dokładnie tę informację.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class WebhookEventType(StrEnum):
    ANALYSIS_COMPLETED = "analysis.completed"
    SECURITY_FINDING = "security.finding"
    GAP_DETECTED = "gap.detected"
    EXPORT_READY = "export.ready"
    SUBSCRIPTION_CHANGED = "subscription.changed"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class OutboundWebhook(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Endpoint klienta subskrybujący wybrane zdarzenia."""

    __tablename__ = "outbound_webhooks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048))
    # AES-256-GCM pod kluczem tenanta (core.encryption) — jak tokeny OAuth.
    secret_encrypted: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(200), default=None)
    # Lista typów zdarzeń jako tekst: walidację robi kontrakt Pydantic, a
    # tablica enumów w Postgresie utrudniłaby dokładanie nowych typów.
    events: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    last_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_delivery_status: Mapped[DeliveryStatus | None] = mapped_column(
        Enum(
            DeliveryStatus,
            name="webhook_delivery_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=None,
    )

    def subscribes_to(self, event_type: str) -> bool:
        return self.is_active and event_type in (self.events or [])

    def __repr__(self) -> str:
        try:
            return f"<OutboundWebhook {self.url[:60]} events={len(self.events or [])}>"
        except Exception:
            return "<OutboundWebhook (detached)>"


class WebhookDelivery(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Pojedyncza próba dostarczenia zdarzenia pod adres klienta."""

    __tablename__ = "webhook_deliveries"

    webhook_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("outbound_webhooks.id", ondelete="CASCADE"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    response_status: Mapped[int | None] = mapped_column(Integer, default=None)
    # Ciało odpowiedzi przycięte do 1 KB — klient potrzebuje go do diagnozy,
    # ale pełna odpowiedź potrafi być megabajtem HTML-a z proxy.
    response_body: Mapped[str | None] = mapped_column(String(1024), default=None)
    error_message: Mapped[str | None] = mapped_column(String(500), default=None)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(
            DeliveryStatus,
            name="webhook_delivery_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=DeliveryStatus.PENDING,
        index=True,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )

    def __repr__(self) -> str:
        try:
            return f"<WebhookDelivery {self.event_type} próba={self.attempt_number} {self.status.value}>"
        except Exception:
            return "<WebhookDelivery (detached)>"
