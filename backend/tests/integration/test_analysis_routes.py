"""Tests for analysis API endpoint (Story DEMO-001, Task 3, AC#1)."""

import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.user_tenant import TenantRole
from tests.factories import make_tenant, make_user, make_user_tenant


@pytest.fixture
def app_with_analysis():
    app = create_app()

    tenant = make_tenant(name="Test Tenant")
    user = make_user(email="analysis@test.com", name="Analysis User")
    make_user_tenant(user_id=user.id, tenant_id=tenant.id, role=TenantRole.OWNER)

    async def _override_get_current_user(request=None):
        if request:
            request.state.user = user
            request.state.tenant_id = tenant.id
            request.state.role = TenantRole.OWNER
            request.state.is_admin = False
        return user

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()

    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[__import__("app.core.dependencies", fromlist=["get_current_user"]).get_current_user] = (
        _override_get_current_user
    )
    app.dependency_overrides[__import__("app.core.dependencies", fromlist=["get_db"]).get_db] = _override_get_db

    yield app, mock_db, user, tenant
    app.dependency_overrides.clear()


@pytest.fixture
async def analysis_client(app_with_analysis):
    app = app_with_analysis[0]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_analyze_endpoint_returns_200(app_with_analysis, analysis_client):
    _app, mock_db, _user, _tenant = app_with_analysis
    project_id = uuid.uuid4()
    file_id = uuid.uuid4()

    source_file = MagicMock()
    source_file.id = file_id
    source_file.project_id = project_id
    source_file.filename = "test.py"
    source_file.storage_key = "test-key"
    source_file.is_cleaned_up = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = source_file
    mock_db.execute.return_value = mock_result

    mock_minio_response = MagicMock()
    mock_minio_response.read.return_value = b"print('hello')"
    mock_minio_response.close = MagicMock()
    mock_minio_response.release_conn = MagicMock()

    mock_analysis = {"raw_response": '{"structures": []}', "model": "glm-5.1", "usage": {}}

    with (
        patch("app.api.routes.analysis.get_minio_client") as mock_minio,
        patch("app.api.routes.analysis.analyze_file_content", new_callable=AsyncMock, return_value=mock_analysis),
        patch("app.api.routes.analysis.get_settings") as mock_settings,
    ):
        mock_minio.return_value.get_object.return_value = mock_minio_response
        mock_settings.return_value.minio_bucket_name = "testgen-files"

        response = await analysis_client.post(f"/api/v1/projects/{project_id}/files/{file_id}/analyze")

    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == str(file_id)
    assert data["project_id"] == str(project_id)
    assert data["analysis"]["model"] == "glm-5.1"


@pytest.mark.asyncio
async def test_analyze_endpoint_file_not_found(analysis_client, app_with_analysis):
    _, mock_db, _, _ = app_with_analysis
    project_id = uuid.uuid4()
    file_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    response = await analysis_client.post(f"/api/v1/projects/{project_id}/files/{file_id}/analyze")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyze_endpoint_llm_error(analysis_client, app_with_analysis):
    _, mock_db, _, _ = app_with_analysis
    project_id = uuid.uuid4()
    file_id = uuid.uuid4()

    source_file = MagicMock()
    source_file.id = file_id
    source_file.project_id = project_id
    source_file.filename = "test.py"
    source_file.storage_key = "test-key"
    source_file.is_cleaned_up = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = source_file
    mock_db.execute.return_value = mock_result

    mock_minio_response = MagicMock()
    mock_minio_response.read.return_value = b"print('hello')"
    mock_minio_response.close = MagicMock()
    mock_minio_response.release_conn = MagicMock()

    with (
        patch("app.api.routes.analysis.get_minio_client") as mock_minio,
        patch(
            "app.api.routes.analysis.analyze_file_content", new_callable=AsyncMock, side_effect=Exception("LLM failed")
        ),
        patch("app.api.routes.analysis.get_settings") as mock_settings,
    ):
        mock_minio.return_value.get_object.return_value = mock_minio_response
        mock_settings.return_value.minio_bucket_name = "testgen-files"

        response = await analysis_client.post(f"/api/v1/projects/{project_id}/files/{file_id}/analyze")

    assert response.status_code == 502


# ── Brama modułowa /analyze (UML bez kodu) ─────────────────────────────────


@pytest.fixture
def analyze_gate(monkeypatch):
    """App z typowanym overridem auth (request: Request) — get_tenant widzi kontekst."""
    from fastapi import Request

    from app.core.dependencies import get_current_user, get_db

    app = create_app()
    tenant = make_tenant(name="Gate Tenant")
    user = make_user(email="gate@test.com", name="Gate User")
    make_user_tenant(user_id=user.id, tenant_id=tenant.id, role=TenantRole.OWNER)
    user._tenant_id = tenant.id

    async def override_user(request: Request):
        request.state.user = user
        request.state.tenant_id = tenant.id
        request.state.role = TenantRole.OWNER
        request.state.is_admin = False
        return user

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=MagicMock(plan="basic"))
    mock_db.scalar = AsyncMock(return_value=1)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    yield app, mock_db
    app.dependency_overrides.clear()


@pytest.fixture
async def gate_client(analyze_gate):
    async with AsyncClient(
        transport=ASGITransport(app=analyze_gate[0]),
        base_url="http://test",
    ) as ac:
        yield ac


def _patch_dispatch():
    """Wspólny patch: quota (Redis + DB, Story 7.8) i oba taski Celery."""
    run_pipeline = MagicMock()
    run_pipeline.delay.return_value = MagicMock(id="pipeline-task-1")
    cross = MagicMock()
    cross.delay.return_value = MagicMock(id="uml-task-1")
    # Story 7.8: BillingQuotaService (limity DB) — async no-op
    billing = MagicMock()
    billing.enforce_quota = AsyncMock()
    billing.increment_usage = AsyncMock()

    @contextlib.contextmanager
    def quota_patches():
        with (
            patch("app.api.routes.analysis.QuotaService"),
            patch("app.api.routes.analysis.BillingQuotaService", MagicMock(return_value=billing)),
        ):
            yield

    return (
        quota_patches(),
        patch("app.api.routes.analysis.TaskProgressService"),
        patch("app.api.routes.analysis.run_pipeline", run_pipeline),
        patch("app.api.routes.analysis.analyze_cross_diagrams", cross),
        run_pipeline,
        cross,
    )


@pytest.mark.asyncio
async def test_analyze_uml_only_dispatches_cross_diagram(gate_client, analyze_gate):
    """uml_analysis bez modułów kodowych: brama wymaga UML (nie kodu), dispatch cross-diagram."""
    _app, mock_db = analyze_gate
    project_id = uuid.uuid4()
    mock_db.scalar = AsyncMock(return_value=3)  # 3 diagramy UML

    q, tp, rp, cross, _r, _c = _patch_dispatch()
    with q, tp, rp, cross:
        response = await gate_client.post(f"/api/v1/projects/{project_id}/analyze", json={"modules": ["uml_analysis"]})

    assert response.status_code == 202
    assert response.json()["task_id"] == "uml-task-1"


@pytest.mark.asyncio
async def test_analyze_uml_only_without_diagrams_rejected(gate_client, analyze_gate):
    _app, mock_db = analyze_gate
    project_id = uuid.uuid4()
    mock_db.scalar = AsyncMock(return_value=0)  # brak diagramów

    q, tp, rp, cross, _r, _c = _patch_dispatch()
    with q, tp, rp, cross:
        response = await gate_client.post(f"/api/v1/projects/{project_id}/analyze", json={"modules": ["uml_analysis"]})

    assert response.status_code == 422
    assert "UML" in response.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_code_module_still_requires_source_files(gate_client, analyze_gate):
    _app, mock_db = analyze_gate
    project_id = uuid.uuid4()
    mock_db.scalar = AsyncMock(return_value=0)  # brak plików kodu

    q, tp, rp, cross, _r, _c = _patch_dispatch()
    with q, tp, rp, cross:
        response = await gate_client.post(f"/api/v1/projects/{project_id}/analyze", json={"modules": ["code_analysis"]})

    assert response.status_code == 422
    assert "source files" in response.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_mixed_runs_pipeline_and_cross_diagram(gate_client, analyze_gate):
    """Kod + UML: główny task pipeline, cross-diagram odpalany równolegle."""
    _app, mock_db = analyze_gate
    project_id = uuid.uuid4()
    mock_db.scalar = AsyncMock(return_value=2)  # pliki i diagramy istnieją

    q, tp, rp, cross, run_pipeline, cross_mock = _patch_dispatch()
    with q, tp, rp, cross:
        response = await gate_client.post(
            f"/api/v1/projects/{project_id}/analyze",
            json={"modules": ["code_analysis", "test_generation", "uml_analysis"]},
        )

    assert response.status_code == 202
    assert response.json()["task_id"] == "pipeline-task-1"
    run_pipeline.delay.assert_called_once()
    cross_mock.delay.assert_called_once()
