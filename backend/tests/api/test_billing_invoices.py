"""Testy API faktur VAT — Story 7.6 (AC4, AC5; Task 7.3).

GET /billing/invoices (lista z paginacją), GET /billing/invoices/{id}/pdf
(plik z MinIO, 404 gdy nie wygenerowany), GET/PUT /billing/invoice-data
(guard roli Owner). DB i serwis mockowane (wzorzec test_billing_payment_methods).
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.main import create_app
from app.models.invoice import InvoicePaymentMethod, InvoiceStatus
from app.services.billing.invoice_service import InvoiceService
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db, role="owner"):
    from fastapi import Request

    tenant_id = uuid.uuid4()
    user._tenant_id = tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant_id
        request.state.role = role
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return tenant_id


def _invoice(tenant_id, seq=1, pdf_path=None, **kw) -> MagicMock:
    fields = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        invoice_number=f"FV/2026/09/{seq:04d}",
        issue_date=date(2026, 9, 10),
        sale_date=date(2026, 9, 10),
        buyer_name="Klient Sp. z o.o.",
        subtotal_net=Decimal("24.39"),
        vat_rate=Decimal("23"),
        vat_amount=Decimal("5.61"),
        total_gross=Decimal("30.00"),
        currency="PLN",
        payment_method=InvoicePaymentMethod.CARD,
        status=InvoiceStatus.ISSUED,
        pdf_path=pdf_path,
        pdf_generated_at=datetime.now(UTC) if pdf_path else None,
        created_at=datetime.now(UTC),
    )
    fields.update(kw)
    inv = MagicMock()
    for k, v in fields.items():
        setattr(inv, k, v)
    inv.pdf_available = pdf_path is not None
    return inv


def _invoice_data(tenant_id, **kw) -> MagicMock:
    fields = dict(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        company_name="Klient Sp. z o.o.",
        nip="1234567890",
        address={"street": "ul. Kliencka 2", "city": "Kraków", "postal_code": "30-001", "country": "Polska"},
    )
    fields.update(kw)
    data = MagicMock()
    for k, v in fields.items():
        setattr(data, k, v)
    return data


class TestListInvoices:
    async def test_owner_gets_paginated_list(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        rows = [_invoice(tid, seq=i) for i in (3, 2, 1)]

        with patch.object(InvoiceService, "get_invoices", AsyncMock(return_value=(rows, 3))):
            resp = await client.get("/api/v1/billing/invoices")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["size"] == 20
        assert len(body["items"]) == 3
        assert body["items"][0]["invoice_number"] == "FV/2026/09/0003"
        assert body["items"][0]["total_gross"] == "30.00"
        assert body["items"][0]["status"] == "issued"
        assert body["items"][0]["pdf_available"] is False

    async def test_user_role_allowed(self, client, app):
        """AC5 — Owner LUB User."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")

        with patch.object(InvoiceService, "get_invoices", AsyncMock(return_value=([], 0))):
            resp = await client.get("/api/v1/billing/invoices")

        assert resp.status_code == 200
        assert resp.json()["items"] == []

    async def test_page_and_size_params(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)

        with patch.object(InvoiceService, "get_invoices", AsyncMock(return_value=([], 45))) as mock:
            resp = await client.get("/api/v1/billing/invoices", params={"page": 3, "size": 10})

        assert resp.status_code == 200
        assert mock.call_args.args[0] == tid
        assert mock.call_args.kwargs == {"page": 3, "size": 10}


class TestDownloadInvoicePdf:
    async def test_pdf_streamed_from_minio(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        inv = _invoice(tid, pdf_path=f"{tid}/2026/09/FV.pdf")

        with patch.object(InvoiceService, "get_invoice_pdf", AsyncMock(return_value=(inv, b"%PDF-1.4-bytes"))):
            resp = await client.get(f"/api/v1/billing/invoices/{inv.id}/pdf")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == b"%PDF-1.4-bytes"
        assert "Faktura_FV_2026_09_0001.pdf" in resp.headers["content-disposition"]

    async def test_pdf_not_generated_404(self, client, app):
        from app.core.exceptions import NotFoundError

        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        with patch.object(
            InvoiceService, "get_invoice_pdf", AsyncMock(side_effect=NotFoundError("PDF nie wygenerowany"))
        ):
            resp = await client.get(f"/api/v1/billing/invoices/{uuid.uuid4()}/pdf")

        assert resp.status_code == 404


class TestInvoiceData:
    async def test_get_initializes_from_tenant(self, client, app):
        """AC4 — brak rekordu → inicjalizacja z profilu tenanta."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        data = _invoice_data(tid)

        with patch.object(InvoiceService, "get_or_create_invoice_data", AsyncMock(return_value=data)):
            resp = await client.get("/api/v1/billing/invoice-data")

        assert resp.status_code == 200
        body = resp.json()
        assert body["company_name"] == "Klient Sp. z o.o."
        assert body["nip"] == "1234567890"
        assert body["address"]["postal_code"] == "30-001"

    async def test_get_requires_owner(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")

        resp = await client.get("/api/v1/billing/invoice-data")

        assert resp.status_code == 403

    async def test_put_updates_and_returns(self, client, app):
        """AC4 — aktualizacja danych fakturowych."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        data = _invoice_data(tid, company_name="Nowa Nazwa", nip=None, address={"street": "ul. Nowa 5"})

        with patch.object(InvoiceService, "update_invoice_data", AsyncMock(return_value=data)) as mock:
            resp = await client.put(
                "/api/v1/billing/invoice-data",
                json={
                    "company_name": "Nowa Nazwa",
                    "nip": None,
                    "street": "ul. Nowa 5",
                    "city": "",
                    "postal_code": "",
                    "country": "Polska",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["company_name"] == "Nowa Nazwa"
        assert mock.call_args.kwargs["company_name"] == "Nowa Nazwa"
        assert mock.call_args.kwargs["address"]["street"] == "ul. Nowa 5"

    async def test_put_requires_owner(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")

        resp = await client.put(
            "/api/v1/billing/invoice-data",
            json={"company_name": "X"},
        )

        assert resp.status_code == 403

    async def test_put_validates_empty_name(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        resp = await client.put(
            "/api/v1/billing/invoice-data",
            json={"company_name": ""},
        )

        assert resp.status_code == 422
