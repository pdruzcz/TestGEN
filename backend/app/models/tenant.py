from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class PlanType(StrEnum):
    """Model 3-planowy (CR#2 2026-08-28): Freemium 0 / Basic 30 / Premium 50 PLN/mies.

    Kanoniczny enum planów w całym kodzie (SQLAlchemy, Pydantic, FE TS).
    Alias ``PlanName`` (subscription_plan.py) wskazuje na tę klasę.
    """

    FREEMIUM = "freemium"
    BASIC = "basic"
    PREMIUM = "premium"


class Tenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    nip: Mapped[str | None] = mapped_column(String(20), unique=True, default=None)
    plan: Mapped[PlanType] = mapped_column(
        Enum(PlanType, name="plan_type", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        default=PlanType.FREEMIUM,
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    settings: Mapped[dict | None] = mapped_column(JSONB, default=None)

    users = relationship(
        "User",
        secondary="user_tenants",
        primaryjoin="Tenant.id == foreign(UserTenant.tenant_id)",
        secondaryjoin="User.id == foreign(UserTenant.user_id)",
        backref="tenants",
        lazy="raise",
        viewonly=True,
    )
    projects = relationship("Project", back_populates="tenant", lazy="raise", viewonly=True)

    def __repr__(self) -> str:
        try:
            return f"<Tenant id={self.id} name={self.name!r} plan={self.plan.value}>"
        except Exception:
            return "<Tenant (detached)>"
