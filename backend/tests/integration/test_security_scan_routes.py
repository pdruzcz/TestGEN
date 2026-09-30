"""Integration tests for Story 4.1 security-scan routes.

Covers POST /security-scan (202 + async dispatch), GET /security-scans (list),
GET /security-scans/{id} (status + severity counts, 404) and GET
/security-findings (filters/pagination). The Celery task and DB session are
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


def _make_scan(tenant_id, project_id, **kw):
    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        tenant_id=tenant_id,
        project_id=project_id,
        scan_type=SimpleNamespace(value="sast"),
        engine_mode="native",
        status=SimpleNamespace(value=kw.get("status", "completed")),
        findings_count=kw.get("findings_count", 0),
        task_id=None,
        target_url=None,
        started_at=None,
        completed_at=None,
        error_message=None,
        created_at=None,
    )


class TestStartScan:
    async def test_post_dispatches_returns_202(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        # db.refresh fills in the committed scan; simulate generated id/status.
        async def refresh(obj):
            obj.id = uuid.uuid4()
            obj.status = SimpleNamespace(value="pending")
            obj.created_at = None

        db.refresh.side_effect = refresh

        with patch(
            "app.api.routes.security_scan.run_sast.delay",
            return_value=MagicMock(id="task-1"),
        ) as delay_mock:
            response = await client.post(
                f"/api/v1/projects/{project_id}/security-scan",
                json={"scan_type": "sast", "engine_mode": "native"},
            )

        assert response.status_code == 202
        body = response.json()
        assert body["task_id"] == "task-1"
        assert body["status"] == "pending"
        delay_mock.assert_called_once()
        app.dependency_overrides = {}


class TestListScans:
    async def test_list_returns_scans(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        tenant_id = _override_auth(app, user, db)
        scans = [
            _make_scan(tenant_id, project_id, findings_count=3),
            _make_scan(tenant_id, project_id, status="running"),
        ]

        result = MagicMock()
        result.scalars.return_value.all.return_value = scans
        db.execute.return_value = result

        response = await client.get(f"/api/v1/projects/{project_id}/security-scans")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["scans"]) == 2
        app.dependency_overrides = {}


class TestGetScan:
    async def test_get_returns_status_and_counts(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        scan_id = uuid.uuid4()
        db = AsyncMock()
        tenant_id = _override_auth(app, user, db)
        scan = _make_scan(tenant_id, project_id, id=scan_id, findings_count=2)

        from app.models.security_finding import Severity

        db.get.return_value = scan
        counts_result = MagicMock()
        counts_result.all.return_value = [(Severity.CRITICAL, 1), (Severity.HIGH, 1)]
        db.execute.return_value = counts_result

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-scans/{scan_id}"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["severity_counts"]["critical"] == 1
        assert body["severity_counts"]["high"] == 1
        app.dependency_overrides = {}

    async def test_get_missing_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)
        db.get.return_value = None

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-scans/{uuid.uuid4()}"
        )

        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_get_wrong_project_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        scan_id = uuid.uuid4()
        db = AsyncMock()
        tenant_id = _override_auth(app, user, db)
        # Scan belongs to a different project.
        db.get.return_value = _make_scan(tenant_id, uuid.uuid4(), id=scan_id)

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-scans/{scan_id}"
        )

        assert response.status_code == 404
        app.dependency_overrides = {}


class TestListFindings:
    async def test_list_findings_paginated(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        finding = SimpleNamespace(
            id=uuid.uuid4(),
            scan_id=uuid.uuid4(),
            scan_type="sast",
            vulnerability_type="sql_injection",
            severity="critical",
            cwe_id="CWE-89",
            owasp_category="A03:2021-Injection",
            file_path="db.py",
            line_start=10,
            line_end=10,
            code_snippet="...",
            description="opis",
            confidence=0.7,
            source="native",
            status="open",
            recommendation="param",
            created_at=None,
        )

        total_result = MagicMock()
        total_result.scalar_one.return_value = 1
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [finding]
        db.execute.side_effect = [total_result, list_result]

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-findings?page=1&page_size=50"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["findings"][0]["vulnerability_type"] == "sql_injection"
        app.dependency_overrides = {}

    async def test_invalid_severity_filter_returns_422(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-findings?severity=bogus"
        )

        assert response.status_code == 422
        app.dependency_overrides = {}


class TestDependencyScan:
    async def test_post_dependency_dispatches_run_dependency_scan(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        async def refresh(obj):
            obj.id = uuid.uuid4()
            obj.status = SimpleNamespace(value="pending")
            obj.created_at = None

        db.refresh.side_effect = refresh

        with patch(
            "app.api.routes.security_scan.run_dependency_scan.delay",
            return_value=MagicMock(id="dep-task"),
        ) as delay_mock:
            response = await client.post(
                f"/api/v1/projects/{project_id}/security-scan",
                json={"scan_type": "dependency", "engine_mode": "native"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "dep-task"
        delay_mock.assert_called_once()
        app.dependency_overrides = {}


class TestConfigScan:
    async def test_post_config_dispatches_run_config_scan(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        async def refresh(obj):
            obj.id = uuid.uuid4()
            obj.status = SimpleNamespace(value="pending")
            obj.created_at = None

        db.refresh.side_effect = refresh

        with patch(
            "app.api.routes.security_scan.run_config_scan.delay",
            return_value=MagicMock(id="cfg-task"),
        ) as delay_mock:
            response = await client.post(
                f"/api/v1/projects/{project_id}/security-scan",
                json={"scan_type": "config", "engine_mode": "native"},
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "cfg-task"
        delay_mock.assert_called_once()
        app.dependency_overrides = {}


class TestDASTScan:
    async def test_post_dast_dispatches_run_dast_scan(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        async def refresh(obj):
            obj.id = uuid.uuid4()
            obj.status = SimpleNamespace(value="pending")
            obj.created_at = None

        db.refresh.side_effect = refresh

        with patch(
            "app.api.routes.security_scan.run_dast_scan.delay",
            return_value=MagicMock(id="dast-task"),
        ) as delay_mock:
            response = await client.post(
                f"/api/v1/projects/{project_id}/security-scan",
                json={
                    "scan_type": "dast",
                    "engine_mode": "native",
                    "target_url": "https://demo.example.com",
                },
            )

        assert response.status_code == 202
        assert response.json()["task_id"] == "dast-task"
        delay_mock.assert_called_once()
        app.dependency_overrides = {}

    async def test_post_dast_without_target_url_returns_422(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        response = await client.post(
            f"/api/v1/projects/{project_id}/security-scan",
            json={"scan_type": "dast", "engine_mode": "native"},
        )

        assert response.status_code == 422
        app.dependency_overrides = {}


class TestScanSbom:
    async def test_get_sbom_returns_cyclonedx(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        scan_id = uuid.uuid4()
        db = AsyncMock()
        tenant_id = _override_auth(app, user, db)
        scan = _make_scan(tenant_id, project_id, id=scan_id)
        scan.scan_type = SimpleNamespace(value="dependency")
        scan.scan_metadata = {"cyclonedx": {"bomFormat": "CycloneDX"}, "spdx": {}}
        db.get.return_value = scan

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-scans/{scan_id}/sbom"
        )

        assert response.status_code == 200
        assert response.json()["bomFormat"] == "CycloneDX"
        app.dependency_overrides = {}

    async def test_get_sbom_wrong_scan_type_returns_400(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        scan_id = uuid.uuid4()
        db = AsyncMock()
        tenant_id = _override_auth(app, user, db)
        scan = _make_scan(tenant_id, project_id, id=scan_id)  # scan_type=sast
        db.get.return_value = scan

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-scans/{scan_id}/sbom"
        )

        assert response.status_code == 400
        app.dependency_overrides = {}

    async def test_get_sbom_not_generated_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        scan_id = uuid.uuid4()
        db = AsyncMock()
        tenant_id = _override_auth(app, user, db)
        scan = _make_scan(tenant_id, project_id, id=scan_id)
        scan.scan_type = SimpleNamespace(value="dependency")
        scan.scan_metadata = None
        db.get.return_value = scan

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-scans/{scan_id}/sbom"
        )

        assert response.status_code == 404
        app.dependency_overrides = {}
