"""Subscription plan definitions — Story 7.1 (3-plan model, CR#2 2026-08-28).

Freemium (0 PLN) / Basic (30 PLN/mies.) / Premium (50 PLN/mies.),
wyłącznie cykl miesięczny. Limits live in ``features`` JSONB — single
source of truth for QuotaService. No provider fields (tpay has no
price_id concept — D1, plan-integracji-tpay.md).
"""

from decimal import Decimal

from sqlalchemy import Boolean, Enum, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.tenant import PlanType

# Jeden enum planów w całym kodzie (7.1/2b.1) — PlanName to alias PlanType.
PlanName = PlanType


class SubscriptionPlan(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subscription_plans"

    name: Mapped[PlanName] = mapped_column(
        Enum(PlanName, name="subscription_plan_name", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        unique=True,
    )
    display_name: Mapped[str] = mapped_column(String(100))
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    features: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        try:
            return f"<SubscriptionPlan id={self.id} name={self.name.value} price={self.price_monthly}>"
        except Exception:
            return "<SubscriptionPlan (detached)>"
