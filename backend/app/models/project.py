"""Project model for project management (CRUD, tenant-scoped)."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ProjectStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("name", "tenant_id", name="uq_projects_name_tenant"),)

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    language_hint: Mapped[str | None] = mapped_column(String(50), default=None)
    language: Mapped[str | None] = mapped_column(String(50), default=None)
    framework: Mapped[str | None] = mapped_column(String(100), default=None)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            name="project_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ProjectStatus.CREATED,
    )
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )

    tenant = relationship("Tenant", lazy="raise")

    def __repr__(self) -> str:
        try:
            return f"<Project id={self.id} name={self.name!r} status={self.status.value}>"
        except Exception:
            return "<Project (detached)>"
