"""PlanChangeHistory — historia zmian planu subskrypcji (Story 7.5, AC4).

Każda zmiana planu (upgrade natychmiastowy / downgrade na koniec okresu)
zostawia rekord audytowy: kto, kiedy, z jakiego na jaki plan, z jakim
statusem (pending → completed | canceled). ``proration_details`` (JSONB)
przechowuje lokalne wyliczenie proration (D2 — liczymy sami, tpay nie ma
odpowiednika ``proration_behavior``): kwota, dni okresu, pozostałe dni,
ceny użyte do wyliczenia — dla audytu i wsparcia.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.subscription_plan import PlanName


class PlanChangeType(StrEnum):
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"


class PlanChangeStatus(StrEnum):
    """pending — zaplanowana (downgrade) lub czeka na płatność (upgrade);
    completed — zrealizowana; canceled — cofnięta / płatność nieudana."""

    PENDING = "pending"
    COMPLETED = "completed"
    CANCELED = "canceled"


def _plan_enum() -> Enum:
    """Współdzielony natywny enum planów (typ ``subscription_plan_name`` z 042)."""
    return Enum(
        PlanName,
        name="subscription_plan_name",
        native_enum=True,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


class PlanChangeHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "plan_change_history"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    from_plan: Mapped[PlanName] = mapped_column(_plan_enum())
    to_plan: Mapped[PlanName] = mapped_column(_plan_enum())
    change_type: Mapped[PlanChangeType] = mapped_column(
        Enum(
            PlanChangeType,
            name="plan_change_type",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
    )
    # Moment wejścia zmiany w życie: upgrade — chwila opłacenia; downgrade —
    # koniec bieżącego okresu (planowany), po egzekucji faktyczna data.
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )
    status: Mapped[PlanChangeStatus] = mapped_column(
        Enum(
            PlanChangeStatus,
            name="plan_change_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=PlanChangeStatus.PENDING,
    )
    # Lokalne wyliczenie proration (AC4): amount, period_days, remaining_days,
    # ceny użyte do wyliczenia — audyt i wsparcie.
    proration_details: Mapped[dict] = mapped_column(JSONB, default=dict)

    def __repr__(self) -> str:
        try:
            return (
                f"<PlanChangeHistory id={self.id} {self.from_plan.value}->{self.to_plan.value} "
                f"{self.change_type.value} status={self.status.value}>"
            )
        except Exception:
            return "<PlanChangeHistory (detached)>"
