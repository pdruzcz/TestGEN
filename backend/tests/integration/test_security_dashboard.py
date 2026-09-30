"""Integration tests for Story 4.8 risk dashboard route.

Covers GET /security-dashboard — CVSS distribution, top 10 and repair sequence.
The DB session is mocked so the test exercises routing + risk-engine wiring +
serialization only.
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
    from app.models.security_finding import AnalysisSource, ScanType, Severity

    return SimpleNamespace(
        id=kw.get("id", uuid.uuid4()),
        project_id=project_id,
        scan_id=uuid.uuid4(),
        scan_type=kw.get("scan_type", ScanType.SAST),
        vulnerability_type=kw.get("vuln", "sql_injection"),
        severity=kw.get("severity", Severity.MEDIUM),
        cwe_id=kw.get("cwe", "CWE-89"),
        owasp_category=None,
        file_path=kw.get("file_path", "app/db.py"),
        line_start=kw.get("line", 10),
        line_end=None,
        code_snippet=None,
        description="opis",
        confidence=0.7,
        source=kw.get("source", AnalysisSource.NATIVE),
        status="open",
        taint_path=None,
        recommendation=None,
        finding_metadata=kw.get("metadata"),
        cvss_score=None,
        cvss_vector=None,
        priority=None,
        effort=None,
        escalation_reason=None,
        created_at=None,
    )


class TestSecurityDashboard:
    async def test_dashboard_scores_and_prioritises(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        from app.models.security_finding import Severity

        findings = [
            _finding(project_id, cwe="CWE-89", severity=Severity.MEDIUM),  # → critical 9.8
            _finding(project_id, cwe="CWE-200", severity=Severity.LOW, line=20),  # medium
        ]
        result = MagicMock()
        result.scalars.return_value.all.return_value = findings
        db.execute.return_value = result

        response = await client.get(f"/api/v1/projects/{project_id}/security-dashboard")

        assert response.status_code == 200
        body = response.json()
        assert body["total_findings"] == 2
        assert body["cvss_distribution"]["critical"] == 1
        # SQLi finding lifted to critical and placed first in the repair sequence.
        assert body["repair_sequence"][0]["severity"] == "critical"
        assert body["repair_sequence"][0]["priority"] == 1
        assert body["top_10_findings"][0]["cvss_score"] == 9.8
        app.dependency_overrides = {}

    async def test_sast_dast_confirmed_finding_escalated(self, client, app):
        user = make_user()
        project_id = uuid.uuid4()
        db = AsyncMock()
        _override_auth(app, user, db)

        from app.models.security_finding import Severity

        # CSRF (CVSS 6.5, medium band) confirmed by SAST+DAST → escalated to high.
        findings = [
            _finding(
                project_id,
                cwe="CWE-352",
                vuln="csrf",
                severity=Severity.MEDIUM,
                metadata={"sources": ["sast", "dast"]},
            ),
        ]
        result = MagicMock()
        result.scalars.return_value.all.return_value = findings
        db.execute.return_value = result

        response = await client.get(f"/api/v1/projects/{project_id}/security-dashboard")

        assert response.status_code == 200
        body = response.json()
        assert body["top_10_findings"][0]["severity"] == "high"
        assert body["top_10_findings"][0]["escalation_reason"] is not None
        app.dependency_overrides = {}
