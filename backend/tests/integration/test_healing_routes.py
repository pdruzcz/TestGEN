"""Integration tests for self-healing routes — Epic 1, Story 1.51.

Patches the Celery task and DB so tests exercise routing, RBAC, plan gating
and serialization only (same convention as test_gap_analysis_routes).
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.healing_report import HealingStatus
from app.models.tenant import PlanType
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _override_auth(app, user, db, role="owner", tenant_id=None):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = tenant_id or uuid.uuid4()
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


def _res(value):
    r = MagicMock()
    r.scalar_one_or_none = MagicMock(return_value=value)
    r.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[value] if value else [])))
    return r


class TestStartHealing:
    @patch("app.workers.tasks.healing_tasks.run_healing_task")
    async def test_post_returns_202_with_task_and_report(self, mock_task, client, app):
        mock_task.delay.return_value = MagicMock(id="task-123")
        user = make_user()
        pid = uuid.uuid4()
        db = AsyncMock()
        tid = _override_auth(app, user, db, role="owner")

        project = SimpleNamespace(id=pid, tenant_id=tid)
        tenant = SimpleNamespace(plan=PlanType.PREMIUM)
        db.add = MagicMock()  # db.add is sync in production
        db.execute = AsyncMock(side_effect=[_res(project), _res(tenant)])

        resp = await client.post(
            f"/api/v1/projects/{pid}/tests/heal",
            json={"version_a": str(uuid.uuid4()), "version_b": str(uuid.uuid4())},
        )

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["task_id"] == "task-123"
        assert "report_id" in body
        assert body["status"] == "pending"
        mock_task.delay.assert_called_once()

    async def test_project_not_found_404(self, client, app):
        user = make_user()
        db = AsyncMock()
        _override_auth(app, user, db, role="owner")
        db.execute = AsyncMock(side_effect=[_res(None)])  # project missing

        resp = await client.post(
            f"/api/v1/projects/{uuid.uuid4()}/tests/heal",
            json={"version_a": str(uuid.uuid4()), "version_b": str(uuid.uuid4())},
        )
        assert resp.status_code == 404


class TestGetHealingReport:
    async def test_get_returns_report(self, client, app):
        user = make_user()
        pid = uuid.uuid4()
        rid = uuid.uuid4()
        db = AsyncMock()
        tid = _override_auth(app, user, db, role="user")

        project = SimpleNamespace(id=pid, tenant_id=tid)
        report = SimpleNamespace(
            id=rid,
            project_id=pid,
            version_a="v1",
            version_b="v2",
            status=HealingStatus.HEALED,
            stats={"total": 1, "healed": 1},
            created_at=datetime.now(UTC),
            items=[],
        )
        db.execute = AsyncMock(side_effect=[_res(project), _res(report)])

        resp = await client.get(f"/api/v1/projects/{pid}/healing/{rid}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "healed"


class TestDecideHealingItem:
    @patch("app.api.routes.healing.SelfHealingService")
    async def test_accept_applies_and_returns_200(self, mock_svc_cls, client, app):
        item = SimpleNamespace(
            id=uuid.uuid4(),
            report_id=uuid.uuid4(),
            status=HealingStatus.HEALED,
        )
        mock_svc_cls.return_value.apply_decision = AsyncMock(return_value=(item, True))

        user = make_user()
        pid = uuid.uuid4()
        db = AsyncMock()
        tid = _override_auth(app, user, db, role="owner")

        project = SimpleNamespace(id=pid, tenant_id=tid)
        db.execute = AsyncMock(side_effect=[_res(project), _res(item)])

        resp = await client.post(
            f"/api/v1/projects/{pid}/healing/{item.report_id}/items/{item.id}/decision",
            json={"action": "accept"},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["applied"] is True
        assert body["status"] == "healed"
