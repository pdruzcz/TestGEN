"""Dane fakturowe tenanta — Story 7.6 (AC4).

``InvoiceData`` — firma do faktury: nazwa, NIP, adres (ulica, miasto,
kod pocztowy, kraj). Edytowalne przez Ownera (PUT /billing/invoice-data);
``Invoice`` robi z nich snapshot przy wystawieniu, więc późniejsze zmiany
nie dotykają już wystawionych faktur.
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class InvoiceData(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "invoice_data"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(String(255))
    nip: Mapped[str | None] = mapped_column(String(20), default=None)
    # {street, city, postal_code, country} (AC4).
    address: Mapped[dict] = mapped_column(JSONB, default=dict)

    def __repr__(self) -> str:
        try:
            return f"<InvoiceData id={self.id} tenant={self.tenant_id} company={self.company_name!r}>"
        except Exception:
            return "<InvoiceData (detached)>"
