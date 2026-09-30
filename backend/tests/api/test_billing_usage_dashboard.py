"""API tests — Story 7.9 (AC5): GET /billing/usage/dashboard + /usage/history.

DB mockowana; QuotaService patchowany (wzorzec test_billing_plans.TestGetUsage).
"""

import uuid
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.usage import CounterType
from app.services.billing.quota_service import (
    DashboardCounter,
    DashboardData,
    ForecastData,
    UsageDataPoint,
)
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db, with_tenant=True):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = uuid.uuid4()
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


def _dashboard_data() -> DashboardData:
    now = datetime.now(UTC)
    return DashboardData(
        current_period_start=now,
        current_period_end=now.replace(day=28),
        plan="freemium",
        counters=[
            DashboardCounter(CounterType.ANALYSES, 7, 10, 70.0),
            DashboardCounter(CounterType.TEST_CASES, 0, None, None),
            DashboardCounter(CounterType.STORAGE_BYTES, 52428800, 524288000, 10.0),
            DashboardCounter(CounterType.FILES_PER_ANALYSIS, 0, 5, 0.0),
        ],
        forecast=ForecastData(
            counter_type=CounterType.ANALYSES,
            limit_date=date(2026, 9, 25),
            avg_daily=1.0,
            days_to_limit=3,
            exceeds_before_period_end=True,
        ),
        days_remaining=18,
    )


class TestGetUsageDashboard:
    """AC5 — GET /usage/dashboard: current_period, plan, counters[], forecast, days_remaining."""

    async def test_dashboard_zwraca_pelny_ksztalt(self, client, app):
        db = AsyncMock()
        tid = _override_auth(app, make_user(), db)
        with patch("app.api.routes.billing.QuotaService") as mock_cls:
            svc = MagicMock()
            svc.get_dashboard_data = AsyncMock(return_value=_dashboard_data())
            mock_cls.return_value = svc

            resp = await client.get("/api/v1/billing/usage/dashboard")

        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {
            "current_period",
            "plan",
            "counters",
            "forecast",
            "days_remaining",
        }
        assert body["plan"] == "freemium"
        assert body["days_remaining"] == 18
        assert set(body["current_period"]) == {"start", "end"}
        analyses = next(c for c in body["counters"] if c["type"] == "analyses")
        assert analyses == {"type": "analyses", "value": 7, "limit": 10, "percentage": 70.0}
        test_cases = next(c for c in body["counters"] if c["type"] == "test_cases")
        assert test_cases["limit"] is None and test_cases["percentage"] is None
        assert body["forecast"]["limit_date"] == "2026-09-25"
        assert body["forecast"]["exceeds_before_period_end"] is True
        svc.get_dashboard_data.assert_awaited_once_with(tid)

    async def test_dashboard_bez_prognozy_forecast_none(self, client, app):
        db = AsyncMock()
        _override_auth(app, make_user(), db)
        data = _dashboard_data()
        object.__setattr__(data, "forecast", None)  # frozen dataclass
        with patch("app.api.routes.billing.QuotaService") as mock_cls:
            svc = MagicMock()
            svc.get_dashboard_data = AsyncMock(return_value=data)
            mock_cls.return_value = svc

            resp = await client.get("/api/v1/billing/usage/dashboard")

        assert resp.status_code == 200
        assert resp.json()["forecast"] is None

    async def test_dashboard_brak_subskrypcji_404(self, client, app):
        from app.core.exceptions import NotFoundError

        db = AsyncMock()
        _override_auth(app, make_user(), db)
        with patch("app.api.routes.billing.QuotaService") as mock_cls:
            svc = MagicMock()
            svc.get_dashboard_data = AsyncMock(side_effect=NotFoundError("Subscription not found"))
            mock_cls.return_value = svc

            resp = await client.get("/api/v1/billing/usage/dashboard")

        assert resp.status_code == 404

    async def test_dashboard_wymaga_kontekstu_tenanta_403(self, client, app):
        db = AsyncMock()
        _override_auth(app, make_user(), db, with_tenant=False)

        resp = await client.get("/api/v1/billing/usage/dashboard")

        assert resp.status_code == 403


class TestGetUsageHistory:
    """AC3 — GET /usage/history?counter_type=&days= — punkty do wykresu."""

    async def test_history_zwraca_punkty(self, client, app):
        db = AsyncMock()
        tid = _override_auth(app, make_user(), db)
        points = [
            UsageDataPoint(date=date(2026, 9, 8), value=3),
            UsageDataPoint(date=date(2026, 9, 9), value=5),
            UsageDataPoint(date=date(2026, 9, 10), value=6),
        ]
        with patch("app.api.routes.billing.QuotaService") as mock_cls:
            svc = MagicMock()
            svc.get_usage_history = AsyncMock(return_value=points)
            mock_cls.return_value = svc

            resp = await client.get(
                "/api/v1/billing/usage/history",
                params={"counter_type": "analyses", "days": 30},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["counter_type"] == "analyses"
        assert body["days"] == 30
        assert body["points"] == [
            {"date": "2026-09-08", "value": 3},
            {"date": "2026-09-09", "value": 5},
            {"date": "2026-09-10", "value": 6},
        ]
        svc.get_usage_history.assert_awaited_once_with(tid, CounterType.ANALYSES, days=30)

    async def test_history_nieznany_counter_type_422(self, client, app):
        db = AsyncMock()
        _override_auth(app, make_user(), db)

        resp = await client.get(
            "/api/v1/billing/usage/history",
            params={"counter_type": "users"},  # usunięty w CR#2 — nie istnieje
        )

        assert resp.status_code == 422

    async def test_history_days_poza_zakresem_422(self, client, app):
        db = AsyncMock()
        _override_auth(app, make_user(), db)

        resp = await client.get(
            "/api/v1/billing/usage/history",
            params={"counter_type": "analyses", "days": 400},
        )

        assert resp.status_code == 422
