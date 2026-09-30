"""Integration tests for functional gap analysis routes — Epic 5, Story 5.1.

Tests POST /gap-analysis (202 + async dispatch), GET /gap-findings (filters,
pagination), and GET /gap-analysis/summary. Celery task and DB session are
patched so tests exercise routing + serialization only.
"""

import uuid
from datetime import datetime, timezone
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
    """Create an AsyncMock db.execute that returns a result whose
    scalar_one_or_none / scalars / scalar_one are sync MagicMock."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=return_value)
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[return_value] if return_value else [])))
    result.scalar_one = MagicMock(return_value=return_value)
    return AsyncMock(return_value=result)


def _make_finding(tenant_id, project_id, **kw):
    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        tenant_id=tenant_id,
        project_id=project_id,
        requirement_id=kw.get("requirement_id", "R1"),
        code_entity_id=kw.get("code_entity_id", None),
        gap_type=kw.get("gap_type", "missing"),
        description=kw.get("description", "Requirement without implementation"),
        requirement_text=kw.get("requirement_text", "System must authenticate users"),
        code_reference=kw.get("code_reference", None),
        match_score=kw.get("match_score", 25.0),
        match_method=kw.get("match_method", "combined"),
        context=kw.get("context", {"best_candidate": None}),
        severity=kw.get("severity", "warning"),
        created_at=kw.get("created_at", datetime.now(timezone.utc)),
    )


class TestStartGapAnalysis:
    async def test_post_dispatches_returns_202(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        project = SimpleNamespace(id=project_id, tenant_id=tenant_id)
        db.execute = _mock_db_execute(project)

        _override_auth(app, user, db, tenant_id)

        mock_task = MagicMock()
        mock_task.id = "task-123"

        with patch("app.workers.tasks.gap_tasks.run_gap_analysis") as mock_delay:
            mock_delay.delay.return_value = mock_task
            resp = await client.post(
                f"/api/v1/projects/{project_id}/gap-analysis",
                json={"engine_mode": "native"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert data["task_id"] == "task-123"
        assert data["status"] == "pending"


class TestListGapFindings:
    async def test_get_findings_returns_list_with_summary(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        project = SimpleNamespace(id=project_id, tenant_id=tenant_id)
        finding = _make_finding(tenant_id, project_id)

        # Project lookup → project
        proj_result = MagicMock()
        proj_result.scalar_one_or_none = MagicMock(return_value=project)

        # Count query → 1
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=1)

        # Findings query → [finding]
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[finding])
        findings_result = MagicMock()
        findings_result.scalars = MagicMock(return_value=scalars_mock)

        # Summary query → [finding]
        summary_scalars = MagicMock()
        summary_scalars.all = MagicMock(return_value=[finding])
        summary_result = MagicMock()
        summary_result.scalars = MagicMock(return_value=summary_scalars)

        db.execute = AsyncMock(
            side_effect=[proj_result, count_result, findings_result, summary_result]
        )

        _override_auth(app, user, db, tenant_id)

        resp = await client.get(f"/api/v1/projects/{project_id}/gap-findings")

        assert resp.status_code == 200
        data = resp.json()
        assert "findings" in data
        assert data["total"] == 1
        assert "summary" in data
        assert "page" in data
        assert "size" in data

    async def test_get_findings_with_gap_type_filter(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        project = SimpleNamespace(id=project_id, tenant_id=tenant_id)
        proj_result = MagicMock()
        proj_result.scalar_one_or_none = MagicMock(return_value=project)

        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=0)

        empty_scalars = MagicMock()
        empty_scalars.all = MagicMock(return_value=[])
        findings_result = MagicMock()
        findings_result.scalars = MagicMock(return_value=empty_scalars)

        summary_result = MagicMock()
        summary_scalars = MagicMock()
        summary_scalars.all = MagicMock(return_value=[])
        summary_result.scalars = MagicMock(return_value=summary_scalars)

        db.execute = AsyncMock(
            side_effect=[proj_result, count_result, findings_result, summary_result]
        )

        _override_auth(app, user, db, tenant_id)

        resp = await client.get(
            f"/api/v1/projects/{project_id}/gap-findings",
            params={"gap_type": "missing"},
        )

        assert resp.status_code == 200

    async def test_get_findings_invalid_gap_type_returns_422(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        project = SimpleNamespace(id=project_id, tenant_id=tenant_id)
        proj_result = MagicMock()
        proj_result.scalar_one_or_none = MagicMock(return_value=project)

        db.execute = AsyncMock(return_value=proj_result)

        _override_auth(app, user, db, tenant_id)

        resp = await client.get(
            f"/api/v1/projects/{project_id}/gap-findings",
            params={"gap_type": "invalid_type"},
        )

        assert resp.status_code == 422


class TestGetSummary:
    async def test_get_summary_returns_counts(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        db = AsyncMock()

        project = SimpleNamespace(id=project_id, tenant_id=tenant_id)
        proj_result = MagicMock()
        proj_result.scalar_one_or_none = MagicMock(return_value=project)

        finding = _make_finding(tenant_id, project_id, gap_type="missing")
        summary_scalars = MagicMock()
        summary_scalars.all = MagicMock(return_value=[finding])
        summary_result = MagicMock()
        summary_result.scalars = MagicMock(return_value=summary_scalars)

        db.execute = AsyncMock(side_effect=[proj_result, summary_result])

        _override_auth(app, user, db, tenant_id)

        resp = await client.get(
            f"/api/v1/projects/{project_id}/gap-analysis/summary"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "missing_count" in data
        assert "coverage_percentage" in data
        assert "avg_match_score" in data


class TestProjectAccess:
    async def test_project_not_found_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()

        proj_result = MagicMock()
        proj_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=proj_result)

        _override_auth(app, user, db)

        resp = await client.get(
            f"/api/v1/projects/{project_id}/gap-analysis/summary"
        )
        assert resp.status_code == 404
