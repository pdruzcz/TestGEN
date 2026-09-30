"""Faktura VAT — Story 7.6 (AC1, AC2, AC5, AC6).

``Invoice`` — automatycznie generowana po płatności (FR57). Rekord jest
snapshotem danych sprzedawcy i nabywcy z chwili wystawienia (AC4: zmiana
danych fakturowych nie modyfikuje już wystawionych faktur — nic nie jest
derywowane z ``tenants``/``invoice_data`` po zapisie).

Numeracja sekwencyjna (AC6): ``FV/{rok}/{miesiąc}/{numer_w_miesiącu}``,
globalna per sprzedawca (TestGEN), z unikalnym ``(year, month,
sequential_number)`` jako twardą gwarancją braku duplikatów przy
współbieżności (backstop dla locka z InvoiceService).

PDF (AC2): renderowany asynchronicznie (Celery), ``pdf_path`` to klucz
obiektu w MinIO ``invoices/{tenant_id}/{year}/{month}/{numer}.pdf``.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class InvoiceStatus(StrEnum):
    ISSUED = "issued"
    CANCELED = "canceled"
    # Faktury korygujące — scope przyszły, model przygotowany (Dev Notes).
    CORRECTED = "corrected"


class InvoicePaymentMethod(StrEnum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    BLIK = "blik"


class Invoice(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        # AC6: sekwencja numerów per (rok, miesiąc) — hard gwarancja unikalności.
        UniqueConstraint("year", "month", "sequential_number", name="uq_invoices_year_month_seq"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
    )
    # Pełny numer "FV/2026/06/0001" — unique; słupki rozbite na year/month/
    # sequential_number umożliwiają sekwencyjne numerowanie (MAX+1, AC6).
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    year: Mapped[int] = mapped_column()
    month: Mapped[int] = mapped_column()
    sequential_number: Mapped[int] = mapped_column()
    issue_date: Mapped[date] = mapped_column(Date)
    sale_date: Mapped[date] = mapped_column(Date)
    # Snapshot sprzedawcy (TestGEN) z configu w chwili wystawienia (AC1).
    seller_name: Mapped[str] = mapped_column(String(255))
    seller_nip: Mapped[str] = mapped_column(String(20))
    seller_krs: Mapped[str | None] = mapped_column(String(20), default=None)
    seller_regon: Mapped[str | None] = mapped_column(String(20), default=None)
    seller_address: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Snapshot nabywcy z invoice_data tenanta (AC1/AC4).
    buyer_name: Mapped[str] = mapped_column(String(255))
    buyer_nip: Mapped[str | None] = mapped_column(String(20), default=None)
    buyer_address: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Pozycje: [{name, period, net, vat_rate, gross}] (AC1).
    items: Mapped[list] = mapped_column(JSONB, default=list)
    subtotal_net: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("23"))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total_gross: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="PLN")
    payment_method: Mapped[InvoicePaymentMethod] = mapped_column(
        Enum(
            InvoicePaymentMethod,
            name="invoice_payment_method",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=InvoicePaymentMethod.CARD,
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payment_transactions.id", ondelete="SET NULL"),
        default=None,
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(
            InvoiceStatus,
            name="invoice_status",
            native_enum=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=InvoiceStatus.ISSUED,
    )
    # AC2: klucz obiektu w MinIO; uzupełniane asynchronicznie przez Celery.
    pdf_path: Mapped[str | None] = mapped_column(String(500), default=None)
    pdf_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    @property
    def pdf_available(self) -> bool:
        """AC5: czy PDF jest już wygenerowany (asynchronicznie z Celery)."""
        return self.pdf_path is not None

    def __repr__(self) -> str:
        try:
            return (
                f"<Invoice id={self.id} number={self.invoice_number} "
                f"status={self.status.value} total={self.total_gross}>"
            )
        except Exception:
            return "<Invoice (detached)>"
