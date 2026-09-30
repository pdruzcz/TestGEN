"""Gherkin/BDD feature model — Epic 3, Story 3.11.

Persists a generated Gherkin ``.feature`` derived from a reconstructed
``UserFlow`` (UML and/or GUI): the structured scenarios, the rendered raw
feature text, the engine mode used and any (non-blocking) validation warnings.
Tenant scope is enforced at the DB level via RLS, analogous to ``user_flows``.
"""

import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin
from app.models.user_flow import _enum_col


class GherkinStatus(StrEnum):
    """Lifecycle status of a generated Gherkin feature."""

    GENERATED = "generated"
    VALIDATED = "validated"
    APPROVED = "approved"


class GherkinFeature(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "gherkin_features"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    source_flow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_flows.id", ondelete="SET NULL"),
        default=None,
        index=True,
    )
    feature_name: Mapped[str] = mapped_column(String(500))
    feature_description: Mapped[str | None] = mapped_column(Text, default=None)
    scenarios: Mapped[list | None] = mapped_column(JSONB, default=None)
    raw_feature: Mapped[str] = mapped_column(Text, default="")
    engine_mode: Mapped[str] = mapped_column(String(20), default="native")
    validation_warnings: Mapped[list | None] = mapped_column(JSONB, default=None)
    status: Mapped[GherkinStatus] = mapped_column(
        _enum_col(GherkinStatus, "gherkin_status"),
        default=GherkinStatus.GENERATED,
        index=True,
    )

    def __repr__(self) -> str:
        try:
            return f"<GherkinFeature id={self.id} name={self.feature_name!r} status={self.status.value}>"
        except Exception:
            return "<GherkinFeature (detached)>"
