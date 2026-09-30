"""Integration tests for code error routes — Epic 5, Stories 5.4 + 5.10.

Covers POST /code-errors/scan (dead_code category, Story 5.10),
GET /code-errors (status/fingerprint serialization), and the triage
PATCH endpoint (false_positive, AC4). Celery task and DB are patched —
routing + serialization only.
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


def _override_auth(app, user, db, tenant_id=None):
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    _tenant_id = tenant_id or uuid.uuid4()
    user._tenant_id = _tenant_id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = _tenant_id
        request.state.role = "user"
        request.state.is_admin = False
        return user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return _tenant_id


def _mock_db_execute(return_value):
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=return_value)
    result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[return_value] if return_value else []))
    )
    result.scalar_one = MagicMock(return_value=return_value)
    return AsyncMock(return_value=result)


def _make_error(tenant_id, project_id, **kw):
    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        tenant_id=tenant_id,
        project_id=project_id,
        source_file_id=kw.get("source_file_id"),
        category=kw.get("category", "dead_code"),
        message=kw.get("message", "Funkcja '_x' nie jest wywoływana nigdzie w projekcie (0 wywołań)"),
        file_path=kw.get("file_path", "app.py"),
        line_start=kw.get("line_start", 1),
        line_end=kw.get("line_end", 2),
        severity=kw.get("severity", "warning"),
        rule_id=kw.get("rule_id", "DEAD_CODE"),
        suggestion=kw.get("suggestion", "Sprawdź i usuń albo oznacz `@internal`"),
        context=kw.get("context"),
        status=kw.get("status", "open"),
        fingerprint=kw.get("fingerprint", "app.py:_x:abcd1234"),
        created_at=kw.get("created_at", datetime.now(UTC)),
    )


class TestStartCodeErrorScan:
    async def test_scan_accepts_dead_code_category(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        db = AsyncMock()
        db.execute = _mock_db_execute(SimpleNamespace(id=project_id, tenant_id=tenant_id))
        _override_auth(app, user, db, tenant_id)

        mock_task = MagicMock()
        mock_task.id = "task-123"

        with patch("app.workers.tasks.code_error_tasks.run_code_error_detection") as mock_delay:
            mock_delay.delay.return_value = mock_task
            resp = await client.post(
                f"/api/v1/projects/{project_id}/code-errors/scan",
                json={"categories": ["dead_code"]},
            )

        assert resp.status_code == 202
        assert resp.json()["task_id"] == "task-123"
        args, _kwargs = mock_delay.delay.call_args
        assert args[2] == ["dead_code"]

    async def test_scan_default_categories_include_dead_code(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        db = AsyncMock()
        db.execute = _mock_db_execute(SimpleNamespace(id=project_id, tenant_id=tenant_id))
        _override_auth(app, user, db, tenant_id)

        mock_task = MagicMock()
        mock_task.id = "task-456"

        with patch("app.workers.tasks.code_error_tasks.run_code_error_detection") as mock_delay:
            mock_delay.delay.return_value = mock_task
            resp = await client.post(
                f"/api/v1/projects/{project_id}/code-errors/scan",
                json={},
            )

        assert resp.status_code == 202
        args, _ = mock_delay.delay.call_args
        assert "dead_code" in args[2]


class TestListCodeErrors:
    async def test_list_serializes_status_and_fingerprint(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        error = _make_error(tenant_id, project_id)

        db = AsyncMock()
        # 1) verify access, 2) count, 3) items, 4+) summary rows
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=1)
        items_result = MagicMock()
        items_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[error])))
        project_result = MagicMock()
        project_result.scalar_one_or_none = MagicMock(return_value=SimpleNamespace(id=project_id, tenant_id=tenant_id))
        db.execute = AsyncMock(side_effect=[project_result, count_result, items_result, items_result])
        _override_auth(app, user, db, tenant_id)

        resp = await client.get(f"/api/v1/projects/{project_id}/code-errors")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        row = data["errors"][0]
        assert row["category"] == "dead_code"
        assert row["status"] == "open"
        assert row["fingerprint"] == "app.py:_x:abcd1234"
        assert data["summary"]["by_category"]["dead_code"] >= 1


class TestUpdateCodeErrorStatus:
    async def test_patch_false_positive(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        error = _make_error(tenant_id, project_id)

        db = AsyncMock()
        db.get = AsyncMock(return_value=error)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        _override_auth(app, user, db, tenant_id)

        resp = await client.patch(
            f"/api/v1/projects/{project_id}/code-errors/{error.id}/status",
            json={"status": "false_positive"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "false_positive"
        assert error.status == "false_positive"

    async def test_patch_unknown_error_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        _override_auth(app, user, db, tenant_id)

        resp = await client.patch(
            f"/api/v1/projects/{project_id}/code-errors/{uuid.uuid4()}/status",
            json={"status": "false_positive"},
        )
        assert resp.status_code == 404

    async def test_patch_invalid_status_422(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        error = _make_error(tenant_id, project_id)

        db = AsyncMock()
        db.get = AsyncMock(return_value=error)
        _override_auth(app, user, db, tenant_id)

        resp = await client.patch(
            f"/api/v1/projects/{project_id}/code-errors/{error.id}/status",
            json={"status": "dismissed"},
        )
        assert resp.status_code == 422
