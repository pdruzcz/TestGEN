"""Integration tests for Story 3.8 GUI screenshot routes.

Covers POST /gui/upload (202 async dispatch), GET /gui (pagination),
POST /gui/analyze (re-analyze / 404) and GET /gui/{id}/result (with + without an
analysis result). The Celery task and service layer are patched so the tests
exercise routing + serialization only.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.gui_screenshot import GUIAnalysisStatus, GUIComponentType
from app.models.user_flow import FlowSourceType, FlowStatus
from app.services.analysis.gui.upload_service import GUIFileAcceptance, GUIUploadOutcome
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


def _make_screenshot(tenant_id, filename="screen.png", seq=1):
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        filename=filename,
        status=GUIAnalysisStatus.PENDING,
        screen_sequence=seq,
        file_size=1234,
        created_at=None,
    )


class TestUploadRoute:
    async def test_upload_dispatches_task_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        screenshot = _make_screenshot(tenant_id)
        outcome = GUIUploadOutcome(
            accepted=[GUIFileAcceptance(screenshot=screenshot, filename="screen.png", status="accepted")],
            rejected=[GUIFileAcceptance(screenshot=None, filename="bad.txt", status="rejected", rejection_reason="x")],
        )

        with (
            patch(
                "app.api.routes.gui.upload_screenshots",
                new_callable=AsyncMock,
                return_value=outcome,
            ),
            patch("app.api.routes.gui.analyze_gui_screenshot.delay") as delay_mock,
        ):
            delay_mock.return_value = MagicMock(id="task-1")
            response = await client.post(
                f"/api/v1/projects/{project_id}/gui/upload",
                files=[("files", ("screen.png", b"\x89PNG", "image/png"))],
            )

        assert response.status_code == 202
        body = response.json()
        assert body["total_accepted"] == 1
        assert body["total_rejected"] == 1
        assert body["accepted"][0]["task_id"] == "task-1"
        delay_mock.assert_called_once_with(str(screenshot.id), str(tenant_id))
        app.dependency_overrides = {}


class TestListRoute:
    async def test_list_paginated(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        rows = [_make_screenshot(tenant_id, "a.png", 1), _make_screenshot(tenant_id, "b.png", 2)]

        with patch(
            "app.api.routes.gui.list_screenshots",
            new_callable=AsyncMock,
            return_value=(rows, 2),
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/gui?page=1&page_size=20")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["screenshots"]) == 2
        assert body["screenshots"][0]["filename"] == "a.png"
        app.dependency_overrides = {}


class TestAnalyzeRoute:
    async def test_analyze_dispatches(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        screenshot = _make_screenshot(tenant_id)

        with (
            patch(
                "app.api.routes.gui.get_screenshot",
                new_callable=AsyncMock,
                return_value=screenshot,
            ),
            patch("app.api.routes.gui.analyze_gui_screenshot.delay") as delay_mock,
        ):
            delay_mock.return_value = MagicMock(id="task-2")
            response = await client.post(
                f"/api/v1/projects/{project_id}/gui/analyze",
                json={"screenshot_id": str(screenshot.id)},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-2"
        app.dependency_overrides = {}

    async def test_analyze_missing_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.gui.get_screenshot",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.post(
                f"/api/v1/projects/{uuid.uuid4()}/gui/analyze",
                json={"screenshot_id": str(uuid.uuid4())},
            )

        assert response.status_code == 404
        app.dependency_overrides = {}


class TestResultRoute:
    async def test_result_without_analysis(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        screenshot = _make_screenshot(tenant_id)

        with (
            patch(
                "app.api.routes.gui.get_screenshot",
                new_callable=AsyncMock,
                return_value=screenshot,
            ),
            patch(
                "app.api.routes.gui.get_analysis_result",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            response = await client.get(
                f"/api/v1/projects/{project_id}/gui/{screenshot.id}/result"
            )

        assert response.status_code == 200
        body = response.json()
        assert body["components"] == []
        assert body["status"] == "pending"
        app.dependency_overrides = {}

    async def test_result_with_analysis(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        screenshot = _make_screenshot(tenant_id)
        screenshot.status = GUIAnalysisStatus.COMPLETED

        component = SimpleNamespace(
            id=uuid.uuid4(),
            component_type=GUIComponentType.BUTTON,
            label="OK",
            bbox={"x": 1, "y": 2, "width": 3, "height": 4},
            confidence=0.8,
            attributes=None,
        )
        analysis = SimpleNamespace(
            ocr_text_blocks=[{"text": "Email", "bbox": {"x": 0, "y": 0, "width": 5, "height": 5}, "confidence": 0.9}],
            layout_tree={"type": "screen", "label": None, "bbox": None, "children": []},
            warnings=["w1"],
            processing_time_ms=42,
            components=[component],
        )

        with (
            patch(
                "app.api.routes.gui.get_screenshot",
                new_callable=AsyncMock,
                return_value=screenshot,
            ),
            patch(
                "app.api.routes.gui.get_analysis_result",
                new_callable=AsyncMock,
                return_value=analysis,
            ),
        ):
            response = await client.get(
                f"/api/v1/projects/{project_id}/gui/{screenshot.id}/result"
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["processing_time_ms"] == 42
        assert body["ocr_text_blocks"][0]["text"] == "Email"
        assert body["components"][0]["component_type"] == "button"
        assert body["layout_tree"]["type"] == "screen"
        app.dependency_overrides = {}

    async def test_result_missing_screenshot_404(self, client, app):
        user = make_user()
        _override_auth(app, user)

        with patch(
            "app.api.routes.gui.get_screenshot",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.get(
                f"/api/v1/projects/{uuid.uuid4()}/gui/{uuid.uuid4()}/result"
            )

        assert response.status_code == 404
        app.dependency_overrides = {}


class TestFlowRoutes:
    async def test_reconstruct_flows_dispatches(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()

        with patch("app.api.routes.gui.reconstruct_gui_flows.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="flow-task-1")
            response = await client.post(
                f"/api/v1/projects/{project_id}/gui/flows",
                json={"screenshot_ids": [str(uuid.uuid4())], "engine_mode": "native"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "flow-task-1"
        delay_mock.assert_called_once()
        assert delay_mock.call_args.args[1] == str(tenant_id)
        app.dependency_overrides = {}

    async def test_list_flows(self, client, app):
        from app.core.dependencies import get_db

        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        flow = SimpleNamespace(
            id=uuid.uuid4(),
            name="Logowanie",
            source_type=FlowSourceType.GUI,
            source_ids=["s1", "s2"],
            flow_steps=[
                SimpleNamespace(
                    id=uuid.uuid4(),
                    sequence=1,
                    action="Kliknięcie przycisku Dalej",
                    actor=None,
                    target_element="Dalej",
                    expected_result=None,
                    source_diagram_id=None,
                    source_screenshot_id=uuid.uuid4(),
                    source="native",
                )
            ],
            status=FlowStatus.DRAFT,
            warnings=None,
            created_at=None,
        )

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [flow]

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(side_effect=[count_result, list_result])

        async def override_db():
            yield db_mock

        app.dependency_overrides[get_db] = override_db

        response = await client.get(
            f"/api/v1/projects/{project_id}/gui/flows?page=1&page_size=20"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["flows"][0]["name"] == "Logowanie"
        assert body["flows"][0]["source_type"] == "gui"
        assert body["flows"][0]["steps"][0]["target_element"] == "Dalej"
        app.dependency_overrides = {}


class TestComparisonRoutes:
    async def test_compare_returns_result(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        baseline_id = uuid.uuid4()
        comparison_id = uuid.uuid4()

        record = SimpleNamespace(
            id=uuid.uuid4(),
            pixel_diff_percentage=1.5,
            status=SimpleNamespace(value="minor_diff"),
            diff_image_key=None,
            created_at=None,
        )
        engine_result = MagicMock()
        engine_result.semantic_diff_payload.return_value = [
            {
                "component_type": "button",
                "change_type": "element_moved",
                "severity": "visual",
                "description": "Przesunięcie 12px.",
                "baseline_bbox": None,
                "comparison_bbox": None,
                "confidence": 0.65,
            }
        ]
        engine_result.warnings = ["Brak numpy - pominięto pixel diff."]

        with patch(
            "app.api.routes.gui.run_comparison",
            new_callable=AsyncMock,
            return_value=(record, engine_result, None),
        ):
            response = await client.post(
                f"/api/v1/projects/{project_id}/gui/compare",
                json={
                    "baseline_screenshot_id": str(baseline_id),
                    "comparison_screenshot_id": str(comparison_id),
                    "pixel_threshold": 0.02,
                    "generate_test_code": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "minor_diff"
        assert body["pixel_diff_percentage"] == 1.5
        assert body["semantic_diff"][0]["change_type"] == "element_moved"
        app.dependency_overrides = {}

    async def test_compare_missing_screenshot_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        with patch(
            "app.api.routes.gui.run_comparison",
            new_callable=AsyncMock,
            return_value=(None, None, "Nie znaleziono screenshotu baseline."),
        ):
            response = await client.post(
                f"/api/v1/projects/{project_id}/gui/compare",
                json={
                    "baseline_screenshot_id": str(uuid.uuid4()),
                    "comparison_screenshot_id": str(uuid.uuid4()),
                },
            )

        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_list_comparisons(self, client, app):
        from app.core.dependencies import get_db

        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        row = SimpleNamespace(
            id=uuid.uuid4(),
            baseline_screenshot_id=uuid.uuid4(),
            comparison_screenshot_id=uuid.uuid4(),
            pixel_diff_percentage=2.0,
            status=SimpleNamespace(value="minor_diff"),
            created_at=None,
        )

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [row]

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(side_effect=[count_result, list_result])

        async def override_db():
            yield db_mock

        app.dependency_overrides[get_db] = override_db

        response = await client.get(
            f"/api/v1/projects/{project_id}/gui/comparisons?page=1&page_size=20"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["status"] == "minor_diff"
        app.dependency_overrides = {}
