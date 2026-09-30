"""Integration tests for Story 4.7 aggregated report routes.

Covers GET /security-report (aggregated summary + findings), GET
/security-findings with the new filters, and PATCH
/security-findings/{id}/status. The DB session is mocked so the tests exercise
routing + serialization + aggregation wiring only.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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


def _finding(project_id, **kw):
    from app.models.security_finding import (
        AnalysisSource,
        ScanType,
        Severity,
    )

    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        project_id=project_id,
        scan_id=uuid.uuid4(),
        scan_type=kw.get("scan_type", ScanType.SAST),
        vulnerability_type=kw.get("vuln", "sql_injection"),
        severity=kw.get("severity", Severity.HIGH),
        cwe_id=kw.get("cwe", "CWE-89"),
        owasp_category=None,
        file_path=kw.get("file_path", "app/db.py"),
        line_start=kw.get("line", 10),
        line_end=None,
        code_snippet=None,
        description="opis",
        confidence=0.5,
        source=kw.get("source", AnalysisSource.NATIVE),
        status=kw.get("status", "open"),
        taint_path=None,
        recommendation=None,
        finding_metadata=None,
        created_at=None,
    )


class TestSecurityReport:
    async def test_report_aggregates_and_dedups(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        from app.models.security_finding import ScanType

        # Same dedup key from SAST + TAINT → 1 finding, dedup_count 1.
        findings = [
            _finding(project_id, scan_type=ScanType.SAST),
            _finding(project_id, scan_type=ScanType.TAINT),
        ]
        result = MagicMock()
        result.scalars.return_value.all.return_value = findings
        db.execute.return_value = result

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-report"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["total_findings"] == 1
        assert body["dedup_count"] == 1
        app.dependency_overrides = {}


class TestFindingFilters:
    async def test_filter_by_cwe(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        total_result = MagicMock()
        total_result.scalar_one.return_value = 0
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []
        db.execute.side_effect = [total_result, list_result]

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-findings?cwe_id=CWE-89&file_path=db"
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0
        app.dependency_overrides = {}


class TestFindingStatusUpdate:
    async def test_patch_status_updates_finding(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        finding = _finding(project_id, id=finding_id)
        db.get.return_value = finding

        async def refresh(obj):
            obj.status = "acknowledged"

        db.refresh.side_effect = refresh

        response = await client.patch(
            f"/api/v1/projects/{project_id}/security-findings/{finding_id}/status",
            json={"status": "acknowledged"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "acknowledged"
        app.dependency_overrides = {}

    async def test_patch_status_missing_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = None

        response = await client.patch(
            f"/api/v1/projects/{project_id}/security-findings/{uuid.uuid4()}/status",
            json={"status": "fixed"},
        )

        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_patch_invalid_status_returns_422(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        response = await client.patch(
            f"/api/v1/projects/{project_id}/security-findings/{uuid.uuid4()}/status",
            json={"status": "bogus"},
        )

        assert response.status_code == 422
        app.dependency_overrides = {}
