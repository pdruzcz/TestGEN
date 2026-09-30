import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class TenantRole(StrEnum):
    USER = "user"
    OWNER = "owner"


class UserTenant(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_tenants"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_user_tenants_user_tenant"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[TenantRole] = mapped_column(
        Enum(TenantRole, name="tenant_role", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        default=TenantRole.USER,
    )
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        default=None,
    )

    def __repr__(self) -> str:
        try:
            return f"<UserTenant user_id={self.user_id} tenant_id={self.tenant_id} role={self.role.value}>"
        except Exception:
            return "<UserTenant (detached)>"
