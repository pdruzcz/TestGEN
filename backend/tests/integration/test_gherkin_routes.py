"""Integration tests for Story 3.11 Gherkin/BDD routes.

Covers POST /gherkin/generate (202 async dispatch + 400 guards), GET /gherkin
(pagination) and GET /gherkin/{id} (json + raw + 404). The Celery task and
service layer are patched so the tests exercise routing + serialization only.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.gherkin_feature import GherkinStatus
from tests.factories import make_user


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
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


def _make_feature(tenant_id, name="Logowanie"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        project_id=uuid.uuid4(),
        source_flow_id=uuid.uuid4(),
        feature_name=name,
        feature_description="opis",
        scenarios=[
            {
                "name": "S",
                "tags": [],
                "steps": [{"keyword": "When", "text": "x"}],
                "examples_headers": [],
                "examples_rows": [],
            }
        ],
        raw_feature="Feature: Logowanie\n  Scenario: S\n    When x\n",
        engine_mode="native",
        validation_warnings=[],
        status=GherkinStatus.VALIDATED,
        created_at=None,
    )


class TestGenerateRoute:
    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        flow_id = uuid.uuid4()

        with (
            patch("app.api.routes.gherkin.generate_gherkin.delay") as delay_mock,
            patch("app.api.routes.gherkin.get_settings") as settings_mock,
        ):
            delay_mock.return_value = MagicMock(id="task-1")
            settings_mock.return_value.engine_mode.value = "native"
            response = await client.post(
                f"/api/v1/projects/{project_id}/gherkin/generate",
                json={"flow_ids": [str(flow_id)]},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-1"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(flow_id)], "native", None)
        app.dependency_overrides = {}

    async def test_generate_empty_flows_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/gherkin/generate",
            json={"flow_ids": [], "engine_mode": "native"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}


class TestListRoute:
    async def test_list_paginated(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        rows = [_make_feature(tenant_id, "A"), _make_feature(tenant_id, "B")]

        with patch(
            "app.api.routes.gherkin.list_features",
            new_callable=AsyncMock,
            return_value=(rows, 2),
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/gherkin?page=1&page_size=20")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["features"]) == 2
        assert body["features"][0]["feature_name"] == "A"
        app.dependency_overrides = {}


class TestGetRoute:
    async def test_get_json(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        feature = _make_feature(tenant_id)

        with patch(
            "app.api.routes.gherkin.get_feature",
            new_callable=AsyncMock,
            return_value=feature,
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/gherkin/{feature.id}")

        assert response.status_code == 200
        body = response.json()
        assert body["feature_name"] == "Logowanie"
        assert body["scenarios"][0]["name"] == "S"
        app.dependency_overrides = {}

    async def test_get_raw_returns_plain_text(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        feature = _make_feature(tenant_id)

        with patch(
            "app.api.routes.gherkin.get_feature",
            new_callable=AsyncMock,
            return_value=feature,
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/gherkin/{feature.id}?format=raw")

        assert response.status_code == 200
        assert "Feature: Logowanie" in response.text
        assert response.headers["content-type"].startswith("text/plain")
        app.dependency_overrides = {}

    async def test_get_missing_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        with patch(
            "app.api.routes.gherkin.get_feature",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/gherkin/{uuid.uuid4()}")

        assert response.status_code == 404
        app.dependency_overrides = {}
