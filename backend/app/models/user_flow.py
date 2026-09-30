"""User flow models — Epic 3, Story 3.7: cross-diagram analysis.

Reconstructed end-to-end user flows built by ``CrossDiagramAnalyzer`` from the
parsed UML diagrams of a project (and, later, GUI analyses). Each ``UserFlow``
owns an ordered list of ``FlowStep`` rows. Tenant scope is enforced at the DB
level via RLS, analogous to ``UMLDiagram``.
"""

import uuid
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class FlowSourceType(StrEnum):
    """Origin of a reconstructed user flow."""

    UML = "uml"
    GUI = "gui"
    UML_AND_GUI = "uml_and_gui"


class FlowStatus(StrEnum):
    """Lifecycle status of a reconstructed user flow."""

    DRAFT = "draft"
    VALIDATED = "validated"
    TESTS_GENERATED = "tests_generated"


def _enum_col(enum_cls: type[StrEnum], name: str):
    return Enum(enum_cls, name=name, native_enum=True, values_callable=lambda e: [m.value for m in e])


class UserFlow(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "user_flows"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    source_type: Mapped[FlowSourceType] = mapped_column(
        _enum_col(FlowSourceType, "flow_source_type"),
        default=FlowSourceType.UML,
        index=True,
    )
    source_ids: Mapped[list | None] = mapped_column(JSONB, default=None)
    name: Mapped[str] = mapped_column(String(500))
    steps: Mapped[list | None] = mapped_column(JSONB, default=None)
    status: Mapped[FlowStatus] = mapped_column(
        _enum_col(FlowStatus, "flow_status"),
        default=FlowStatus.DRAFT,
        index=True,
    )
    warnings: Mapped[list | None] = mapped_column(JSONB, default=None)

    flow_steps = relationship(
        "FlowStep",
        back_populates="flow",
        cascade="all, delete-orphan",
        order_by="FlowStep.sequence",
        lazy="raise",
    )

    def __repr__(self) -> str:
        try:
            return f"<UserFlow id={self.id} name={self.name!r} status={self.status.value}>"
        except Exception:
            return "<UserFlow (detached)>"


class FlowStep(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "flow_steps"

    flow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_flows.id", ondelete="CASCADE"),
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    action: Mapped[str] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(String(255), default=None)
    target_element: Mapped[str | None] = mapped_column(String(500), default=None)
    expected_result: Mapped[str | None] = mapped_column(Text, default=None)
    source_diagram_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("uml_diagrams.id", ondelete="SET NULL"),
        default=None,
    )
    source_screenshot_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    source: Mapped[str] = mapped_column(String(20), default="native")
    # UML relation / decision metadata (Story 3-11-domknięcie, AC1): relation_type
    # (include/extend/none), parameters (for Scenario Outline Examples) and
    # branch_label (activity decision branch). Attribute is aliased to ``meta``
    # because ``metadata`` is reserved on the declarative base (``MetaData``).
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)

    flow = relationship("UserFlow", back_populates="flow_steps", lazy="raise")

    def __repr__(self) -> str:
        try:
            return f"<FlowStep flow={self.flow_id} seq={self.sequence} action={self.action!r}>"
        except Exception:
            return "<FlowStep (detached)>"
