"""Tenant subscription — Story 7.1 + 7.2 (metoda płatności, dunning).

Subskrypcja jest własna (nasza), nie dostawcy płatności — brak pól
``stripe_*`` (D2, plan-integracji-tpay.md). tpay obsługuje pojedyncze
płatności/odnowienia (7.2/7.4); harmonogram odnowień trzyma
``next_charge_at`` (SubscriptionScheduler, 7.2). Dunning (7.2 AC6):
``dunning_attempt``/``dunning_next_retry_at`` liczą ponowienia D+1/D+3/D+5,
po 3 porażkach downgrade do Freemium z 7-dniowym grace (``grace_until``,
``previous_plan_id`` — limity planu płatnego utrzymane przez grace, CR#2).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


class Subscription(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            name="subscription_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=SubscriptionStatus.ACTIVE,
    )
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_charge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, index=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # --- Story 7.2: aktywna metoda płatności + stan dunningu (AC1/AC5/AC6) ---
    # Aktywna metoda odnowień (PaymentToken); SET NULL po usunięciu tokena.
    payment_token_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payment_tokens.id", ondelete="SET NULL"),
        default=None,
    )
    # Dunning: liczba nieudanych PONOWIEŃ (D+1/D+3/D+5); 3 → downgrade (AC6).
    dunning_attempt: Mapped[int] = mapped_column(default=0)
    dunning_next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Po downgrade: grace na limicie planu, który był (previous_plan_id).
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    previous_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        default=None,
    )

    def __repr__(self) -> str:
        try:
            return f"<Subscription id={self.id} tenant={self.tenant_id} status={self.status.value}>"
        except Exception:
            return "<Subscription (detached)>"
