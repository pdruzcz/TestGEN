"""Testy API portalu billingowego — Story 7.7 (AC2-AC5; Task 7.1).

GET /billing/subscription (rozbudowany detail: plan, metoda płatności,
zaplanowany downgrade), GET /billing/transactions (filtry + paginacja +
join Invoice), POST /billing/subscription/cancel i /reactivate (operacje
lokalne §3.5 — bez wywołań tpay; provider nie jest w ogóle wołany).
DB mockowana sekwencją wyników ``execute`` (wzorzec test_billing_payment_methods).
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db
from app.main import create_app
from app.models.plan_change import PlanChangeType
from app.models.subscription import SubscriptionStatus
from app.models.subscription_plan import PlanName
from tests.factories import make_user
from tests.fixtures.billing_fixtures import (
    make_change_history,
    make_payment_txn,
    make_plan,
    make_subscription,
    saved_card_token,
    scalar,
    scalars,
)


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


def _count(n: int) -> MagicMock:
    r = MagicMock()
    r.scalar_one.return_value = n
    return r


class TestGetSubscriptionDetail:
    """AC3 — GET /billing/subscription: plan, status, okres, metoda, downgrade."""

    async def test_detail_with_payment_method(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        plan = make_plan(PlanName.BASIC)
        token = saved_card_token(tid)
        sub = make_subscription(plan, tenant_id=tid, payment_token_id=token.id)
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(plan), scalar(token), scalar(None)])

        resp = await client.get("/api/v1/billing/subscription")

        assert resp.status_code == 200
        body = resp.json()
        assert body["plan_name"] == "basic"
        assert body["plan_display_name"] == "Basic"
        assert body["plan_price_monthly"] == "30.00"
        assert body["status"] == "active"
        assert body["cancel_at_period_end"] is False
        assert body["payment_method"]["kind"] == "card_token"
        assert body["payment_method"]["card_tail"] == "0016"
        assert body["payment_method"]["card_brand"] == "mastercard"
        assert body["pending_change"] is None
        assert body["grace_until"] is None

    async def test_detail_without_payment_method_skips_token_query(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        plan = make_plan(PlanName.PREMIUM)
        sub = make_subscription(plan, tenant_id=tid)  # payment_token_id=None
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(plan), scalar(None)])

        resp = await client.get("/api/v1/billing/subscription")

        assert resp.status_code == 200
        body = resp.json()
        assert body["plan_name"] == "premium"
        assert body["payment_method"] is None
        assert db.execute.await_count == 3

    async def test_detail_with_pending_downgrade(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        premium = make_plan(PlanName.PREMIUM)
        sub = make_subscription(premium, tenant_id=tid, cancel_at_period_end=True, with_next_charge=False)
        pending = make_change_history(
            tid, from_plan=PlanName.PREMIUM, to_plan=PlanName.BASIC, change_type=PlanChangeType.DOWNGRADE
        )
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(premium), scalar(pending)])

        resp = await client.get("/api/v1/billing/subscription")

        assert resp.status_code == 200
        body = resp.json()
        assert body["cancel_at_period_end"] is True
        assert body["pending_change"]["to_plan"] == "basic"
        assert body["pending_change"]["change_type"] == "downgrade"

    async def test_no_subscription_404(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.execute = AsyncMock(side_effect=[scalar(None)])

        resp = await client.get("/api/v1/billing/subscription")
        assert resp.status_code == 404

    async def test_user_role_can_view(self, client, app):
        """Task 2.2 — User może przeglądać (widok), nie zarządzać."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db, role="user")
        plan = make_plan(PlanName.FREEMIUM)
        sub = make_subscription(plan, tenant_id=tid)
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(plan), scalar(None)])

        resp = await client.get("/api/v1/billing/subscription")
        assert resp.status_code == 200


class TestCancelSubscription:
    """AC4 — anulowanie lokalne: cancel_at_period_end=true, next_charge_at=None."""

    async def test_owner_cancels(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        plan = make_plan(PlanName.BASIC)
        token = saved_card_token(tid)
        sub = make_subscription(plan, tenant_id=tid, payment_token_id=token.id)
        db.execute = AsyncMock(
            side_effect=[
                scalar(sub),  # locked sub
                scalar(None),  # pending change
                scalar(plan),  # plan (guard Freemium)
                scalar(sub),  # detail: sub
                scalar(plan),  # detail: plan
                scalar(token),  # detail: token
                scalar(None),  # detail: pending
            ]
        )

        resp = await client.post("/api/v1/billing/subscription/cancel")

        assert resp.status_code == 200
        assert sub.cancel_at_period_end is True
        assert sub.next_charge_at is None
        db.commit.assert_awaited_once()
        body = resp.json()
        assert body["cancel_at_period_end"] is True
        assert body["next_charge_at"] is None
        assert body["payment_method"]["card_tail"] == "0016"

    async def test_non_owner_gets_403(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")
        resp = await client.post("/api/v1/billing/subscription/cancel")
        assert resp.status_code == 403

    async def test_freemium_409(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        freemium = make_plan(PlanName.FREEMIUM)
        sub = make_subscription(freemium, tenant_id=tid)
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(None), scalar(freemium)])

        resp = await client.post("/api/v1/billing/subscription/cancel")

        assert resp.status_code == 409
        assert "freemium" in resp.json()["detail"].lower()

    async def test_already_cancelled_409(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        plan = make_plan(PlanName.BASIC)
        sub = make_subscription(plan, tenant_id=tid, cancel_at_period_end=True, with_next_charge=False)
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(None), scalar(plan)])

        resp = await client.post("/api/v1/billing/subscription/cancel")

        assert resp.status_code == 409
        assert "anulowana" in resp.json()["detail"].lower()

    async def test_cancel_with_pending_downgrade_is_idempotent(self, client, app):
        """AC4 — zaplanowany downgrade (7.5) ma pierwszeństwo: postconditions
        już spełnione, powrót na koniec okresu do planu niższego, nie Freemium."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        premium = make_plan(PlanName.PREMIUM)
        sub = make_subscription(premium, tenant_id=tid, cancel_at_period_end=True, with_next_charge=False)
        pending = make_change_history(
            tid, from_plan=PlanName.PREMIUM, to_plan=PlanName.BASIC, change_type=PlanChangeType.DOWNGRADE
        )
        db.execute = AsyncMock(
            side_effect=[
                scalar(sub),
                scalar(pending),
                scalar(premium),
                scalar(sub),
                scalar(premium),
                scalar(pending),
            ]
        )

        resp = await client.post("/api/v1/billing/subscription/cancel")

        assert resp.status_code == 200
        assert resp.json()["pending_change"]["to_plan"] == "basic"

    async def test_past_due_409(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        plan = make_plan(PlanName.BASIC)
        sub = make_subscription(plan, tenant_id=tid, status=SubscriptionStatus.PAST_DUE)
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(None), scalar(plan)])

        resp = await client.post("/api/v1/billing/subscription/cancel")
        assert resp.status_code == 409

    async def test_no_subscription_404(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.execute = AsyncMock(side_effect=[scalar(None)])

        resp = await client.post("/api/v1/billing/subscription/cancel")
        assert resp.status_code == 404


class TestReactivateSubscription:
    """AC5 — reaktywacja lokalna: flaga zdjęta, next_charge_at=koniec okresu."""

    async def test_owner_reactivates(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        plan = make_plan(PlanName.PREMIUM)
        sub = make_subscription(plan, tenant_id=tid, cancel_at_period_end=True, with_next_charge=False)
        db.execute = AsyncMock(
            side_effect=[
                scalar(sub),  # locked sub
                scalar(None),  # pending change
                scalar(sub),  # detail
                scalar(plan),
                scalar(None),
            ]
        )

        resp = await client.post("/api/v1/billing/subscription/reactivate")

        assert resp.status_code == 200
        assert sub.cancel_at_period_end is False
        assert sub.next_charge_at == sub.current_period_end
        db.commit.assert_awaited_once()
        assert resp.json()["cancel_at_period_end"] is False
        assert resp.json()["next_charge_at"] is not None

    async def test_not_cancelled_409(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        plan = make_plan(PlanName.BASIC)
        sub = make_subscription(plan, tenant_id=tid)  # cancel=False
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(None)])

        resp = await client.post("/api/v1/billing/subscription/reactivate")
        assert resp.status_code == 409

    async def test_pending_change_409(self, client, app):
        """Reaktywacja sprzeczna z zaplanowanym downgrade — najpierw anuluj zmianę."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        plan = make_plan(PlanName.PREMIUM)
        sub = make_subscription(plan, tenant_id=tid, cancel_at_period_end=True, with_next_charge=False)
        pending = make_change_history(
            tid, from_plan=PlanName.PREMIUM, to_plan=PlanName.BASIC, change_type=PlanChangeType.DOWNGRADE
        )
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(pending)])

        resp = await client.post("/api/v1/billing/subscription/reactivate")

        assert resp.status_code == 409
        assert "zmian" in resp.json()["detail"].lower()

    async def test_period_ended_409(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        plan = make_plan(PlanName.BASIC)
        sub = make_subscription(
            plan,
            tenant_id=tid,
            period_start=datetime.now(UTC) - timedelta(days=40),
            days=30,  # okres zakończony 10 dni temu
            cancel_at_period_end=True,
            with_next_charge=False,
        )
        db.execute = AsyncMock(side_effect=[scalar(sub), scalar(None)])

        resp = await client.post("/api/v1/billing/subscription/reactivate")
        assert resp.status_code == 409

    async def test_non_owner_gets_403(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")
        resp = await client.post("/api/v1/billing/subscription/reactivate")
        assert resp.status_code == 403


class TestListTransactions:
    """AC2 — historia transakcji: sortowanie malejąco, filtry, paginacja 20/stronę."""

    def _txn(self, tid, *, days_ago=0, status=None, meta=None):
        from app.models.payment import PaymentStatus

        txn = make_payment_txn(
            tid,
            amount="30.00",
            status=status or PaymentStatus.PAID,
            meta=meta,
        )
        txn.created_at = datetime.now(UTC) - timedelta(days=days_ago)
        txn.test_mode = False  # default kolumny widoczny dopiero po flush
        return txn

    def _invoice(self, txn, number="FV/2026/09/0001", method="card"):
        inv = MagicMock()
        inv.id = uuid.uuid4()
        inv.payment_id = txn.id
        inv.invoice_number = number
        inv.payment_method = type("M", (), {"value": method})()  # enum-wartość bez importu modelu faktury
        return inv

    async def test_list_with_invoice_join(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        t_new = self._txn(tid, days_ago=0)
        t_old = self._txn(tid, days_ago=5)
        t_new.paid_amount = None
        inv = self._invoice(t_new)
        db.execute = AsyncMock(side_effect=[_count(2), scalars(t_new, t_old), scalars(inv)])

        resp = await client.get("/api/v1/billing/transactions")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["size"] == 20
        assert len(body["items"]) == 2
        first = body["items"][0]
        assert first["status"] == "paid"
        assert first["amount"] == "30.00"
        assert first["currency"] == "PLN"
        assert first["method"] == "card"  # z joinu z fakturą
        assert first["invoice_number"] == "FV/2026/09/0001"
        assert first["invoice_id"]
        assert body["items"][1]["method"] is None  # brak faktury i meta
        assert body["items"][1]["invoice_number"] is None

    async def test_blik_method_from_meta(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        txn = self._txn(tid, meta={"blik_alias_value": "tg-alias-1"})
        db.execute = AsyncMock(side_effect=[_count(1), scalars(txn), scalars()])

        resp = await client.get("/api/v1/billing/transactions")

        assert resp.status_code == 200
        assert resp.json()["items"][0]["method"] == "blik"

    async def test_filters_status_and_date_range(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        txn = self._txn(tid)
        db.execute = AsyncMock(side_effect=[_count(1), scalars(txn), scalars()])

        resp = await client.get(
            "/api/v1/billing/transactions",
            params={"status": "paid", "date_from": "2026-01-01", "date_to": "2026-01-31", "page": 1},
        )

        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_invalid_status_422(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        resp = await client.get("/api/v1/billing/transactions", params={"status": "bogus"})
        assert resp.status_code == 422

    async def test_empty_page_skips_invoice_query(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.execute = AsyncMock(side_effect=[_count(0), scalars()])

        resp = await client.get("/api/v1/billing/transactions")

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert db.execute.await_count == 2

    async def test_user_role_can_view(self, client, app):
        """AC2 — historia dostępna też dla roli User (przeglądanie)."""
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")
        db.execute = AsyncMock(side_effect=[_count(0), scalars()])

        resp = await client.get("/api/v1/billing/transactions")
        assert resp.status_code == 200
