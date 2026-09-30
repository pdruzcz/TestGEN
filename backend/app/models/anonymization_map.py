"""Anonymization mapping model — Epic 1, Story 1.54 (FR72).

One row per anonymization run: the placeholder → original mapping used to
detokenize LLM output.  The mapping is stored **encrypted** (AES-256-GCM,
per-tenant key derived from the master encryption key) and never leaves the
tenant boundary — in particular it is never sent to the LLM provider.
Tenant isolation via RLS, analogous to ``healing_reports`` / ``gap_findings``.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class AnonymizationMap(Base, UUIDMixin, TenantMixin, TimestampMixin):
    """Encrypted placeholder→original mapping for one anonymization run."""

    __tablename__ = "anonymization_maps"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
    )
    # NULL for gateway-level runs that are not tied to a single analysis.
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="CASCADE"),
        index=True,
        default=None,
    )
    # AES-256-GCM ciphertext of the JSON mapping {"<PLACEHOLDER>": "original"}.
    encrypted_map: Mapped[bytes] = mapped_column(LargeBinary)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    # Counts only — never the secret values themselves (RODO, FR72).
    secret_count: Mapped[int] = mapped_column(Integer, default=0)
    # Retention consistent with Story 1.49 (immediate Basic / 24h Professional).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        try:
            return (
                f"<AnonymizationMap id={self.id} project_id={self.project_id} "
                f"tokens={self.token_count} secrets={self.secret_count}>"
            )
        except Exception:
            return "<AnonymizationMap (detached)>"
