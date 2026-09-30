import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class VerificationType(StrEnum):
    REGISTRATION = "registration"
    INVITATION = "invitation"
    PASSWORD_RESET = "password_reset"


class EmailVerification(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_verifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    token: Mapped[str] = mapped_column(String(64), unique=True)
    type: Mapped[VerificationType] = mapped_column(
        Enum(
            VerificationType, name="verification_type", native_enum=True, values_callable=lambda e: [m.value for m in e]
        ),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    def __repr__(self) -> str:
        try:
            return f"<EmailVerification id={self.id} type={self.type.value} user_id={self.user_id}>"
        except Exception:
            return "<EmailVerification (detached)>"
