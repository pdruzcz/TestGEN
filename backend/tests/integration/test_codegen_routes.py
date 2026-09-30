"""Integration tests for Story 3.12 Cypress codegen routes.

Covers POST /codegen/cypress (202 async dispatch + 400 guards) and
GET /codegen/{code_id} (json + 404). The Celery task and service layer are
patched so the tests exercise routing + serialization only.
"""

import uuid
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


class TestGenerateRoute:
    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_cypress_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-1")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/cypress",
                json={"test_case_ids": [str(tc_id)], "framework": "cypress", "base_url": "https://app.test"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-1"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)], "https://app.test")
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/cypress",
            json={"test_case_ids": [], "framework": "cypress"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}


class TestGenerateSikulixRoute:
    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_sikulix_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-sx")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/sikulix",
                json={"test_case_ids": [str(tc_id)], "framework": "sikulix"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-sx"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)])
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/sikulix",
            json={"test_case_ids": [], "framework": "sikulix"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}


class TestGenerateDatabaseRoute:
    """Story 1.53 (FR70) — POST /codegen/database (202 async dispatch)."""

    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_database_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-db")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/database",
                json={"test_case_ids": [str(tc_id)], "framework": "database"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-db"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)])
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/database",
            json={"test_case_ids": [], "framework": "database"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}


class TestGeneratePhpUnitRoute:
    """Story 1.55 (FR24) — POST /codegen/phpunit (202 async dispatch)."""

    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_phpunit_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-phpunit")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/phpunit",
                json={"test_case_ids": [str(tc_id)], "framework": "phpunit"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-phpunit"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)])
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/phpunit",
            json={"test_case_ids": [], "framework": "phpunit"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}


class TestGeneratePestRoute:
    """Story 1.55 (FR24) — POST /codegen/pest (202 async dispatch)."""

    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_pest_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-pest")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/pest",
                json={"test_case_ids": [str(tc_id)], "framework": "pest"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-pest"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)])
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/pest",
            json={"test_case_ids": [], "framework": "pest"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}


class TestGenerateSeleniumRoute:
    """Story 1.56 — POST /codegen/selenium (202 async dispatch)."""

    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_selenium_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-sel")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/selenium",
                json={"test_case_ids": [str(tc_id)], "framework": "selenium"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-sel"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)])
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/selenium",
            json={"test_case_ids": [], "framework": "selenium"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}

    async def test_generate_invalid_framework_returns_422(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/selenium",
            json={"test_case_ids": [str(uuid.uuid4())], "framework": "foo"},
        )

        assert response.status_code == 422
        app.dependency_overrides = {}


class TestGeneratePlaywrightRoute:
    """Story 1.56 — POST /codegen/playwright (202 async dispatch)."""

    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_playwright_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-pw")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/playwright",
                json={"test_case_ids": [str(tc_id)], "framework": "playwright"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-pw"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)])
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/playwright",
            json={"test_case_ids": [], "framework": "playwright"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}

    async def test_generate_invalid_framework_returns_422(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/playwright",
            json={"test_case_ids": [str(uuid.uuid4())], "framework": "foo"},
        )

        assert response.status_code == 422
        app.dependency_overrides = {}


class TestGenerateAppiumRoute:
    """Story 1.56 — POST /codegen/appium (202 async dispatch + platform)."""

    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_appium_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-ap")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/appium",
                json={"test_case_ids": [str(tc_id)], "framework": "appium"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-ap"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)], None)
        app.dependency_overrides = {}

    async def test_generate_dispatches_platform(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_appium_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-ap-ios")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/appium",
                json={"test_case_ids": [str(tc_id)], "framework": "appium", "platform": "ios"},
            )

        assert response.status_code == 202
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)], "ios")
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/appium",
            json={"test_case_ids": [], "framework": "appium"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}

    async def test_generate_invalid_platform_returns_422(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/appium",
            json={"test_case_ids": [str(uuid.uuid4())], "framework": "appium", "platform": "windows"},
        )

        assert response.status_code == 422
        app.dependency_overrides = {}


class TestGenerateUnittestRoute:
    """Story 1.57 — POST /codegen/unittest (202 async dispatch)."""

    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_unittest_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-ut")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/unittest",
                json={"test_case_ids": [str(tc_id)], "framework": "unittest"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-ut"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)])
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/unittest",
            json={"test_case_ids": [], "framework": "unittest"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}


class TestGenerateTestNgRoute:
    """Story 1.57 — POST /codegen/testng (202 async dispatch)."""

    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_testng_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-tng")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/testng",
                json={"test_case_ids": [str(tc_id)], "framework": "testng"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-tng"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)])
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/testng",
            json={"test_case_ids": [], "framework": "testng"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}


class TestGenerateMsTestRoute:
    """Story 1.57 — POST /codegen/mstest (202 async dispatch)."""

    async def test_generate_dispatches_returns_202(self, client, app):
        user = make_user()
        tenant_id = _override_auth(app, user)
        project_id = uuid.uuid4()
        tc_id = uuid.uuid4()

        with patch("app.api.routes.codegen.generate_mstest_code.delay") as delay_mock:
            delay_mock.return_value = MagicMock(id="task-mst")
            response = await client.post(
                f"/api/v1/projects/{project_id}/codegen/mstest",
                json={"test_case_ids": [str(tc_id)], "framework": "mstest"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "task-mst"
        delay_mock.assert_called_once_with(str(project_id), str(tenant_id), [str(tc_id)])
        app.dependency_overrides = {}

    async def test_generate_empty_ids_returns_400(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        response = await client.post(
            f"/api/v1/projects/{project_id}/codegen/mstest",
            json={"test_case_ids": [], "framework": "mstest"},
        )

        assert response.status_code == 400
        app.dependency_overrides = {}


class TestGetRoute:
    async def test_get_returns_code(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()
        code_id = uuid.uuid4()
        record = SimpleNamespace(
            id=code_id,
            test_case_id=uuid.uuid4(),
            framework="cypress",
            language="typescript",
            code="describe('x', () => {});\n",
            file_path="cypress/e2e/x.cy.ts",
            created_at=None,
        )

        with patch(
            "app.api.routes.codegen.get_generated_code",
            new_callable=AsyncMock,
            return_value=record,
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/codegen/{code_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["framework"] == "cypress"
        assert body["file_path"] == "cypress/e2e/x.cy.ts"
        app.dependency_overrides = {}

    async def test_get_missing_returns_404(self, client, app):
        user = make_user()
        _override_auth(app, user)
        project_id = uuid.uuid4()

        with patch(
            "app.api.routes.codegen.get_generated_code",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = await client.get(f"/api/v1/projects/{project_id}/codegen/{uuid.uuid4()}")

        assert response.status_code == 404
        app.dependency_overrides = {}
