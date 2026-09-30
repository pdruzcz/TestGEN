"""Daily snapshoty zużycia per tenant — Story 7.9 (AC3).

``UsageHistory`` zapisuje raz na dobę wartość każdego licznika
(``UsageCounter``) — jedno źródło danych wykresu historii zużycia (AC3)
i prognozy (AC4). Wymiary bez ``users`` (unlimited, CR#2 2026-08-28).
"""

import uuid
from datetime import date

from sqlalchemy import BigInteger, Date, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.usage import CounterType


class UsageHistory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "usage_history"
    __table_args__ = (
        # Jeden snapshot per tenant per counter_type per dzień (Task 1.2) —
        # idempotencja tasku Celery (Task 2) i unikalność danych wykresu.
        UniqueConstraint("tenant_id", "counter_type", "snapshot_date", name="uq_usage_history_tenant_type_date"),
    )

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
    # BIGINT: snapshot ``storage_bytes`` to skumulowane bajty — int32 kończy
    # się przy ~2 GiB (patrz migracja 059).
    value: Mapped[int] = mapped_column(BigInteger, default=0)
    snapshot_date: Mapped[date] = mapped_column(Date)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)

    def __repr__(self) -> str:
        try:
            return (
                f"<UsageHistory tenant={self.tenant_id} type={self.counter_type.value} "
                f"value={self.value} date={self.snapshot_date}>"
            )
        except Exception:
            return "<UsageHistory (detached)>"
