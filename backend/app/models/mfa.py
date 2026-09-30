"""MFA (TOTP) model for optional two-factor authentication."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserMFA(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_mfa"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    totp_secret: Mapped[str] = mapped_column(String(255))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_codes_hash: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    user = relationship("User", backref="mfa", lazy="raise", uselist=False)
