"""API tests — Story 7.13: GET /billing/features + 402 na gated endpointach.

DB mockowana; auth przez dependency_overrides (wzorzec test_billing_plans).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.subscription_plan import PlanName, SubscriptionPlan
from app.models.tenant import PlanType
from app.seed.seed_plans import GATED_MODULES
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db, tenant_id=None, with_tenant=True, role="owner"):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = tenant_id or uuid.uuid4()
    if with_tenant:
        user._tenant_id = _tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = _tenant_id
        request.state.role = role
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return _tenant_id


def _scalar(item) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = item
    return r


def _plan_row(name: PlanName) -> SubscriptionPlan:
    return SubscriptionPlan(
        id=uuid.uuid4(),
        name=name,
        display_name=name.value.capitalize(),
        features={"gated_modules": dict(GATED_MODULES)},
    )


def _gating_db(plan: PlanType) -> AsyncMock:
    """execute → [Tenant.plan, SubscriptionPlan] (kolejność zapytań serwisu)."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(plan), _scalar(_plan_row(PlanName(plan.value)))])
    return db


class TestGetFeatures:
    """GET /billing/features — status modułów per plan (AC4)."""

    async def test_freemium_all_gated_locked(self, client, app):
        user = make_user()
        _override_auth(app, user, _gating_db(PlanType.FREEMIUM))

        resp = await client.get("/api/v1/billing/features")

        assert resp.status_code == 200
        body = resp.json()
        assert body["current_plan"] == "freemium"
        modules = {m["key"]: m for m in body["modules"]}
        assert modules["documentation"] == {"key": "documentation", "locked": True, "required_plan": "basic"}
        assert modules["security"]["required_plan"] == "premium"
        assert modules["code_analysis"]["locked"] is False
        assert len(body["modules"]) == len(GATED_MODULES)

    async def test_basic_unlocks_basic_modules(self, client, app):
        user = make_user()
        _override_auth(app, user, _gating_db(PlanType.BASIC))

        resp = await client.get("/api/v1/billing/features")

        assert resp.status_code == 200
        modules = {m["key"]: m for m in resp.json()["modules"]}
        assert modules["uml"]["locked"] is False
        assert modules["gui"]["locked"] is False
        assert modules["security"]["locked"] is True

    async def test_premium_unlocks_all(self, client, app):
        user = make_user()
        _override_auth(app, user, _gating_db(PlanType.PREMIUM))

        resp = await client.get("/api/v1/billing/features")

        assert resp.status_code == 200
        assert all(m["locked"] is False for m in resp.json()["modules"])

    async def test_requires_tenant_context(self, client, app):
        user = make_user()
        _override_auth(app, user, AsyncMock(), with_tenant=False)

        resp = await client.get("/api/v1/billing/features")

        assert resp.status_code == 403


class TestGatedRoute402:
    """402 feature_requires_plan na gated endpointach (AC2/AC3)."""

    async def test_uml_analyze_locked_for_freemium(self, client, app):
        user = make_user()
        _override_auth(app, user, _gating_db(PlanType.FREEMIUM))

        resp = await client.post(f"/api/v1/projects/{uuid.uuid4()}/uml/analyze", json={})

        assert resp.status_code == 402
        body = resp.json()
        assert body["error"] == "feature_requires_plan"
        assert body["feature"] == "uml"
        assert body["required_plan"] == "basic"
        assert body["upgrade_url"] == "/billing/plans"

    async def test_security_scan_locked_for_basic(self, client, app):
        user = make_user()
        _override_auth(app, user, _gating_db(PlanType.BASIC))

        resp = await client.post(f"/api/v1/projects/{uuid.uuid4()}/security-scan", json={})

        assert resp.status_code == 402
        body = resp.json()
        assert body["error"] == "feature_requires_plan"
        assert body["feature"] == "security"
        assert body["required_plan"] == "premium"

    async def test_gap_analysis_locked_for_basic(self, client, app):
        user = make_user()
        _override_auth(app, user, _gating_db(PlanType.BASIC))

        resp = await client.post(f"/api/v1/projects/{uuid.uuid4()}/gap-analysis", json={})

        assert resp.status_code == 402
        body = resp.json()
        assert body["feature"] == "code_doc_consistency"
        assert body["required_plan"] == "premium"

    async def test_heal_locked_for_freemium(self, client, app):
        """Self-healing (GUI) — spięcie hooka TODO(7.13) z gatingiem."""
        user = make_user()
        # execute → [Project (access check), Tenant.plan, SubscriptionPlan]
        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[
                _scalar(MagicMock()),  # project istnieje
                _scalar(PlanType.FREEMIUM),
                _scalar(_plan_row(PlanName.FREEMIUM)),
            ]
        )
        _override_auth(app, user, db)

        resp = await client.post(
            f"/api/v1/projects/{uuid.uuid4()}/tests/heal",
            json={"version_a": "a", "version_b": "b"},
        )

        assert resp.status_code == 402
        assert resp.json()["feature"] == "gui"
