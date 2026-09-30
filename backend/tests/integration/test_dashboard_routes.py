"""Integration tests for dashboard routes — Epic 6, Story 6.1.

Tests GET /dashboard/summary (aggregated payload, role-gated plan_usage)
and GET /dashboard/audit-logs (activity feed). DB session is mocked.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db, tenant_id=None, role="user", is_admin=False):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = tenant_id or uuid.uuid4()
    user._tenant_id = _tenant_id
    user._tenant_role = role
    user.is_admin = is_admin

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = _tenant_id
        request.state.role = role
        request.state.is_admin = is_admin
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return _tenant_id


def _result_with_all(rows: list | None = None, scalar_one_val=None, scalar_one_or_none_val=None):
    """Build a MagicMock db.execute result supporting .all(), .scalar_one(), .scalar_one_or_none()."""
    result = MagicMock()
    result.all = MagicMock(return_value=rows or [])
    result.scalar_one = MagicMock(return_value=scalar_one_val)
    result.scalar_one_or_none = MagicMock(return_value=scalar_one_or_none_val)
    return result


class TestDashboardSummary:
    """GET /dashboard/summary — aggregated dashboard payload."""

    async def test_summary_returns_projects_stats_and_plan_usage_for_owner(self, client, app):
        user = make_user(email="owner@example.com")
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        project_row = SimpleNamespace(
            id=uuid.uuid4(),
            name="Project A",
            status=SimpleNamespace(value="active"),
            compliance_score=87.5,
            last_analysis_at=datetime.now(UTC),
            test_cases_count=12,
        )

        # 1) _fetch_project_rows
        proj_result = MagicMock()
        proj_scalars = MagicMock()
        proj_scalars.all = MagicMock(return_value=[project_row])
        proj_result.all = MagicMock(return_value=[project_row])

        # 2) analyses_this_month scalar_one
        analyses_result = MagicMock()
        analyses_result.scalar_one = MagicMock(return_value=3)

        # 3) avg compliance scalar_one_or_none
        avg_result = MagicMock()
        avg_result.scalar_one_or_none = MagicMock(return_value=92.0)

        # 4) total test cases scalar_one (Story 6.1 AC2)
        tc_total_result = MagicMock()
        tc_total_result.scalar_one = MagicMock(return_value=42)

        # 5) active users scalar_one
        users_result = MagicMock()
        users_result.scalar_one = MagicMock(return_value=5)

        # 6) tenant plan scalar_one_or_none
        from app.models.tenant import PlanType

        tenant_result = MagicMock()
        tenant_result.scalar_one_or_none = MagicMock(return_value=PlanType.PREMIUM)

        db.execute = AsyncMock(
            side_effect=[
                proj_result,
                analyses_result,
                avg_result,
                tc_total_result,
                users_result,
                tenant_result,
            ]
        )

        _override_auth(app, user, db, tenant_id, role="owner")

        # Mock QuotaService.get_usage to avoid Redis
        with patch("app.services.dashboard_service.QuotaService") as mock_quota:
            mock_quota.return_value.get_usage.return_value = {
                "plan": "premium",
                "analyses_used": 3,
                "analyses_limit": 50,
            }
            resp = await client.get("/api/v1/dashboard/summary")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["projects"]) == 1
        proj = data["projects"][0]
        assert proj["name"] == "Project A"
        assert proj["test_cases_count"] == 12
        assert proj["compliance_score"] == 87.5
        assert proj["status"] == "active"

        stats = data["statistics"]
        assert stats["total_projects"] == 1
        assert stats["analyses_this_month"] == 3
        assert stats["avg_compliance"] == 92.0
        # Story 6.1 AC2 — 4. karta to liczba wygenerowanych test case'ów.
        assert stats["total_test_cases"] == 42
        assert stats["active_users"] == 5

        plan = data["plan_usage"]
        assert plan is not None
        assert plan["plan"] == "premium"
        assert plan["analyses_used"] == 3
        assert plan["analyses_limit"] == 50
        assert plan["projects_count"] == 1

    async def test_summary_hides_plan_usage_for_member(self, client, app):
        user = make_user(email="user@example.com")
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        empty_result = MagicMock()
        empty_result.all = MagicMock(return_value=[])

        analyses_result = MagicMock()
        analyses_result.scalar_one = MagicMock(return_value=0)

        avg_result = MagicMock()
        avg_result.scalar_one_or_none = MagicMock(return_value=None)

        tc_total_result = MagicMock()
        tc_total_result.scalar_one = MagicMock(return_value=0)

        users_result = MagicMock()
        users_result.scalar_one = MagicMock(return_value=1)

        db.execute = AsyncMock(
            side_effect=[
                empty_result,
                analyses_result,
                avg_result,
                tc_total_result,
                users_result,
            ]
        )

        _override_auth(app, user, db, tenant_id, role="user")

        resp = await client.get("/api/v1/dashboard/summary")

        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_usage"] is None
        assert data["statistics"]["total_projects"] == 0

    async def test_summary_no_tenant_returns_403(self, client, app):
        user = make_user()
        # No _tenant_id set → _tenant_of raises 403
        from app.core.dependencies import get_current_user, get_db

        async def override_user():
            user._tenant_id = None
            user._tenant_role = "user"
            return user

        async def override_db():
            yield AsyncMock()

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        resp = await client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 403


class TestDashboardAuditLogs:
    """GET /dashboard/audit-logs — activity feed."""

    async def test_audit_logs_returns_items(self, client, app):
        user = make_user()
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        log = SimpleNamespace(
            id=uuid.uuid4(),
            user_id=user.id,
            action="project.created",
            resource_type="project",
            resource_id=uuid.uuid4(),
            details={"name": "Project A"},
            created_at=datetime.now(UTC),
        )

        logs_result = MagicMock()
        logs_scalars = MagicMock()
        logs_scalars.all = MagicMock(return_value=[log])
        logs_result.scalars = MagicMock(return_value=logs_scalars)

        email_result = MagicMock()
        email_result.all = MagicMock(return_value=[(user.id, "user@example.com")])

        db.execute = AsyncMock(side_effect=[logs_result, email_result])

        _override_auth(app, user, db, tenant_id)

        resp = await client.get("/api/v1/dashboard/audit-logs")

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["action"] == "project.created"
        assert item["user_email"] == "user@example.com"
        assert item["resource_type"] == "project"

    async def test_audit_logs_empty_when_no_logs(self, client, app):
        user = make_user()
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        empty_result = MagicMock()
        empty_scalars = MagicMock()
        empty_scalars.all = MagicMock(return_value=[])
        empty_result.scalars = MagicMock(return_value=empty_scalars)

        db.execute = AsyncMock(return_value=empty_result)

        _override_auth(app, user, db, tenant_id)

        resp = await client.get("/api/v1/dashboard/audit-logs")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_audit_logs_invalid_limit_returns_422(self, client, app):
        user = make_user()
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        _override_auth(app, user, db, tenant_id)

        resp = await client.get("/api/v1/dashboard/audit-logs?limit=0")
        assert resp.status_code == 422

        resp2 = await client.get("/api/v1/dashboard/audit-logs?limit=100")
        assert resp2.status_code == 422
