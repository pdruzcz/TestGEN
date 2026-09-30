"""API tests for billing routes — Story 7.1 (AC4).

GET /api/v1/billing/plans, /subscription, /usage. DB session is mocked;
auth via dependency_overrides (wzorzec test_dashboard_routes).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.models.tenant import Tenant
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db, tenant_id=None, with_tenant=True):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = tenant_id or uuid.uuid4()
    if with_tenant:
        user._tenant_id = _tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = _tenant_id
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return _tenant_id


def _make_plan(name: PlanName, sort_order: int, price: str, features: dict) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=uuid.uuid4(),
        name=name,
        display_name=name.value.capitalize(),
        price_monthly=Decimal(price),
        currency="PLN",
        features=features,
        is_active=True,
        sort_order=sort_order,
    )


def _exec_all(items: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = items
    return r


def _exec_scalar_one_or_none(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _three_plans() -> list[SubscriptionPlan]:
    return [
        _make_plan(PlanName.FREEMIUM, 0, "0.00", {"analyses": 10}),
        _make_plan(PlanName.BASIC, 1, "30.00", {"analyses": 50}),
        _make_plan(PlanName.PREMIUM, 2, "50.00", {"analyses": None}),
    ]


class TestGetPlans:
    """AC4 — GET /billing/plans z current_plan i linkami prawnymi (tpay)."""

    async def test_plans_returns_three_plans_with_current(self, client, app):
        user = make_user()
        plans = _three_plans()
        sub = Subscription(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            plan_id=plans[1].id,  # Basic
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC),
            cancel_at_period_end=False,
        )
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_exec_all(plans), _exec_scalar_one_or_none(sub)])
        _override_auth(app, user, db)

        resp = await client.get("/api/v1/billing/plans")

        assert resp.status_code == 200
        body = resp.json()
        assert [p["name"] for p in body["plans"]] == ["freemium", "basic", "premium"]
        assert body["plans"][1]["price_monthly"] == "30.00"
        assert body["current_plan"] == "basic"
        # Wymóg tpay: linki prawne z konfiguracji, nie hardcode
        assert body["terms_url"] == "https://test-gen.pl/regulamin/"
        assert body["privacy_policy_url"] == "https://test-gen.pl/polityka/"

    async def test_plans_without_subscription_falls_back_to_tenant_plan(self, client, app):
        """Plan startowy (Freemium) nie ma wiersza subskrypcji — fallback do
        kolumny tenants.plan, żeby karta aktualnego planu się wyróżniała
        (fix 2026-09-14: wcześniej current_plan=null dla Freemium)."""
        user = make_user()
        tenant = Tenant(slug="t-freemium", plan=PlanName.FREEMIUM)
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_all(_three_plans()),
                _exec_scalar_one_or_none(None),  # brak subskrypcji
                _exec_scalar_one_or_none(tenant),  # fallback: tenants.plan
            ]
        )
        _override_auth(app, user, db)

        resp = await client.get("/api/v1/billing/plans")

        assert resp.status_code == 200
        assert resp.json()["current_plan"] == "freemium"

    async def test_plans_without_subscription_and_tenant_current_null(self, client, app):
        """Defensywnie: brak subskrypcji i brak wiersza tenanta → null."""
        user = make_user()
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _exec_all(_three_plans()),
                _exec_scalar_one_or_none(None),
                _exec_scalar_one_or_none(None),
            ]
        )
        _override_auth(app, user, db)

        resp = await client.get("/api/v1/billing/plans")

        assert resp.status_code == 200
        assert resp.json()["current_plan"] is None

    async def test_plans_requires_tenant_context(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, with_tenant=False)

        resp = await client.get("/api/v1/billing/plans")

        assert resp.status_code == 403


class TestGetSubscription:
    async def test_subscription_found(self, client, app):
        user = make_user()
        plan = SubscriptionPlan(
            id=uuid.uuid4(),
            name=PlanName.BASIC,
            display_name="Basic",
            price_monthly=Decimal("30.00"),
            currency="PLN",
            is_active=True,
        )
        sub = Subscription(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC),
            cancel_at_period_end=False,
        )
        db = AsyncMock()
        # 7.7 (AC3): detail = subskrypcja + plan + pending change (bez metody)
        db.execute = AsyncMock(
            side_effect=[
                _exec_scalar_one_or_none(sub),
                _exec_scalar_one_or_none(plan),
                _exec_scalar_one_or_none(None),
            ]
        )
        _override_auth(app, user, db)

        resp = await client.get("/api/v1/billing/subscription")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "active"
        assert body["cancel_at_period_end"] is False
        assert body["plan_name"] == "basic"

    async def test_subscription_not_found_404(self, client, app):
        user = make_user()
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[_exec_scalar_one_or_none(None)])
        _override_auth(app, user, db)

        resp = await client.get("/api/v1/billing/subscription")

        assert resp.status_code == 404


class TestGetUsage:
    """Story 7.8 Task 4 — GET /usage zwraca liczniki z limitami i procentem."""

    async def test_usage_returns_counters_with_limits_and_percent(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        usage = {
            "analyses": {"used": 7, "limit": 10, "percent": 70.0},
            "test_cases": {"used": 0, "limit": None, "percent": None},
            "storage_bytes": {"used": 1024, "limit": 104857600, "percent": 0.0},
            "files_per_analysis": {"used": 0, "limit": 20, "percent": 0.0},
        }
        with patch("app.api.routes.billing.QuotaService") as mock_cls:
            svc = MagicMock()
            svc.get_usage = AsyncMock(return_value=usage)
            mock_cls.return_value = svc

            resp = await client.get("/api/v1/billing/usage")

        assert resp.status_code == 200
        body = resp.json()
        assert body["analyses"] == {"used": 7, "limit": 10, "percent": 70.0}
        assert body["test_cases"]["limit"] is None  # unlimited
        assert body["test_cases"]["percent"] is None
        assert body["storage_bytes"]["used"] == 1024

    async def test_usage_empty(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db)

        with patch("app.api.routes.billing.QuotaService") as mock_cls:
            svc = MagicMock()
            svc.get_usage = AsyncMock(return_value={})
            mock_cls.return_value = svc

            resp = await client.get("/api/v1/billing/usage")

        assert resp.status_code == 200
        assert resp.json() == {}
