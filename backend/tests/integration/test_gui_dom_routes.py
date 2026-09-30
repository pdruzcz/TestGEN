"""Integration tests for Story 1.51-zakańczenie DOM routes.

Covers POST /gui/dom/upload (202 async dispatch per HTML file, a11y flag,
rejection passthrough) and GET /gui/analyses (history list with source_type +
pagination). The service layer and Celery task are patched so the tests
exercise routing + serialization only, mirroring test_gui_routes.py.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.analysis.gui.dom_upload_service import (
    DOMSourceAcceptance,
    DOMUploadOutcome,
)
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


def _source(tenant_id):
    return SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id)


class TestDomUploadRoute:
    async def test_upload_dispatches_task_per_html(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        outcome = DOMUploadOutcome(
            accepted=[
                DOMSourceAcceptance(source_file=_source(tenant_id), filename="logowanie.html", status="accepted")
            ],
            rejected=[],
            a11y_storage_key="tenant/proj/gui-dom/abc_a11y.json",
        )

        with (
            patch(
                "app.api.routes.gui.upload_dom_sources",
                new_callable=AsyncMock,
                return_value=outcome,
            ),
            patch("app.api.routes.gui.analyze_dom_source.delay") as delay_mock,
        ):
            delay_mock.return_value = MagicMock(id="task-dom-1")
            response = await client.post(
                f"/api/v1/projects/{project_id}/gui/dom/upload",
                files=[("files", ("logowanie.html", b"<button>X</button>", "text/html"))],
                data={"version_label": "przed refaktoryzacją"},
            )

        assert response.status_code == 202
        body = response.json()
        assert body["total_accepted"] == 1
        assert body["accepted"][0]["task_id"] == "task-dom-1"
        assert body["accepted"][0]["filename"] == "logowanie.html"
        assert body["a11y_accepted"] is True
        # task dispatched with the shared a11y key + version label
        delay_mock.assert_called_once()
        args = delay_mock.call_args.args
        assert args[2] == "tenant/proj/gui-dom/abc_a11y.json"
        assert args[3] == "przed refaktoryzacją"

    async def test_upload_rejects_non_html_passthrough(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        outcome = DOMUploadOutcome(
            accepted=[],
            rejected=[
                DOMSourceAcceptance(source_file=None, filename="notepad.txt", status="rejected", rejection_reason="x")
            ],
            a11y_storage_key=None,
        )

        with (
            patch(
                "app.api.routes.gui.upload_dom_sources",
                new_callable=AsyncMock,
                return_value=outcome,
            ),
            patch("app.api.routes.gui.analyze_dom_source.delay") as delay_mock,
        ):
            response = await client.post(
                f"/api/v1/projects/{project_id}/gui/dom/upload",
                files=[("files", ("notepad.txt", b"x", "text/plain"))],
            )

        assert response.status_code == 202
        body = response.json()
        assert body["total_rejected"] == 1
        assert body["total_accepted"] == 0
        assert body["a11y_accepted"] is False
        delay_mock.assert_not_called()


class TestListAnalysesRoute:
    async def test_list_returns_history_with_source_type(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        analyses = [
            {
                "id": str(uuid.uuid4()),
                "source_type": "dom",
                "created_at": "2026-07-29T10:00:00",
                "version_label": "po",
                "source_label": "logowanie.html",
                "screen_sequence": None,
                "component_count": 8,
            },
            {
                "id": str(uuid.uuid4()),
                "source_type": "screenshot",
                "created_at": "2026-07-10T10:00:00",
                "version_label": None,
                "source_label": "screen.png",
                "screen_sequence": 1,
                "component_count": 5,
            },
        ]

        with patch(
            "app.api.routes.gui.list_dom_analyses",
            new_callable=AsyncMock,
            return_value=(analyses, 2),
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/gui/analyses")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["analyses"][0]["source_type"] == "dom"
        assert body["analyses"][0]["component_count"] == 8
        assert body["analyses"][1]["source_type"] == "screenshot"
