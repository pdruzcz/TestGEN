"""Integration tests for Story 4.11 patch routes.

Covers generate-patch / get / preview / download (per finding) and the batch +
conflicts endpoints. The DB session is mocked so the tests exercise routing,
patch-generator wiring and serialization.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.factories import make_user

_ORIGINAL = 'def login(uid):\n    cursor.execute("SELECT * FROM users WHERE id = " + uid)\n    return cursor.fetchone()\n'


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
    from app.models.security_finding import Severity

    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        project_id=project_id,
        vulnerability_type=kw.get("vuln", "sql_injection"),
        severity=kw.get("severity", Severity.HIGH),
        file_path=kw.get("file_path", "app/db.py"),
        line_start=kw.get("line_start", 2),
        line_end=kw.get("line_end", 2),
        code_snippet=kw.get("code_snippet", _ORIGINAL),
        finding_metadata=kw.get("finding_metadata"),
    )


def _execute_returning(findings):
    result = MagicMock()
    result.scalars.return_value.all.return_value = findings
    return result


class TestGeneratePatch:
    async def test_generate_patch_persists_and_returns(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding = _finding(project_id)
        db = AsyncMock()
        db.get.return_value = finding
        _override_auth(app, user, db)

        response = await client.post(
            f"/api/v1/projects/{project_id}/security-findings/{finding.id}/generate-patch",
            json={"engine_mode": "native"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["patch_content"].startswith("--- a/app/db.py")
        assert body["patch_filename"].endswith(".patch")
        assert finding.finding_metadata["patch"]["patch_content"] == body["patch_content"]
        db.commit.assert_awaited()
        app.dependency_overrides = {}

    async def test_missing_finding_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        db.get.return_value = None
        _override_auth(app, user, db)

        response = await client.post(
            f"/api/v1/projects/{project_id}/security-findings/{uuid.uuid4()}/generate-patch",
            json={"engine_mode": "native"},
        )

        assert response.status_code == 404
        app.dependency_overrides = {}


class TestGetAndDownloadPatch:
    async def test_get_existing_patch(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding = _finding(
            project_id,
            finding_metadata={
                "patch": {
                    "patch_content": "--- a/app/db.py\n+++ b/app/db.py\n",
                    "patch_filename": "fix_x.patch",
                    "is_valid": True,
                }
            },
        )
        db = AsyncMock()
        db.get.return_value = finding
        _override_auth(app, user, db)

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-findings/{finding.id}/patch"
        )

        assert response.status_code == 200
        assert response.json()["patch_filename"] == "fix_x.patch"
        app.dependency_overrides = {}

    async def test_get_patch_not_generated_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding = _finding(project_id, finding_metadata=None)
        db = AsyncMock()
        db.get.return_value = finding
        _override_auth(app, user, db)

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-findings/{finding.id}/patch"
        )

        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_download_returns_patch_file(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding = _finding(
            project_id,
            finding_metadata={
                "patch": {
                    "patch_content": "--- a/app/db.py\n+++ b/app/db.py\n",
                    "patch_filename": "fix_sql.patch",
                    "is_valid": True,
                }
            },
        )
        db = AsyncMock()
        db.get.return_value = finding
        _override_auth(app, user, db)

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-findings/{finding.id}/patch/download"
        )

        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        assert "fix_sql.patch" in response.headers["content-disposition"]
        app.dependency_overrides = {}


class TestPreview:
    async def test_preview_returns_before_after(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        finding = _finding(project_id)
        db = AsyncMock()
        db.get.return_value = finding
        _override_auth(app, user, db)

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-findings/{finding.id}/patch/preview"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["original_code"] == _ORIGINAL
        assert body["fixed_code"]
        app.dependency_overrides = {}


class TestBatchAndConflicts:
    async def test_batch_generates_patches_and_conflicts(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        a = _finding(project_id, line_start=2, line_end=2)
        b = _finding(project_id, line_start=2, line_end=3)
        db = AsyncMock()
        db.execute.return_value = _execute_returning([a, b])
        _override_auth(app, user, db)

        response = await client.post(
            f"/api/v1/projects/{project_id}/security-patches/batch",
            json={"engine_mode": "native"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["conflicts"]) == 1
        assert body["conflicts"][0]["severity"] == "critical"
        db.commit.assert_awaited()
        app.dependency_overrides = {}

    async def test_batch_no_findings_returns_404(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        db.execute.return_value = _execute_returning([])
        _override_auth(app, user, db)

        response = await client.post(
            f"/api/v1/projects/{project_id}/security-patches/batch",
            json={"engine_mode": "native"},
        )

        assert response.status_code == 404
        app.dependency_overrides = {}

    async def test_list_conflicts(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        a = _finding(project_id, line_start=5, line_end=10)
        b = _finding(project_id, line_start=8, line_end=12)
        db = AsyncMock()
        db.execute.return_value = _execute_returning([a, b])
        _override_auth(app, user, db)

        response = await client.get(
            f"/api/v1/projects/{project_id}/security-patches/conflicts"
        )

        assert response.status_code == 200
        conflicts = response.json()
        assert len(conflicts) == 1
        assert conflicts[0]["severity"] == "critical"
        app.dependency_overrides = {}
