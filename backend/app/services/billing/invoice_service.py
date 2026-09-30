"""InvoiceService — faktury VAT, Story 7.6 (AC1-AC6).

Generowanie po udanej płatności (wywołanie z WebhookProcessor.mark_paid,
AC1), numeracja sekwencyjna ``FV/{rok}/{miesiąc}/{numer}`` (AC6), PDF
asynchronicznie z Celery → MinIO (AC2) → email z załącznikiem do Ownera
(AC3). Lista i pobieranie faktur (AC5) + dane fakturowe tenanta (AC4).

Kluczowe decyzje:

- **Snapshot, nie referencja** — Invoice kopiuje dane sprzedawcy (config)
  i nabywcy (``invoice_data``) w chwili wystawienia; zmiana danych nie
  modyfikuje wystawionych faktur (AC4).
- **Idempotencja po ``payment_id``** — ponowienia webhooka/replay/
  reconciliation nie dublują faktury.
- **Numeracja (AC6)** — ``SELECT sequential_number ... ORDER BY DESC LIMIT 1
  ... FOR UPDATE`` na wierszach miesiąca + unique ``(year, month,
  sequential_number)`` (bez agregatu — ``max``+``FOR UPDATE`` to nieważny
  SQL w PG);
  wyścig na PIERWSZY numer miesiąca (brak wierszy do zablokowania)
  łapie constraint → retry na savepoincie (``begin_nested``), bez
  rollbacku zewnętrznej transakcji webhooka.
- **Gross→net** — tpay pobiera kwotę brutto; netto = brutto / 1.23
  (ROUND_HALF_UP), VAT = brutto - netto.
"""

import asyncio
import logging
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.config_billing import get_billing_settings
from app.core.exceptions import NotFoundError
from app.models.invoice import Invoice, InvoicePaymentMethod, InvoiceStatus
from app.models.invoice_data import InvoiceData
from app.models.payment import PaymentTransaction
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant import TenantRole, UserTenant

logger = logging.getLogger(__name__)

# Bucket dedykowany (wzorzec testgen-files/testgen-exports) — faktury to
# dokumenty księgowe: ZERO lifecycle (wygasanie tylko w testgen-exports).
INVOICES_BUCKET = "testgen-invoices"

VAT_RATE = Decimal("23")
_VAT_DIVISOR = Decimal("1.23")
_CENT = Decimal("0.01")

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "invoice"

_PAYMENT_METHOD_DISPLAY = {
    InvoicePaymentMethod.CARD: "Karta płatnicza",
    InvoicePaymentMethod.BANK_TRANSFER: "Przelew bankowy",
    InvoicePaymentMethod.BLIK: "BLIK",
}

# Retry numeracji po IntegrityError (wyścig na pierwszy numer miesiąca, AC6).
_NUMBERING_ATTEMPTS = 3

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def format_pln(value: Decimal | str) -> str:
    """``Decimal("30.00")`` → ``"30,00"`` (polski separator, bez grupowań)."""
    return f"{Decimal(str(value)):.2f}".replace(".", ",")


def split_vat(gross: Decimal) -> tuple[Decimal, Decimal]:
    """Kwota brutto → ``(netto, vat)``; 23%, ROUND_HALF_UP na groszach."""
    net = (gross / _VAT_DIVISOR).quantize(_CENT, rounding=ROUND_HALF_UP)
    return net, (gross - net).quantize(_CENT, rounding=ROUND_HALF_UP)


def seller_snapshot() -> dict:
    """Dane sprzedawcy (TestGEN) z configu — snapshot do faktury (AC1)."""
    billing = get_billing_settings()
    address = {**billing.invoice_seller_address}
    return {
        "name": billing.invoice_seller_name,
        "nip": billing.invoice_seller_nip,
        "krs": billing.invoice_seller_krs,
        "regon": billing.invoice_seller_regon,
        "address": address,
    }


def invoice_pdf_object_name(tenant_id: uuid.UUID, year: int, month: int, invoice_number: str) -> str:
    """Klucz obiektu w MinIO (AC2): ``{tenant_id}/{year}/{month}/{numer}.pdf``
    w buckecie ``testgen-invoices`` (prefiks bucketa z AC to przestrzeń
    ``invoices/`` platformy)."""
    return f"{tenant_id}/{year}/{month:02d}/{invoice_number}.pdf"


class InvoiceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # --- AC1/AC6: generowanie po płatności ---

    async def generate_invoice(
        self,
        tenant_id: uuid.UUID,
        txn: PaymentTransaction,
        *,
        payment_method: InvoicePaymentMethod = InvoicePaymentMethod.CARD,
    ) -> Invoice:
        """Faktura za opłaconą transakcję. Idempotentna po ``payment_id``."""
        existing = await self._invoice_for_payment(txn.id)
        if existing is not None:
            logger.info("Faktura dla transakcji %s już istnieje (%s) — pomijam", txn.id, existing.invoice_number)
            return existing

        seller = seller_snapshot()
        buyer = await self._buyer_snapshot(tenant_id)
        gross = txn.paid_amount if txn.paid_amount is not None else txn.amount
        net, vat = split_vat(gross)

        now = datetime.now(UTC)
        year, month = now.year, now.month
        issue_date = sale_date = now.date()

        items = [
            {
                "name": self._item_name(txn),
                "plan_display": self._plan_display(txn),
                "period": await self._period_description(tenant_id, txn, issue_date),
                # Kwoty jako str — JSONB nie trzyma Decimal; precyzja zachowana.
                "net": str(net),
                "vat_rate": str(VAT_RATE),
                "vat_amount": str(vat),
                "gross": str(gross),
            }
        ]

        for attempt in range(1, _NUMBERING_ATTEMPTS + 1):
            seq = await self._get_next_invoice_number(year, month)
            invoice = Invoice(
                tenant_id=tenant_id,
                invoice_number=self._format_invoice_number(year, month, seq),
                year=year,
                month=month,
                sequential_number=seq,
                issue_date=issue_date,
                sale_date=sale_date,
                seller_name=seller["name"],
                seller_nip=seller["nip"],
                seller_krs=seller["krs"],
                seller_regon=seller["regon"],
                seller_address=seller["address"],
                buyer_name=buyer["name"],
                buyer_nip=buyer["nip"],
                buyer_address=buyer["address"],
                items=items,
                subtotal_net=net,
                vat_rate=VAT_RATE,
                vat_amount=vat,
                total_gross=gross,
                currency=txn.currency,
                payment_method=payment_method,
                payment_id=txn.id,
                status=InvoiceStatus.ISSUED,
            )
            # Savepoint: porażka unique (wyścig na pierwszy numer miesiąca)
            # cofa tylko tę fakturę, nie transakcję webhooka.
            try:
                async with self._db.begin_nested():
                    self._db.add(invoice)
                    await self._db.flush()
            except IntegrityError:
                logger.warning(
                    "Kolizja numeru faktury (%s/%s, próba %s) — ponawiam numerację",
                    year,
                    month,
                    attempt,
                )
                continue
            logger.info("Wygenerowano fakturę %s (tenant %s, transakcja %s)", invoice.invoice_number, tenant_id, txn.id)
            return invoice

        raise RuntimeError(
            f"Nie udało się przydzielić numeru faktury po {_NUMBERING_ATTEMPTS} próbach ({year}/{month})"
        )

    @staticmethod
    def _format_invoice_number(year: int, month: int, seq: int) -> str:
        """AC1/AC6: ``FV/{rok}/{miesiąc}/{numer}`` np. ``FV/2026/06/0001``."""
        return f"FV/{year}/{month:02d}/{seq:04d}"

    async def _get_next_invoice_number(self, year: int, month: int) -> int:
        """Najwyższy ``sequential_number`` miesiąca +1 z row-level lock (AC6).

        ``with_for_update`` blokuje wiersz największego numeru do końca
        transakcji — równoległe wystawienie serializuje się na odczycie;
        dla pierwszego numeru miesiąca (0 wierszy) backstopem jest unique
        constraint + retry w :meth:`generate_invoice`.

        Celowo bez agregatu: ``max(...) FOR UPDATE`` to nieważny SQL
        w PostgreSQL (asyncpg FeatureNotSupportedError — wykryte na
        pierwszym żywym przebiegu sandboxa 2026-09-14); ``ORDER BY … DESC
        LIMIT 1`` daje ten sam wynik z legalnym lockiem wiersza.
        """
        result = await self._db.execute(
            select(Invoice.sequential_number)
            .where(Invoice.year == year, Invoice.month == month)
            .order_by(Invoice.sequential_number.desc())
            .limit(1)
            .with_for_update()
        )
        current = result.scalar_one_or_none()
        return (current or 0) + 1

    async def _invoice_for_payment(self, payment_id: uuid.UUID) -> Invoice | None:
        result = await self._db.execute(select(Invoice).where(Invoice.payment_id == payment_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _item_name(txn: PaymentTransaction) -> str:
        plan = (txn.meta or {}).get("plan")
        if plan:
            return f"Subskrypcja TestGEN — plan {str(plan).capitalize()} (miesięczna)"
        return "Subskrypcja TestGEN (miesięczna)"

    @staticmethod
    def _plan_display(txn: PaymentTransaction) -> str:
        plan = (txn.meta or {}).get("plan")
        return str(plan).capitalize() if plan else "TestGEN"

    async def _period_description(self, tenant_id: uuid.UUID, txn: PaymentTransaction, fallback_date: date) -> str:
        """Okres, którego dotyczy płatność (AC1): bieżący okres subskrypcji
        (po aktywacji/odnowieniu), fallback ``meta.period_end_hint``, potem miesiąc."""
        result = await self._db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id))
        subscription = result.scalar_one_or_none()
        if subscription is not None and subscription.current_period_end is not None:
            start = subscription.current_period_start
            end = subscription.current_period_end
            return f"{start.date().isoformat()} - {end.date().isoformat()}"
        hint = (txn.meta or {}).get("period_end_hint")
        if hint:
            return str(hint)
        return fallback_date.strftime("%Y-%m")

    async def _buyer_snapshot(self, tenant_id: uuid.UUID) -> dict:
        """Dane nabywcy (AC1/AC4): ``invoice_data``, przy braku — fallback
        na profil tenanta (faktura musi powstać, nie blokuje płatności)."""
        data = await self.get_or_create_invoice_data(tenant_id)
        return {"name": data.company_name, "nip": data.nip, "address": dict(data.address or {})}

    # --- AC2/AC3: PDF asynchronicznie (Celery) ---

    async def render_and_deliver(self, invoice_id: uuid.UUID) -> Invoice:
        """PDF → MinIO → email (AC2/AC3). Idempotentne — gotowy PDF nie
        jest generowany ani wysyłany ponownie. Uruchamiane z Celery
        (kontekst RLS admina, jak WebhookProcessor)."""
        invoice = await self._get_invoice(invoice_id)
        if invoice.pdf_path and invoice.pdf_generated_at:
            logger.info("PDF faktury %s już wygenerowany (%s) — pomijam", invoice.invoice_number, invoice.pdf_path)
            return invoice

        pdf_bytes = self._render_pdf(invoice)
        invoice.pdf_path = await self._upload_to_minio(
            pdf_bytes, invoice.tenant_id, invoice.year, invoice.month, invoice.invoice_number
        )
        invoice.pdf_generated_at = datetime.now(UTC)
        await self._db.flush()

        await self._send_invoice_email(invoice, pdf_bytes)
        logger.info("PDF faktury %s zapisany w MinIO i wysłany emailem", invoice.invoice_number)
        return invoice

    def _render_pdf(self, invoice: Invoice) -> bytes:
        """HTML (Jinja2) → PDF (WeasyPrint). Import defensywny — pakiet
        opcjonalny w środowiskach bez Pango (wzorzec sqlglot, Story 1.53)."""
        try:
            from weasyprint import HTML
        except ImportError as exc:  # pragma: no cover — brak natywnych bibliotek
            raise RuntimeError("weasyprint niedostępny — zainstaluj pakiet i zależności systemowe (libpango)") from exc

        html = _jinja_env.get_template("invoice_template.html").render(**self._template_context(invoice))
        return HTML(string=html).write_pdf()

    def _template_context(self, invoice: Invoice) -> dict:
        item = (invoice.items or [{}])[0]
        buyer_address = dict(invoice.buyer_address or {})
        seller_address = dict(invoice.seller_address or {})

        def _addr(a: dict) -> dict:
            return {
                "street": a.get("street", ""),
                "city": a.get("city", ""),
                "postal_code": a.get("postal_code", ""),
                "country": a.get("country", ""),
            }

        return {
            "invoice_number": invoice.invoice_number,
            "issue_date": invoice.issue_date.isoformat(),
            "sale_date": invoice.sale_date.isoformat(),
            "seller": {
                "name": invoice.seller_name,
                "nip": invoice.seller_nip,
                "krs": invoice.seller_krs or "",
                "regon": invoice.seller_regon or "",
                "address": _addr(seller_address),
            },
            "buyer": {
                "name": invoice.buyer_name,
                "nip": invoice.buyer_nip,
                "address": _addr(buyer_address),
            },
            "items": [
                {
                    "name": item.get("name", ""),
                    "period": item.get("period", ""),
                    "net": format_pln(item.get("net", invoice.subtotal_net)),
                    "vat_rate": item.get("vat_rate", str(invoice.vat_rate)),
                    "vat_amount": format_pln(item.get("vat_amount", invoice.vat_amount)),
                    "gross": format_pln(item.get("gross", invoice.total_gross)),
                }
            ],
            "subtotal_net": format_pln(invoice.subtotal_net),
            "vat_rate": invoice.vat_rate,
            "vat_amount": format_pln(invoice.vat_amount),
            "total_gross": format_pln(invoice.total_gross),
            "currency": invoice.currency,
            "payment_method_display": _PAYMENT_METHOD_DISPLAY.get(invoice.payment_method, str(invoice.payment_method)),
        }

    async def _upload_to_minio(
        self, pdf_bytes: bytes, tenant_id: uuid.UUID, year: int, month: int, invoice_number: str
    ) -> str:
        """Upload PDF do MinIO (AC2). SDK synchroniczne → ``to_thread``."""
        object_name = invoice_pdf_object_name(tenant_id, year, month, invoice_number)

        def _upload() -> None:
            storage.ensure_bucket_exists(INVOICES_BUCKET)
            import io

            storage.upload_file(INVOICES_BUCKET, object_name, io.BytesIO(pdf_bytes), len(pdf_bytes), "application/pdf")

        await asyncio.to_thread(_upload)
        return object_name

    async def _send_invoice_email(self, invoice: Invoice, pdf_bytes: bytes) -> None:
        """AC3: email z PDF do Ownera tenanta (best-effort — nie wywala
        taska po udanym zapisie w MinIO; PDF jest w panelu)."""
        owner_email = await self._owner_email(invoice.tenant_id)
        if not owner_email:
            logger.warning("Faktura %s: brak adresu Ownera — email pominięty", invoice.invoice_number)
            return

        item = (invoice.items or [{}])[0]
        try:
            from app.services.email.email_service import send_invoice_email

            send_invoice_email(
                email=owner_email,
                invoice_number=invoice.invoice_number,
                plan_display=str(item.get("plan_display", "")),
                amount=f"{format_pln(invoice.total_gross)} {invoice.currency}",
                period=str(item.get("period", "")),
                pdf_bytes=pdf_bytes,
            )
        except Exception:
            logger.exception("Email z fakturą %s nie wysłany — PDF dostępny w panelu", invoice.invoice_number)

    async def _owner_email(self, tenant_id: uuid.UUID) -> str | None:
        result = await self._db.execute(
            select(User.email)
            .join(UserTenant, UserTenant.user_id == User.id)
            .where(UserTenant.tenant_id == tenant_id, UserTenant.role == TenantRole.OWNER)
            .limit(1)
        )
        return result.scalar_one_or_none()

    # --- AC5: lista i pobieranie ---

    async def get_invoices(self, tenant_id: uuid.UUID, page: int = 1, size: int = 20) -> tuple[list[Invoice], int]:
        """Lista faktur malejąco po dacie wystawienia (AC5), paginacja
        domyślnie 20/stronę."""
        total = await self._db.scalar(select(func.count()).select_from(Invoice).where(Invoice.tenant_id == tenant_id))
        result = await self._db.execute(
            select(Invoice)
            .where(Invoice.tenant_id == tenant_id)
            .order_by(Invoice.issue_date.desc(), Invoice.sequential_number.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(result.scalars().all()), int(total or 0)

    async def get_invoice_pdf(self, invoice_id: uuid.UUID, tenant_id: uuid.UUID) -> tuple[Invoice, bytes]:
        """PDF faktury z MinIO (AC5) — tenant-scoped (RLS + jawny filtr)."""
        invoice = await self._get_invoice(invoice_id)
        if invoice.tenant_id != tenant_id:
            raise NotFoundError("Faktura nie istnieje")
        if not invoice.pdf_path:
            raise NotFoundError("PDF faktury jeszcze nie wygenerowany")
        data = await asyncio.to_thread(storage.download_file_bytes, INVOICES_BUCKET, invoice.pdf_path)
        return invoice, data

    async def _get_invoice(self, invoice_id: uuid.UUID) -> Invoice:
        result = await self._db.execute(select(Invoice).where(Invoice.id == invoice_id))
        invoice = result.scalar_one_or_none()
        if invoice is None:
            raise NotFoundError("Faktura nie istnieje")
        return invoice

    # --- AC4: dane fakturowe ---

    async def get_or_create_invoice_data(self, tenant_id: uuid.UUID) -> InvoiceData:
        """Dane fakturowe tenanta; przy braku — inicjalizacja z profilu
        tenanta (nazwa, NIP), do uzupełnienia przez Ownera (AC4)."""
        result = await self._db.execute(select(InvoiceData).where(InvoiceData.tenant_id == tenant_id))
        data = result.scalar_one_or_none()
        if data is not None:
            return data

        tenant = await self._db.get(Tenant, tenant_id)
        data = InvoiceData(
            tenant_id=tenant_id,
            company_name=tenant.name if tenant else "",
            nip=tenant.nip if tenant else None,
            address={},
        )
        self._db.add(data)
        await self._db.flush()
        return data

    async def update_invoice_data(
        self,
        tenant_id: uuid.UUID,
        *,
        company_name: str,
        nip: str | None = None,
        address: dict | None = None,
    ) -> InvoiceData:
        """Aktualizacja danych fakturowych (AC4) — upsert; używane przy
        następnej generacji faktury, wystawione pozostają bez zmian."""
        data = await self.get_or_create_invoice_data(tenant_id)
        data.company_name = company_name
        data.nip = nip
        data.address = address or {}
        await self._db.flush()
        return data
