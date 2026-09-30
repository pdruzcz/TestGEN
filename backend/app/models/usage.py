"""Per-tenant usage counters — Story 7.1.

Wymiary zgodne z zatwierdzoną macierzą 2026-08-28: bez ``users``
(unlimited) i bez ``api_requests`` (wymiar API calls/dzień usunięty).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CounterType(StrEnum):
    ANALYSES = "analyses"
    TEST_CASES = "test_cases"
    STORAGE_BYTES = "storage_bytes"
    FILES_PER_ANALYSIS = "files_per_analysis"


class UsageCounter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "usage_counters"
    __table_args__ = (Index("ix_usage_counters_tenant_type_period", "tenant_id", "counter_type", "period_start"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    counter_type: Mapped[CounterType] = mapped_column(
        Enum(
            CounterType,
            name="usage_counter_type",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
    )
    # BIGINT, nie INTEGER: limity planów w bajtach (10 GiB = 10 737 418 240)
    # i skumulowane zużycie storage nie mieszczą się w int32 (max ~2,1 mld) —
    # INSERT licznika storage kończył się „value out of int32 range" (2026-09-29).
    value: Mapped[int] = mapped_column(BigInteger, default=0)
    limit_value: Mapped[int] = mapped_column(BigInteger)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        try:
            return f"<UsageCounter tenant={self.tenant_id} type={self.counter_type.value} value={self.value}>"
        except Exception:
            return "<UsageCounter (detached)>"
