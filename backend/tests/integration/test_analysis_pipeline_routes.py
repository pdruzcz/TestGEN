"""Integration tests for analysis pipeline and task status routes (Story 1.10, 6.3)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_db, get_tenant
from app.core.exceptions import QuotaExceededError
from app.main import create_app
from app.models.tenant import PlanType
from app.models.user_tenant import TenantRole
from tests.factories import make_tenant, make_user, make_user_tenant


@pytest.fixture
def tenant():
    return make_tenant(name="Test Tenant", plan=PlanType.BASIC)


@pytest.fixture
def owner_user(tenant):
    user = make_user(email="owner@test.com", name="Owner")
    ut = make_user_tenant(user_id=user.id, tenant_id=tenant.id, role=TenantRole.OWNER)
    user._user_tenant = ut
    user._tenant_id = tenant.id
    user._role = "owner"
    return user


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    return session


@pytest.fixture(autouse=True)
def mock_billing_quota():
    """Story 7.8: start_analysis woła BillingQuotaService (limity DB) — mock,
    by nie dokładać zapytań do AsyncMock sesji."""
    with patch("app.api.routes.analysis.BillingQuotaService") as mock_cls:
        svc = MagicMock()
        svc.enforce_quota = AsyncMock()
        svc.increment_usage = AsyncMock()
        mock_cls.return_value = svc
        yield svc


@pytest.fixture
def app_with_deps(owner_user, mock_db_session, tenant):
    app = create_app()

    async def _override_user():
        return owner_user

    async def _override_db():
        yield mock_db_session

    def _override_tenant():
        return owner_user._tenant_id

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_tenant] = _override_tenant
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app_with_deps):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_deps),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def project_id():
    return uuid.uuid4()


# ── Task 1: POST /analyze ────────────────────────────────────────────────────


class TestStartAnalysis:
    @pytest.mark.asyncio
    async def test_returns_202_with_task_id(self, client, mock_db_session, project_id, tenant):
        mock_project = MagicMock()
        mock_task = MagicMock()
        mock_task.id = str(uuid.uuid4())

        with (
            patch("app.api.routes.analysis.QuotaService") as mock_quota_cls,
            patch("app.api.routes.analysis.TaskProgressService") as mock_progress_cls,
            patch("app.api.routes.analysis.run_pipeline") as mock_pipeline,
        ):
            mock_db_session.get = AsyncMock(side_effect=[mock_project, tenant])
            mock_db_session.scalar = AsyncMock(return_value=5)

            mock_quota = MagicMock()
            mock_quota.check_and_reserve.return_value = 1
            mock_quota_cls.return_value = mock_quota

            mock_progress = MagicMock()
            mock_progress_cls.return_value = mock_progress

            mock_pipeline.delay.return_value = mock_task

            response = await client.post(
                f"/api/v1/projects/{project_id}/analyze",
                json={"engine_mode": "native", "modules": ["code_analysis"]},
            )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert "status_url" in data

    @pytest.mark.asyncio
    async def test_no_files_returns_422(self, client, mock_db_session, project_id, tenant):
        mock_project = MagicMock()

        with (
            patch("app.api.routes.analysis.QuotaService"),
            patch("app.api.routes.analysis.TaskProgressService"),
            patch("app.api.routes.analysis.run_pipeline"),
        ):
            mock_db_session.get = AsyncMock(side_effect=[mock_project, tenant])
            mock_db_session.scalar = AsyncMock(return_value=0)

            response = await client.post(
                f"/api/v1/projects/{project_id}/analyze",
                json={"engine_mode": "native", "modules": ["code_analysis"]},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_quota_exceeded_returns_429(self, client, mock_db_session, project_id, tenant):
        mock_project = MagicMock()

        with (
            patch("app.api.routes.analysis.QuotaService") as mock_quota_cls,
            patch("app.api.routes.analysis.TaskProgressService"),
            patch("app.api.routes.analysis.run_pipeline"),
        ):
            mock_db_session.get = AsyncMock(side_effect=[mock_project, tenant])
            mock_db_session.scalar = AsyncMock(return_value=5)

            mock_quota = MagicMock()
            mock_quota.check_and_reserve.side_effect = QuotaExceededError(
                detail="Limit reached",
                limit=10,
                used=10,
                plan="basic",
                upgrade_url="/pricing",
            )
            mock_quota_cls.return_value = mock_quota

            response = await client.post(
                f"/api/v1/projects/{project_id}/analyze",
                json={"engine_mode": "native", "modules": ["code_analysis"]},
            )

        assert response.status_code == 429
        data = response.json()
        assert data["type"] == "https://testgen.io/errors/quota-exceeded"

    @pytest.mark.asyncio
    async def test_billing_quota_limit_reached_returns_429(
        self, client, mock_db_session, project_id, tenant, mock_billing_quota,
    ):
        """Story 7.8 (6.3, AC1): BillingQuotaService (limity DB) → 429 z body limit_reached."""
        mock_project = MagicMock()

        with (
            patch("app.api.routes.analysis.QuotaService"),
            patch("app.api.routes.analysis.TaskProgressService"),
            patch("app.api.routes.analysis.run_pipeline"),
        ):
            mock_db_session.get = AsyncMock(side_effect=[mock_project, tenant])
            mock_db_session.scalar = AsyncMock(return_value=5)

            mock_billing_quota.enforce_quota.side_effect = QuotaExceededError(
                detail="Osiągnięto limit analyses planu freemium (10/10).",
                error="limit_reached",
                resource="analyses",
                limit=10,
                current=10,
                plan="freemium",
                upgrade_url="/billing/plans",
            )

            response = await client.post(
                f"/api/v1/projects/{project_id}/analyze",
                json={"engine_mode": "native", "modules": ["code_analysis"]},
            )

        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "limit_reached"
        assert data["resource"] == "analyses"
        assert data["limit"] == 10
        assert data["current"] == 10
        assert data["plan"] == "freemium"

    @pytest.mark.asyncio
    async def test_project_not_found_returns_404(self, client, mock_db_session, project_id):
        mock_db_session.get = AsyncMock(return_value=None)

        response = await client.post(
            f"/api/v1/projects/{project_id}/analyze",
            json={"engine_mode": "native", "modules": ["code_analysis"]},
        )

        assert response.status_code == 404


# ── Task 2: GET /tasks/{task_id} ─────────────────────────────────────────────


class TestGetTaskStatus:
    @pytest.mark.asyncio
    async def test_returns_task_status(self, client, owner_user):
        with patch("app.api.routes.tasks.TaskProgressService") as mock_progress_cls:
            mock_svc = MagicMock()
            mock_svc.get_task_status.return_value = {
                "task_id": "abc-123",
                "status": "running",
                "tenant_id": str(owner_user._tenant_id),
                "progress": 50,
                "current_step": "Parsowanie AST",
                "error": "",
                "result_url": "",
            }
            mock_progress_cls.return_value = mock_svc

            response = await client.get("/api/v1/tasks/abc-123")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "abc-123"
        assert data["status"] == "running"
        assert data["progress"] == 50
        assert data["current_step"] == "Parsowanie AST"

    @pytest.mark.asyncio
    async def test_task_not_found(self, client):
        with patch("app.api.routes.tasks.TaskProgressService") as mock_progress_cls:
            mock_svc = MagicMock()
            mock_svc.get_task_status.return_value = None
            mock_progress_cls.return_value = mock_svc

            response = await client.get("/api/v1/tasks/nonexistent")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_completed_task_has_result_url(self, client, owner_user):
        with patch("app.api.routes.tasks.TaskProgressService") as mock_progress_cls:
            mock_svc = MagicMock()
            mock_svc.get_task_status.return_value = {
                "task_id": "done-123",
                "status": "completed",
                "tenant_id": str(owner_user._tenant_id),
                "progress": 100,
                "current_step": "export",
                "error": "",
                "result_url": "/api/v1/tasks/done-123/result",
            }
            mock_progress_cls.return_value = mock_svc

            response = await client.get("/api/v1/tasks/done-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result_url"] == "/api/v1/tasks/done-123/result"


# ── Story 6.3: POST /tasks/{task_id}/cancel ──────────────────────────────────


class TestCancelTask:
    @pytest.mark.asyncio
    async def test_cancel_returns_202(self, client, owner_user):
        with (
            patch("app.api.routes.tasks.TaskProgressService") as mock_progress_cls,
            patch("app.api.routes.tasks.celery_app") as mock_celery,
        ):
            mock_svc = MagicMock()
            mock_svc.get_task_status.return_value = {
                "task_id": "task-to-cancel",
                "status": "running",
                "tenant_id": str(owner_user._tenant_id),
                "progress": 30,
                "current_step": "analysis",
            }
            mock_progress_cls.return_value = mock_svc

            response = await client.post("/api/v1/tasks/task-to-cancel/cancel")

        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == "task-to-cancel"
        assert data["status"] == "cancelled"
        mock_celery.control.revoke.assert_called_once_with(
            "task-to-cancel", terminate=True,
        )

    @pytest.mark.asyncio
    async def test_cancel_not_found_returns_404(self, client):
        with patch("app.api.routes.tasks.TaskProgressService") as mock_progress_cls:
            mock_svc = MagicMock()
            mock_svc.get_task_status.return_value = None
            mock_progress_cls.return_value = mock_svc

            response = await client.post("/api/v1/tasks/nonexistent/cancel")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_wrong_tenant_returns_404(self, client, owner_user):
        with patch("app.api.routes.tasks.TaskProgressService") as mock_progress_cls:
            mock_svc = MagicMock()
            mock_svc.get_task_status.return_value = {
                "task_id": "other-task",
                "status": "running",
                "tenant_id": str(uuid.uuid4()),  # different tenant
                "progress": 50,
                "current_step": "analysis",
            }
            mock_progress_cls.return_value = mock_svc

            response = await client.post("/api/v1/tasks/other-task/cancel")

        assert response.status_code == 404


# ── Story 6.3: AnalysisRequest extended fields ───────────────────────────────


class TestAnalysisRequestConfig:
    @pytest.mark.asyncio
    async def test_engine_mode_passed_to_pipeline(
        self, client, mock_db_session, project_id, tenant,
    ):
        mock_project = MagicMock()
        mock_task = MagicMock()
        mock_task.id = str(uuid.uuid4())

        with (
            patch("app.api.routes.analysis.QuotaService") as mock_quota_cls,
            patch("app.api.routes.analysis.TaskProgressService") as mock_progress_cls,
            patch("app.api.routes.analysis.run_pipeline") as mock_pipeline,
        ):
            mock_db_session.get = AsyncMock(side_effect=[mock_project, tenant])
            mock_db_session.scalar = AsyncMock(return_value=5)

            mock_quota = MagicMock()
            mock_quota.check_and_reserve.return_value = 1
            mock_quota_cls.return_value = mock_quota

            mock_progress = MagicMock()
            mock_progress_cls.return_value = mock_progress

            mock_pipeline.delay.return_value = mock_task

            response = await client.post(
                f"/api/v1/projects/{project_id}/analyze",
                json={
                    "engine_mode": "hybrid",
                    "modules": ["code_analysis", "test_generation"],
                    "test_framework": "cypress",
                    "temperature": 0.5,
                },
            )

        assert response.status_code == 202
        call_kwargs = mock_pipeline.delay.call_args.kwargs
        assert call_kwargs["engine_mode"] == "hybrid"
        assert call_kwargs["modules"] == ["code_analysis", "test_generation"]
