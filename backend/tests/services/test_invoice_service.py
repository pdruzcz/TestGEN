"""Testy InvoiceService — Story 7.6 (AC1-AC6; Task 7.1/7.2/7.4).

Generowanie faktury po płatności (snapshot sprzedawcy/nabywcy, VAT 23%
od kwoty brutto), numeracja sekwencyjna z row-level lock + retry na
kolizji unikalności (AC6), PDF→MinIO→email (mocki), lista z paginacją,
dane fakturowe (AC4) oraz integracja webhook→faktura (Task 7.4).
DB mockowana (wzorzec test_payment_tokens).
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.models.invoice import Invoice, InvoicePaymentMethod, InvoiceStatus
from app.models.invoice_data import InvoiceData
from app.models.payment import PaymentStatus, PaymentTransaction
from app.services.billing.invoice_service import (
    INVOICES_BUCKET,
    InvoiceService,
    format_pln,
    invoice_pdf_object_name,
    seller_snapshot,
    split_vat,
)
from tests.fixtures.billing_fixtures import savepoint_cm


def _columns(model) -> dict[str, object]:
    return {c.name for c in inspect(model).columns}


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _txn(tenant_id=None, amount="30.00", **kw) -> PaymentTransaction:
    fields = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        provider="tpay",
        hidden_description=str(uuid.uuid4()),
        amount=Decimal(amount),
        currency="PLN",
        status=PaymentStatus.PAID,
        paid_amount=Decimal(amount),
        meta={"plan": "basic", "payer_email": "owner@test.com"},
    )
    fields.update(kw)
    return PaymentTransaction(**fields)


def _db() -> AsyncMock:
    """AsyncMock sesji z poprawnym ``begin_nested`` (async CM, nie korutyna)."""
    db = AsyncMock()
    db.begin_nested = MagicMock(return_value=AsyncMock())
    return db


def _tenant(name: str = "Acme Sp. z o.o.", nip: str | None = "1112223344") -> MagicMock:
    """Tenant dla ``db.get`` — atrybuty jawne (``name=`` kwarg ustawia repr mocka)."""
    tenant = MagicMock()
    tenant.name = name
    tenant.nip = nip
    return tenant


def _invoice_row(tenant_id, seq=1, **kw) -> Invoice:
    fields = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_number=f"FV/2026/09/{seq:04d}",
        year=2026,
        month=9,
        sequential_number=seq,
        issue_date=date(2026, 9, 10),
        sale_date=date(2026, 9, 10),
        seller_name="TestGEN Sp. z o.o.",
        seller_nip="5210000000",
        seller_address={"street": "ul. Testowa 1", "city": "Warszawa", "postal_code": "00-001", "country": "Polska"},
        buyer_name="Klient Sp. z o.o.",
        buyer_nip="1234567890",
        buyer_address={"street": "ul. Kliencka 2", "city": "Kraków", "postal_code": "30-001", "country": "Polska"},
        items=[
            {
                "name": "Subskrypcja — plan Basic",
                "net": "24.39",
                "vat_rate": "23",
                "vat_amount": "5.61",
                "gross": "30.00",
            }
        ],
        subtotal_net=Decimal("24.39"),
        vat_rate=Decimal("23"),
        vat_amount=Decimal("5.61"),
        total_gross=Decimal("30.00"),
        currency="PLN",
        payment_method=InvoicePaymentMethod.CARD,
        status=InvoiceStatus.ISSUED,
        created_at=datetime.now(UTC),
    )
    fields.update(kw)
    return Invoice(**fields)


class TestInvoiceModelShape:
    """Task 1 — kształt tabel invoices/invoice_data."""

    def test_tablenames(self):
        assert Invoice.__tablename__ == "invoices"
        assert InvoiceData.__tablename__ == "invoice_data"

    def test_invoice_columns(self):
        cols = _columns(Invoice)
        expected = {
            "id",
            "tenant_id",
            "invoice_number",
            "year",
            "month",
            "sequential_number",
            "issue_date",
            "sale_date",
            "seller_name",
            "seller_nip",
            "seller_address",
            "buyer_name",
            "buyer_nip",
            "buyer_address",
            "items",
            "subtotal_net",
            "vat_rate",
            "vat_amount",
            "total_gross",
            "currency",
            "payment_method",
            "payment_id",
            "status",
            "pdf_path",
            "pdf_generated_at",
            "created_at",
            "updated_at",
        }
        assert expected <= cols

    def test_unique_constraint_year_month_seq(self):
        """AC6 — unikalność (year, month, sequential_number)."""
        names = {c.name for c in Invoice.__table__.constraints}
        assert "uq_invoices_year_month_seq" in names

    def test_enum_values(self):
        assert {s.value for s in InvoiceStatus} == {"issued", "canceled", "corrected"}
        assert {m.value for m in InvoicePaymentMethod} == {"card", "bank_transfer", "blik"}

    def test_invoice_data_columns(self):
        cols = _columns(InvoiceData)
        assert {"id", "tenant_id", "company_name", "nip", "address", "created_at", "updated_at"} <= cols


class TestVatHelpers:
    """AC1 — kwoty netto/VAT od brutto (23%, ROUND_HALF_UP)."""

    def test_split_vat_30(self):
        net, vat = split_vat(Decimal("30.00"))
        assert (net, vat) == (Decimal("24.39"), Decimal("5.61"))
        assert net + vat == Decimal("30.00")

    def test_split_vat_50(self):
        net, vat = split_vat(Decimal("50.00"))
        assert (net, vat) == (Decimal("40.65"), Decimal("9.35"))

    def test_format_pln(self):
        assert format_pln(Decimal("30.00")) == "30,00"

    def test_seller_snapshot_from_config(self):
        seller = seller_snapshot()
        # 2026-09-22: snapshot rozszerzony o dane rejestrowe wystawcy
        assert set(seller) == {"name", "nip", "krs", "regon", "address"}
        assert set(seller["address"]) == {"street", "city", "postal_code", "country"}

    def test_pdf_object_name(self):
        """AC2 — ścieżka {tenant}/{rok}/{miesiąc}/{numer}.pdf w buckecie faktur."""
        tid = uuid.UUID(int=7)
        assert invoice_pdf_object_name(tid, 2026, 6, "FV/2026/06/0001") == (f"{tid}/2026/06/FV/2026/06/0001.pdf")
        assert INVOICES_BUCKET == "testgen-invoices"


class TestGenerateInvoice:
    """AC1 — generowanie po płatności."""

    async def test_creates_invoice_with_sequential_number(self):
        db = _db()
        tid = uuid.uuid4()
        # execute: brak faktury dla payment → brak InvoiceData → brak subskrypcji → seq=0
        db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(None), _scalar(None), _scalar(0)])
        db.get = AsyncMock(return_value=_tenant())

        invoice = await InvoiceService(db).generate_invoice(tid, _txn(tid))

        assert invoice.invoice_number == f"FV/{invoice.year}/{invoice.month:02d}/0001"
        assert invoice.sequential_number == 1
        assert invoice.status == InvoiceStatus.ISSUED
        assert invoice.subtotal_net == Decimal("24.39")
        assert invoice.vat_amount == Decimal("5.61")
        assert invoice.total_gross == Decimal("30.00")
        assert invoice.items[0]["gross"] == "30.00"
        # snapshot nabywcy z fallbacku na profil tenanta (brak invoice_data)
        assert invoice.buyer_name == "Acme Sp. z o.o."
        # add: inicjalizacja InvoiceData (fallback) + rekord faktury
        added_types = [type(c.args[0]).__name__ for c in db.add.call_args_list]
        assert added_types == ["InvoiceData", "Invoice"]

    async def test_idempotent_per_payment(self):
        """Ponowienia webhooka nie dublują faktury (payment_id)."""
        db = _db()
        tid = uuid.uuid4()
        existing = _invoice_row(tid)
        db.execute = AsyncMock(return_value=_scalar(existing))

        txn = _txn(tid)
        invoice = await InvoiceService(db).generate_invoice(tid, txn)

        assert invoice is existing
        db.add.assert_not_called()

    async def test_number_continues_sequence(self):
        db = _db()
        tid = uuid.uuid4()
        db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(None), _scalar(None), _scalar(41)])
        db.get = AsyncMock(return_value=_tenant(name="X", nip=None))

        invoice = await InvoiceService(db).generate_invoice(tid, _txn(tid))

        assert invoice.sequential_number == 42
        assert invoice.invoice_number.endswith("/0042")

    async def test_retry_on_unique_collision(self):
        """AC6 — kolizja (year, month, seq) → savepoint retry z kolejnym numerem."""
        db = _db()
        tid = uuid.uuid4()
        db.execute = AsyncMock(
            side_effect=[
                _scalar(None),  # brak faktury dla payment
                _scalar(None),  # brak InvoiceData
                _scalar(None),  # brak subskrypcji
                _scalar(0),  # seq → 1 (kolizja)
                _scalar(1),  # retry: seq → 2
            ]
        )
        db.get = AsyncMock(return_value=_tenant(name="X", nip=None))
        # flush: #1 get_or_create (OK), #2 insert z sekwencją 1 (kolizja), #3 retry (OK)
        db.flush = AsyncMock(side_effect=[None, IntegrityError("s", "p", Exception("dup")), None])

        invoice = await InvoiceService(db).generate_invoice(tid, _txn(tid))

        assert invoice.sequential_number == 2
        assert invoice.invoice_number.endswith("/0002")


class TestSequentialNumbering:
    """AC6 — row-level lock sekwencji (Task 7.2)."""

    async def test_numbering_query_uses_for_update(self):
        """Najwyższy sequential_number z FOR UPDATE — BEZ agregatu
        (kompilacja postgres). ``max(...) FOR UPDATE`` to nieważny SQL
        w PostgreSQL (asyncpg FeatureNotSupportedError) — wykryte na
        pierwszym żywym przebiegu sandboxa 2026-09-14."""
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_scalar(7))

        await InvoiceService(db)._get_next_invoice_number(2026, 6)

        stmt = db.execute.call_args[0][0]
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE" in sql
        assert "ORDER BY invoices.sequential_number DESC" in sql.replace("\n", " ")
        assert "LIMIT" in sql  # sparametryzowany: LIMIT %(param_1)s
        assert "max(" not in sql.replace("\n", " ")

    async def test_two_concurrent_numbers_differ(self):
        """Symulacja dwóch generowań pod rząd — numery 1 i 2 (AC6)."""
        made: list[Invoice] = []

        for seq_max in (0, 1):
            db = _db()
            tid = uuid.uuid4()
            db.execute = AsyncMock(side_effect=[_scalar(None), _scalar(None), _scalar(None), _scalar(seq_max)])
            db.get = AsyncMock(return_value=_tenant(name="X", nip=None))
            made.append(await InvoiceService(db).generate_invoice(tid, _txn(tid)))

        assert {m.sequential_number for m in made} == {1, 2}
        assert len({m.invoice_number for m in made}) == 2


class TestRenderAndDeliver:
    """AC2/AC3 — PDF → MinIO → email (mocki; Task 7.4 flow)."""

    async def test_pdf_upload_and_email(self):
        db = _db()
        tid = uuid.uuid4()
        invoice = _invoice_row(tid)
        db.execute = AsyncMock(side_effect=[_scalar(invoice), _scalar("owner@test.com")])

        with (
            patch.object(InvoiceService, "_render_pdf", return_value=b"%PDF-1.4") as render,
            patch("app.services.billing.invoice_service.storage") as storage_mock,
            patch("app.services.email.email_service.send_invoice_email") as email_mock,
        ):
            result = await InvoiceService(db).render_and_deliver(invoice.id)

        assert result is invoice
        assert invoice.pdf_path == invoice_pdf_object_name(tid, 2026, 9, invoice.invoice_number)
        assert invoice.pdf_generated_at is not None
        render.assert_called_once_with(invoice)
        storage_mock.upload_file.assert_called_once()
        upload_args = storage_mock.upload_file.call_args
        assert upload_args.args[0] == INVOICES_BUCKET
        assert upload_args.args[1] == invoice.pdf_path
        email_mock.assert_called_once()
        assert email_mock.call_args.kwargs["pdf_bytes"] == b"%PDF-1.4"
        assert email_mock.call_args.kwargs["invoice_number"] == invoice.invoice_number

    async def test_idempotent_when_pdf_exists(self):
        db = AsyncMock()
        invoice = _invoice_row(uuid.uuid4(), pdf_path="tid/2026/09/FV.pdf", pdf_generated_at=datetime.now(UTC))
        db.execute = AsyncMock(return_value=_scalar(invoice))

        with (
            patch.object(InvoiceService, "_render_pdf") as render,
            patch("app.services.billing.invoice_service.storage") as storage_mock,
        ):
            result = await InvoiceService(db).render_and_deliver(invoice.id)

        assert result is invoice
        render.assert_not_called()
        storage_mock.upload_file.assert_not_called()

    async def test_email_skipped_without_owner(self):
        db = AsyncMock()
        invoice = _invoice_row(uuid.uuid4())
        db.execute = AsyncMock(side_effect=[_scalar(invoice), _scalar(None)])

        with (
            patch.object(InvoiceService, "_render_pdf", return_value=b"%PDF"),
            patch("app.services.billing.invoice_service.storage"),
            patch("app.services.email.email_service.send_invoice_email") as email_mock,
        ):
            await InvoiceService(db).render_and_deliver(invoice.id)

        email_mock.assert_not_called()

    def test_template_context_snapshot(self):
        """Kontekst szablonu z rekordu (snapshot), kwoty po polsku."""
        svc = InvoiceService.__new__(InvoiceService)
        invoice = _invoice_row(uuid.uuid4())
        ctx = svc._template_context(invoice)
        assert ctx["invoice_number"] == invoice.invoice_number
        assert ctx["total_gross"] == "30,00"
        assert ctx["seller"]["nip"] == "5210000000"
        assert ctx["buyer"]["address"]["city"] == "Kraków"
        assert ctx["payment_method_display"] == "Karta płatnicza"


class TestListAndPdf:
    """AC5 — lista z paginacją i pobieranie PDF."""

    async def test_get_invoices_paginated(self):
        db = _db()
        tid = uuid.uuid4()
        rows = [_invoice_row(tid, seq=i) for i in range(3)]
        db.scalar = AsyncMock(return_value=3)
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        db.execute = AsyncMock(return_value=result)

        items, total = await InvoiceService(db).get_invoices(tid, page=2, size=3)

        assert items == rows
        assert total == 3
        stmt = db.execute.call_args[0][0]
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "OFFSET" in sql and "LIMIT" in sql
        assert "issue_date DESC" in sql.replace("\n", " ")

    async def test_get_invoice_pdf_downloads_from_minio(self):
        db = _db()
        tid = uuid.uuid4()
        invoice = _invoice_row(tid, pdf_path="tid/2026/09/x.pdf")
        db.execute = AsyncMock(return_value=_scalar(invoice))

        with patch("app.services.billing.invoice_service.storage") as storage_mock:
            storage_mock.download_file_bytes.return_value = b"%PDF"
            inv, data = await InvoiceService(db).get_invoice_pdf(invoice.id, tid)

        assert inv is invoice
        assert data == b"%PDF"
        storage_mock.download_file_bytes.assert_called_once_with(INVOICES_BUCKET, "tid/2026/09/x.pdf")

    async def test_get_invoice_pdf_not_generated_404(self):
        from app.core.exceptions import NotFoundError

        db = _db()
        tid = uuid.uuid4()
        invoice = _invoice_row(tid)
        db.execute = AsyncMock(return_value=_scalar(invoice))

        with pytest.raises(NotFoundError):
            await InvoiceService(db).get_invoice_pdf(invoice.id, tid)

    async def test_get_invoice_pdf_other_tenant_404(self):
        from app.core.exceptions import NotFoundError

        db = AsyncMock()
        invoice = _invoice_row(uuid.uuid4(), pdf_path="x.pdf")
        db.execute = AsyncMock(return_value=_scalar(invoice))

        with pytest.raises(NotFoundError):
            await InvoiceService(db).get_invoice_pdf(invoice.id, uuid.uuid4())


class TestInvoiceData:
    """AC4 — dane fakturowe."""

    async def test_get_or_create_falls_back_to_tenant(self):
        db = _db()
        tid = uuid.uuid4()
        db.execute = AsyncMock(return_value=_scalar(None))
        db.get = AsyncMock(return_value=_tenant(name="Acme"))

        data = await InvoiceService(db).get_or_create_invoice_data(tid)

        assert data.company_name == "Acme"
        assert data.nip == "1112223344"
        db.add.assert_called_once()

    async def test_update_reuses_row(self):
        db = _db()
        tid = uuid.uuid4()
        existing = InvoiceData(tenant_id=tid, company_name="Old", nip=None, address={})
        db.execute = AsyncMock(return_value=_scalar(existing))

        data = await InvoiceService(db).update_invoice_data(
            tid, company_name="New Sp. z o.o.", nip="9998887777", address={"city": "Gdańsk"}
        )

        assert data is existing
        assert data.company_name == "New Sp. z o.o."
        assert data.address == {"city": "Gdańsk"}
        db.add.assert_not_called()


class TestWebhookIntegration:
    """Task 7.4 — płatność → webhook → faktura → PDF (enqueue)."""

    async def test_mark_paid_generates_invoice_and_enqueues_celery(self):
        from app.services.billing.webhook_processor import WebhookProcessor

        db = AsyncMock()
        db.begin_nested = MagicMock(return_value=savepoint_cm())
        provider = MagicMock()
        provider.settings.is_sandbox = False
        txn = _txn(amount="30.00", meta={"plan": "basic", "payer_email": "owner@test.com"})
        invoice = _invoice_row(txn.tenant_id)

        with (
            patch("app.services.billing.webhook_processor.SubscriptionService") as sub_svc,
            patch("app.services.billing.webhook_processor.InvoiceService") as inv_svc,
            patch("app.workers.tasks.generate_invoice_pdf.generate_invoice_pdf") as task_mock,
            patch("app.services.email.email_service.send_payment_confirmation_email"),
        ):
            sub_svc.return_value.activate_paid_plan = AsyncMock()
            inv_svc.return_value.generate_invoice = AsyncMock(return_value=invoice)
            processor = WebhookProcessor(db, provider=provider)
            await processor.mark_paid(txn)

        inv_svc.return_value.generate_invoice.assert_awaited_once()
        # AC2 — PDF asynchronicznie (Celery), nie blokuje webhooka
        task_mock.delay.assert_called_once_with(str(invoice.id))

    async def test_invoice_failure_does_not_break_webhook(self):
        """Best-effort: porażka faktury nie wywala przetwarzania płatności."""
        from app.services.billing.webhook_processor import WebhookProcessor

        db = AsyncMock()
        db.begin_nested = MagicMock(return_value=savepoint_cm())
        provider = MagicMock()
        provider.settings.is_sandbox = False
        txn = _txn(meta={"plan": "basic"})

        with (
            patch("app.services.billing.webhook_processor.SubscriptionService") as sub_svc,
            patch("app.services.billing.webhook_processor.InvoiceService") as inv_svc,
            patch("app.workers.tasks.generate_invoice_pdf.generate_invoice_pdf") as task_mock,
            patch("app.services.email.email_service.send_payment_confirmation_email"),
        ):
            sub_svc.return_value.activate_paid_plan = AsyncMock()
            inv_svc.return_value.generate_invoice = AsyncMock(side_effect=RuntimeError("db down"))
            processor = WebhookProcessor(db, provider=provider)
            await processor.mark_paid(txn)  # nie rzuca

        task_mock.delay.assert_not_called()
        sub_svc.return_value.activate_paid_plan.assert_awaited_once()
