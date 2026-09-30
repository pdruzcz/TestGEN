"""Integration tests for the admin CVE pipeline routes — Story 4.12.

Covers status / logs / trigger. The DB session and Celery dispatch are mocked so
the tests exercise routing, admin authorization and serialization.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


def _override_admin(app, user, db):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = None
        request.state.role = "admin"
        request.state.is_admin = True
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db


def _log(**kw):
    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        status=kw.get("status", "completed"),
        started_at=kw.get("started_at", datetime(2026, 6, 1, tzinfo=UTC)),
        completed_at=kw.get("completed_at", datetime(2026, 6, 1, 1, tzinfo=UTC)),
        total_new=kw.get("total_new", 5),
        total_updated=kw.get("total_updated", 3),
        affected_projects=kw.get("affected_projects", 2),
        sources_status=kw.get(
            "sources_status",
            {"nvd": {"ok": True, "fetched": 10, "error": None}},
        ),
        errors=kw.get("errors"),
    )


class TestStatus:
    async def test_status_returns_latest_run(self, client, app):
        user = make_user()
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = _log()
        db.execute.return_value = result
        _override_admin(app, user, db)

        response = await client.get("/api/v1/admin/cve-pipeline/status")

        assert response.status_code == 200
        body = response.json()
        assert body["last_status"] == "completed"
        assert body["total_new"] == 5
        assert body["sources_status"]["nvd"]["fetched"] == 10
        app.dependency_overrides = {}

    async def test_status_empty_when_no_runs(self, client, app):
        user = make_user()
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result
        _override_admin(app, user, db)

        response = await client.get("/api/v1/admin/cve-pipeline/status")

        assert response.status_code == 200
        assert response.json()["last_status"] is None
        app.dependency_overrides = {}

    async def test_status_forbidden_for_non_admin(self, client, app):
        from fastapi import Request

        from app.core.dependencies import get_current_user, get_db

        user = make_user()
        db = AsyncMock()

        async def override_user(request: Request):
            request.state.role = "user"
            request.state.is_admin = False
            return user

        async def override_db():
            yield db

        app.dependency_overrides[get_current_user] = override_user
        app.dependency_overrides[get_db] = override_db

        response = await client.get("/api/v1/admin/cve-pipeline/status")

        assert response.status_code == 403
        app.dependency_overrides = {}


class TestLogs:
    async def test_logs_returns_history(self, client, app):
        user = make_user()
        db = AsyncMock()
        db.scalar.return_value = 2
        result = MagicMock()
        result.scalars.return_value.all.return_value = [_log(), _log(status="failed")]
        db.execute.return_value = result
        _override_admin(app, user, db)

        response = await client.get("/api/v1/admin/cve-pipeline/logs")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["logs"]) == 2
        app.dependency_overrides = {}


class TestTrigger:
    async def test_trigger_enqueues_update(self, client, app, monkeypatch):
        user = make_user()
        db = AsyncMock()
        _override_admin(app, user, db)

        fake = MagicMock()
        fake.delay.return_value = SimpleNamespace(id="task-123")
        monkeypatch.setattr("app.workers.cve_tasks.update_cve_database", fake)

        response = await client.post("/api/v1/admin/cve-pipeline/trigger")

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "queued"
        assert body["task_id"] == "task-123"
        fake.delay.assert_called_once()
        app.dependency_overrides = {}

    async def test_trigger_handles_broker_failure(self, client, app, monkeypatch):
        user = make_user()
        db = AsyncMock()
        _override_admin(app, user, db)

        fake = MagicMock()
        fake.delay.side_effect = RuntimeError("broker down")
        monkeypatch.setattr("app.workers.cve_tasks.update_cve_database", fake)

        response = await client.post("/api/v1/admin/cve-pipeline/trigger")

        assert response.status_code == 202
        assert response.json()["status"] == "error"
        app.dependency_overrides = {}
