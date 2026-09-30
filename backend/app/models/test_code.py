"""TestCode model — generated test code for a test case."""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class TestCode(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "test_codes"

    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        index=True,
    )
    framework: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(50))
    code: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(1000), default=None)
    # Story 3-13-domknięcie: patterny SikuliX wycięte bbox→PNG
    # (``[{"name": "button_login.png", "storage_key": "...", "component_id": "..."}]``).
    pattern_images: Mapped[list | None] = mapped_column(JSONB, default=None)

    test_case = relationship("TestCase", lazy="raise")

    def __repr__(self) -> str:
        try:
            return f"<TestCode id={self.id} framework={self.framework!r} language={self.language!r}>"
        except Exception:
            return "<TestCode (detached)>"
