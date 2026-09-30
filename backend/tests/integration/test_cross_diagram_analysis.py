"""Integration tests for Story 3.7 cross-diagram analysis routes.

Covers POST /uml/analyze (202 async dispatch), GET /uml/flows (pagination) and
GET /uml/flows/{flow_id} (detail / 404). The Celery task and repository are
patched so the tests exercise the routing + serialization layer only.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.user_flow import FlowSourceType, FlowStatus
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


def _override_auth(app, user, tenant_id=None):
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
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    return _tenant_id


def _make_flow(name="Logowanie", steps=1):
    flow = SimpleNamespace()
    flow.id = uuid.uuid4()
    flow.name = name
    flow.source_type = FlowSourceType.UML
    flow.source_ids = ["d1"]
    flow.status = FlowStatus.DRAFT
    flow.warnings = None
    flow.created_at = None
    flow.flow_steps = [
        SimpleNamespace(
            id=uuid.uuid4(),
            sequence=i + 1,
            action=f"krok {i + 1}",
            actor="User",
            target_element=None,
            expected_result=None,
            source_diagram_id=None,
            source="native",
        )
        for i in range(steps)
    ]
    return flow


class TestAnalyzeRoute:
    async def test_analyze_dispatches_task_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()

        with (
            patch("app.api.routes.uml.analyze_cross_diagrams.delay") as delay_mock,
            patch("app.api.routes.uml.get_settings") as settings_mock,
        ):
            delay_mock.return_value = MagicMock(id="task-123")
            settings_mock.return_value.engine_mode.value = "native"
            response = await client.post(
                f"/api/v1/projects/{project_id}/uml/analyze",
                json={},
            )

        assert response.status_code == 202
        body = response.json()
        assert body["task_id"] == "task-123"
        assert body["status"] == "pending"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), None, "native")
        app.dependency_overrides = {}

    async def test_analyze_with_diagram_ids(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        diagram_id = uuid.uuid4()

        with (
            patch("app.api.routes.uml.analyze_cross_diagrams.delay") as delay_mock,
            patch("app.api.routes.uml.get_settings") as settings_mock,
        ):
            delay_mock.return_value = MagicMock(id="task-xyz")
            settings_mock.return_value.engine_mode.value = "hybrid"
            response = await client.post(
                f"/api/v1/projects/{project_id}/uml/analyze",
                json={"diagram_ids": [str(diagram_id)]},
            )

        assert response.status_code == 202
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(diagram_id)], "hybrid")
        app.dependency_overrides = {}


class TestListFlowsRoute:
    async def test_list_flows_paginated(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        flows = [_make_flow("Logowanie"), _make_flow("Wylogowanie", steps=2)]

        with patch(
            "app.api.routes.uml.UserFlowRepository.get_by_project",
            new_callable=AsyncMock,
            return_value=(flows, 2),
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/uml/flows?page=1&page_size=20")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["flows"]) == 2
        assert body["flows"][0]["name"] == "Logowanie"
        assert body["flows"][1]["steps"][0]["action"] == "krok 1"
        app.dependency_overrides = {}


class TestGetFlowRoute:
    async def test_get_flow_returns_detail(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        flow = _make_flow("Logowanie", steps=3)

        with patch(
            "app.api.routes.uml.UserFlowRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=flow,
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/uml/flows/{flow.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Logowanie"
        assert len(body["steps"]) == 3
        app.dependency_overrides = {}

    async def test_get_flow_missing_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.uml.UserFlowRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.get(f"/api/v1/projects/{uuid.uuid4()}/uml/flows/{uuid.uuid4()}")

        assert response.status_code == 404
        app.dependency_overrides = {}
