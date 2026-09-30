"""Tests for POST /api/v1/tasks/{id}/cancel — Story 6.3 AC5."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_tenant
from app.main import create_app
from app.models.user_tenant import TenantRole
from tests.factories import make_tenant, make_user, make_user_tenant


@pytest.fixture
def app_with_task():
    app = create_app()

    tenant = make_tenant(name="Cancel Tenant")
    user = make_user(email="cancel@test.com", name="Cancel User")
    make_user_tenant(
        user_id=user.id,
        tenant_id=tenant.id,
        role=TenantRole.OWNER,
    )

    async def _override_user():
        return user

    def _override_tenant():
        return tenant.id

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_tenant] = _override_tenant

    yield app, tenant
    app.dependency_overrides.clear()


@pytest.fixture
async def task_client(app_with_task):
    app = app_with_task[0]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_cancel_task_marks_cancelled(task_client, app_with_task):
    """POST /tasks/{id}/cancel returns 202 with status='cancelled'."""
    _app, tenant = app_with_task
    task_id = "task-xyz"

    fake_status = {
        "task_id": task_id,
        "status": "running",
        "tenant_id": str(tenant.id),
        "progress": 25,
        "current_step": "analysis",
        "error": "",
        "result_url": "",
    }
    with (
        patch(
            "app.api.routes.tasks.TaskProgressService.get_task_status",
            return_value=fake_status,
        ),
        patch(
            "app.api.routes.tasks.TaskProgressService.cancel_task"
        ) as mock_cancel,
        patch(
            "app.api.routes.tasks.celery_app"
        ) as mock_celery,
    ):
        mock_celery.control.revoke = MagicMock()
        response = await task_client.post(f"/api/v1/tasks/{task_id}/cancel")

    assert response.status_code == 202
    body = response.json()
    assert body["task_id"] == task_id
    assert body["status"] == "cancelled"
    mock_cancel.assert_called_once_with(task_id)


@pytest.mark.asyncio
async def test_cancel_task_not_found(task_client):
    """404 when task doesn't exist."""
    with patch(
        "app.api.routes.tasks.TaskProgressService.get_task_status",
        return_value=None,
    ):
        response = await task_client.post(
            "/api/v1/tasks/nonexistent-task/cancel"
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_task_tenant_isolation(task_client):
    """404 when task belongs to a different tenant."""
    other_tenant_id = uuid.uuid4()
    fake_status = {
        "task_id": "task-other",
        "status": "running",
        "tenant_id": str(other_tenant_id),
        "progress": 0,
        "current_step": "",
        "error": "",
        "result_url": "",
    }
    with patch(
        "app.api.routes.tasks.TaskProgressService.get_task_status",
        return_value=fake_status,
    ):
        response = await task_client.post("/api/v1/tasks/task-other/cancel")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_task_revoke_called(task_client, app_with_task):
    """Cancel also revokes the Celery task (best-effort)."""
    _app, tenant = app_with_task
    task_id = "task-celery"

    fake_status = {
        "task_id": task_id,
        "status": "running",
        "tenant_id": str(tenant.id),
        "progress": 50,
        "current_step": "test_generation",
        "error": "",
        "result_url": "",
    }
    with (
        patch(
            "app.api.routes.tasks.TaskProgressService.get_task_status",
            return_value=fake_status,
        ),
        patch(
            "app.api.routes.tasks.TaskProgressService.cancel_task"
        ),
        patch(
            "app.api.routes.tasks.celery_app"
        ) as mock_celery,
    ):
        mock_celery.control.revoke = MagicMock()
        await task_client.post(f"/api/v1/tasks/{task_id}/cancel")

    mock_celery.control.revoke.assert_called_once_with(
        task_id, terminate=True
    )
