import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin

# No FK on tenant_id — audit logs must retain tenant_id even after tenant deletion.
# No TimestampMixin — audit logs are immutable (updated_at not applicable).


class AuditEventType(StrEnum):
    """Types of audit events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"
    CONFIGURATION_CHANGE = "configuration_change"
    TEST_EXECUTION = "test_execution"
    PROJECT_ACCESS = "project_access"
    ADMIN_ACTION = "admin_action"


class AuditEvent(Base, UUIDMixin):
    """Audit event record for tracking system events."""
    __tablename__ = "audit_events"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    severity: Mapped[str] = mapped_column(String(20), default="info")
    details: Mapped[dict | None] = mapped_column(JSONB, default=None)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(500), default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        try:
            return f"<AuditEvent id={self.id} event_type={self.event_type} action={self.action}>"
        except Exception:
            return "<AuditEvent (detached)>"


class AuditLog(Base, UUIDMixin):
    __tablename__ = "audit_logs"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        index=True,
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    details: Mapped[dict | None] = mapped_column("changes", JSONB, default=None)
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        try:
            return f"<AuditLog id={self.id} action={self.action!r} user_id={self.user_id}>"
        except Exception:
            return "<AuditLog (detached)>"
