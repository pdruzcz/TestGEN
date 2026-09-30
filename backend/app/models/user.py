from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255), default="")
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=False)
    # Odwracalna blokada nałożona przez administratora platformy (Story 6.15).
    is_blocked: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Miękkie usunięcie konta — rekord zostaje dla integralności logu audytu.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    notification_preferences: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    def __repr__(self) -> str:
        try:
            return f"<User id={self.id} email={self.email!r} is_admin={self.is_admin}>"
        except Exception:
            return "<User (detached)>"
