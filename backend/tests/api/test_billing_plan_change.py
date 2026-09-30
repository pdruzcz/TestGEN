"""Testy API zmiany planu — Story 7.5 (Task 3, Task 6.3).

POST /billing/subscription/change, POST /billing/subscription/change/cancel-pending,
GET /billing/subscription/history, GET /billing/subscription/proration.
Walidacje: ten sam plan → 400, brak roli Owner → 403, downgrade podczas
dunningu → 409. DB mockowana + provider mock (wzorzec test_billing_payment_methods).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db, get_payment_provider
from app.main import create_app
from app.models.plan_change import PlanChangeHistory, PlanChangeStatus, PlanChangeType
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
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


def _override_provider(app) -> AsyncMock:
    provider = AsyncMock()
    checkout = MagicMock()
    checkout.transaction_id = "ta_123"
    checkout.transaction_payment_url = "https://secure.tpay.com/panel/x"
    provider.create_checkout = AsyncMock(return_value=checkout)
    app.dependency_overrides[get_payment_provider] = lambda: provider
    return provider


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _scalars(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _plan(name: PlanName) -> SubscriptionPlan:
    return SubscriptionPlan(id=uuid.uuid4(), name=name, display_name=name.value.capitalize())


def _sub(tenant_id, plan_id, status=SubscriptionStatus.ACTIVE) -> Subscription:
    now = datetime.now(UTC)
    return Subscription(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        plan_id=plan_id,
        status=status,
        current_period_start=now - timedelta(days=14, hours=12),
        current_period_end=now + timedelta(days=15, hours=12),
        next_charge_at=now + timedelta(days=15, hours=12),
        cancel_at_period_end=False,
        payment_token_id=None,
    )


def _history(tenant_id, *, change_type=PlanChangeType.DOWNGRADE, status=PlanChangeStatus.PENDING) -> PlanChangeHistory:
    now = datetime.now(UTC)
    return PlanChangeHistory(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        from_plan=PlanName.PREMIUM,
        to_plan=PlanName.BASIC,
        change_type=change_type,
        effective_at=now + timedelta(days=15),
        requested_at=now,
        requested_by=None,
        status=status,
        proration_details={},
        created_at=now,
    )


class TestChangePlan:
    async def test_upgrade_returns_payment_url(self, client, app):
        """AC1 — upgrade bez zapisanej metody → checkout tpay z kwotą prorated."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        _override_provider(app)
        basic = _plan(PlanName.BASIC)
        sub = _sub(tid, basic.id)
        # kolejność: locked sub → plan aktualny → pending change (brak)
        db.execute = AsyncMock(side_effect=[_scalar(sub), _scalar(basic), _scalar(None)])

        resp = await client.post("/api/v1/billing/subscription/change", json={"plan": "premium"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["change_type"] == "upgrade"
        assert body["payment_required"] is True
        assert body["payment_url"].startswith("https://")
        assert Decimal(body["amount"]) > 0
        assert body["change"]["from_plan"] == "basic"
        assert body["change"]["to_plan"] == "premium"
        assert body["change"]["status"] == "pending"

    async def test_downgrade_scheduled_locally_no_tpay(self, client, app):
        """AC2 — downgrade czysto lokalny: bez wywołań tpay, efekt na koniec okresu."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        provider = _override_provider(app)
        premium = _plan(PlanName.PREMIUM)
        sub = _sub(tid, premium.id)
        db.execute = AsyncMock(side_effect=[_scalar(sub), _scalar(premium), _scalar(None)])

        resp = await client.post("/api/v1/billing/subscription/change", json={"plan": "basic"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["change_type"] == "downgrade"
        assert body["payment_required"] is False
        assert Decimal(body["amount"]) == Decimal("0.00")
        provider.create_checkout.assert_not_awaited()
        provider.charge_recurring.assert_not_awaited()
        assert sub.cancel_at_period_end is True
        assert sub.next_charge_at is None

    async def test_same_plan_returns_400(self, client, app):
        """Task 3.2 — zmiana na ten sam plan → 400."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        _override_provider(app)
        basic = _plan(PlanName.BASIC)
        db.execute = AsyncMock(side_effect=[_scalar(_sub(tid, basic.id)), _scalar(basic)])

        resp = await client.post("/api/v1/billing/subscription/change", json={"plan": "basic"})
        assert resp.status_code == 400

    async def test_downgrade_during_dunning_returns_409(self, client, app):
        """Task 3.2 — downgrade w grace period dunningu → 409."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        _override_provider(app)
        premium = _plan(PlanName.PREMIUM)
        sub = _sub(tid, premium.id, status=SubscriptionStatus.PAST_DUE)
        db.execute = AsyncMock(side_effect=[_scalar(sub), _scalar(premium)])

        resp = await client.post("/api/v1/billing/subscription/change", json={"plan": "basic"})
        assert resp.status_code == 409

    async def test_no_subscription_returns_404(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        _override_provider(app)
        db.execute = AsyncMock(side_effect=[_scalar(None)])

        resp = await client.post("/api/v1/billing/subscription/change", json={"plan": "premium"})
        assert resp.status_code == 404

    async def test_non_owner_gets_403(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")
        resp = await client.post("/api/v1/billing/subscription/change", json={"plan": "premium"})
        assert resp.status_code == 403

    async def test_provider_error_returns_502(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        provider = _override_provider(app)
        provider.create_checkout = AsyncMock(side_effect=RuntimeError("tpay down"))
        basic = _plan(PlanName.BASIC)
        db.execute = AsyncMock(side_effect=[_scalar(_sub(tid, basic.id)), _scalar(basic), _scalar(None)])

        resp = await client.post("/api/v1/billing/subscription/change", json={"plan": "premium"})
        assert resp.status_code == 502
        db.rollback.assert_awaited()


class TestCancelPendingChange:
    async def test_cancel_restores_schedule(self, client, app):
        """AC3 — rezygnacja: rekord canceled + przywrócony harmonogram."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        pending = _history(tid)
        sub = _sub(tid, uuid.uuid4())
        sub.cancel_at_period_end = True
        sub.next_charge_at = None
        db.execute = AsyncMock(side_effect=[_scalar(pending), _scalar(sub)])

        resp = await client.post("/api/v1/billing/subscription/change/cancel-pending")

        assert resp.status_code == 200
        assert resp.json()["status"] == "canceled"
        assert sub.cancel_at_period_end is False
        assert sub.next_charge_at == sub.current_period_end

    async def test_no_pending_returns_404(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.execute = AsyncMock(side_effect=[_scalar(None)])

        resp = await client.post("/api/v1/billing/subscription/change/cancel-pending")
        assert resp.status_code == 404

    async def test_non_owner_gets_403(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")
        resp = await client.post("/api/v1/billing/subscription/change/cancel-pending")
        assert resp.status_code == 403


class TestChangeHistory:
    async def test_returns_records(self, client, app):
        """AC4 — historia zmian planu tenanta."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        record = _history(tid, status=PlanChangeStatus.COMPLETED)
        db.execute = AsyncMock(side_effect=[_scalars([record])])

        resp = await client.get("/api/v1/billing/subscription/history")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["from_plan"] == "premium"
        assert body[0]["to_plan"] == "basic"
        assert body[0]["change_type"] == "downgrade"
        assert body[0]["status"] == "completed"

    async def test_non_owner_gets_403(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="user")
        resp = await client.get("/api/v1/billing/subscription/history")
        assert resp.status_code == 403


class TestProrationPreview:
    async def test_upgrade_preview(self, client, app):
        """AC5 — lokalny podgląd kwoty prorated (bez API tpay)."""
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        _override_provider(app)
        basic = _plan(PlanName.BASIC)
        db.execute = AsyncMock(side_effect=[_scalar(_sub(tid, basic.id)), _scalar(basic)])

        resp = await client.get("/api/v1/billing/subscription/proration", params={"plan": "premium"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["change_type"] == "upgrade"
        assert Decimal(body["amount"]) > 0
        assert body["current_plan"] == "basic"
        assert body["new_plan"] == "premium"
        assert body["currency"] == "PLN"

    async def test_downgrade_preview_zero(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        premium = _plan(PlanName.PREMIUM)
        db.execute = AsyncMock(side_effect=[_scalar(_sub(tid, premium.id)), _scalar(premium)])

        resp = await client.get("/api/v1/billing/subscription/proration", params={"plan": "basic"})

        assert resp.status_code == 200
        assert Decimal(resp.json()["amount"]) == Decimal("0.00")

    async def test_same_plan_returns_400(self, client, app):
        user = make_user()
        db = AsyncMock()
        tid = _override_auth(app, user, db)
        basic = _plan(PlanName.BASIC)
        db.execute = AsyncMock(side_effect=[_scalar(_sub(tid, basic.id)), _scalar(basic)])

        resp = await client.get("/api/v1/billing/subscription/proration", params={"plan": "basic"})
        assert resp.status_code == 400
