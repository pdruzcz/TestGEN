"""Tests for Pydantic schemas — serialization and validation."""

import uuid
from datetime import UTC, datetime

import pytest

from app.schemas.analysis_result import AnalysisResultCreate, AnalysisResultResponse, AnalysisResultUpdate
from app.schemas.report import ReportCreate, ReportResponse, ReportUpdate
from app.schemas.source_file import SourceFileResponse
from app.schemas.tenant import TenantCreate, TenantResponse, TenantUpdate
from app.schemas.test_case import TestCaseCreate, TestCaseResponse, TestCaseUpdate
from app.schemas.test_code import TestCodeCreate, TestCodeResponse, TestCodeUpdate


class TestTenantSchemas:
    def test_tenant_create_valid(self):
        t = TenantCreate(name="Acme Corp", slug="acme-corp")
        assert t.name == "Acme Corp"
        assert t.slug == "acme-corp"

    def test_tenant_create_blank_name_rejected(self):
        with pytest.raises(ValueError):
            TenantCreate(name="  ", slug="test")

    def test_tenant_create_invalid_slug_format_rejected(self):
        with pytest.raises(ValueError, match="Slug must"):
            TenantCreate(name="Test", slug="INVALID SLUG!")

    def test_tenant_create_slug_with_uppercase_rejected(self):
        with pytest.raises(ValueError, match="Slug must"):
            TenantCreate(name="Test", slug="My-Company")

    def test_tenant_response_from_attributes(self):
        data = {
            "id": uuid.uuid4(),
            "name": "Acme",
            "slug": "acme",
            "nip": None,
            "plan": "basic",
            "is_active": True,
            "settings": None,
            "created_at": datetime.now(UTC),
            "updated_at": None,
        }
        resp = TenantResponse.model_validate(data)
        assert resp.name == "Acme"
        assert resp.plan == "basic"

    def test_tenant_update_partial(self):
        u = TenantUpdate(name="New Name")
        assert u.name == "New Name"
        assert u.nip is None
        assert u.plan is None


class TestSourceFileSchema:
    def test_source_file_response(self):
        data = {
            "id": uuid.uuid4(),
            "tenant_id": uuid.uuid4(),
            "project_id": uuid.uuid4(),
            "filename": "main.py",
            "original_path": "/src/main.py",
            "storage_key": "abc123",
            "file_size": 1024,
            "mime_type": "text/x-python",
            "sha256_hash": "a" * 64,
            "detected_language": "python",
            "detected_framework": None,
            "is_cleaned_up": False,
            "created_at": datetime.now(UTC),
            "updated_at": None,
        }
        resp = SourceFileResponse.model_validate(data)
        assert resp.filename == "main.py"
        assert resp.file_size == 1024


class TestAnalysisResultSchema:
    def test_analysis_result_response(self):
        data = {
            "id": uuid.uuid4(),
            "tenant_id": uuid.uuid4(),
            "project_id": uuid.uuid4(),
            "engine_mode": "hybrid",
            "module": "ast-parser",
            "status": "completed",
            "result_data": {"functions": 42},
            "duration_ms": 1500,
            "created_at": datetime.now(UTC),
            "updated_at": None,
        }
        resp = AnalysisResultResponse.model_validate(data)
        assert resp.module == "ast-parser"
        assert resp.result_data["functions"] == 42


class TestTestCaseSchema:
    def test_test_case_response(self):
        data = {
            "id": uuid.uuid4(),
            "tenant_id": uuid.uuid4(),
            "analysis_result_id": uuid.uuid4(),
            "title": "Test login with valid credentials",
            "description": "Verify user can log in",
            "priority": "high",
            "type": "unit",
            "framework": "pytest",
            "language": "python",
            "generation_engine": "native",
            "preconditions": {"user_exists": True},
            "steps": {"action": "navigate", "target": "/login"},
            "expected_result": "User is logged in",
            "status": "draft",
            "last_executed_at": None,
            "last_execution_result": None,
            "execution_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "is_edited": False,
            "reviewed_at": None,
            "reviewed_by": None,
            "tags": None,
            "meta": None,
            "created_at": datetime.now(UTC),
            "updated_at": None,
        }
        resp = TestCaseResponse.model_validate(data)
        assert resp.title == "Test login with valid credentials"
        assert resp.priority == "high"
        assert resp.steps is not None
        assert resp.steps["action"] == "navigate"


class TestTestCodeSchema:
    def test_test_code_response(self):
        data = {
            "id": uuid.uuid4(),
            "tenant_id": uuid.uuid4(),
            "test_case_id": uuid.uuid4(),
            "framework": "pytest",
            "language": "python",
            "code": "def test_login():\n    assert True",
            "file_path": "/tests/test_login.py",
            "created_at": datetime.now(UTC),
            "updated_at": None,
        }
        resp = TestCodeResponse.model_validate(data)
        assert resp.framework == "pytest"
        assert "def test_login" in resp.code


class TestReportSchemas:
    def test_report_create_valid(self):
        r = ReportCreate(project_id=uuid.uuid4(), title="Analysis Report", format="json", content={"key": "value"})
        assert r.title == "Analysis Report"

    def test_report_create_blank_title_rejected(self):
        with pytest.raises(ValueError):
            ReportCreate(project_id=uuid.uuid4(), title="  ")

    def test_report_response(self):
        data = {
            "id": uuid.uuid4(),
            "tenant_id": uuid.uuid4(),
            "project_id": uuid.uuid4(),
            "title": "Report 1",
            "format": "pdf",
            "content": {"key": "value"},
            "file_url": "https://storage.example.com/reports/1.pdf",
            "created_at": datetime.now(UTC),
            "updated_at": None,
        }
        resp = ReportResponse.model_validate(data)
        assert resp.format == "pdf"
        assert resp.file_url is not None

    def test_report_update_partial(self):
        u = ReportUpdate(title="Updated Report")
        assert u.title == "Updated Report"
        assert u.content is None
        assert u.file_url is None


class TestAnalysisResultSchemas:
    def test_analysis_result_create(self):
        c = AnalysisResultCreate(project_id=uuid.uuid4(), module="ast-parser")
        assert c.module == "ast-parser"
        assert c.engine_mode.value == "hybrid"

    def test_analysis_result_update(self):
        u = AnalysisResultUpdate(status="completed", duration_ms=1500)
        assert u.status.value == "completed"
        assert u.duration_ms == 1500

    def test_analysis_result_update_empty(self):
        u = AnalysisResultUpdate()
        assert u.status is None
        assert u.result_data is None


class TestTestCaseCreateUpdateSchemas:
    def test_test_case_create(self):
        c = TestCaseCreate(analysis_result_id=uuid.uuid4(), title="Login test")
        assert c.title == "Login test"
        assert c.priority.value == "medium"

    def test_test_case_create_blank_title_rejected(self):
        with pytest.raises(ValueError, match="blank"):
            TestCaseCreate(analysis_result_id=uuid.uuid4(), title="  ")

    def test_test_case_update(self):
        u = TestCaseUpdate(title="Updated title", priority="high")
        assert u.title == "Updated title"
        assert u.priority.value == "high"


class TestTestCodeCreateUpdateSchemas:
    def test_test_code_create(self):
        c = TestCodeCreate(
            test_case_id=uuid.uuid4(),
            framework="pytest",
            language="python",
            code="def test_x(): pass",
        )
        assert c.framework == "pytest"
        assert c.code == "def test_x(): pass"

    def test_test_code_update(self):
        u = TestCodeUpdate(code="def test_y(): pass")
        assert u.code == "def test_y(): pass"
        assert u.file_path is None

    def test_test_code_create_empty_code_rejected(self):
        with pytest.raises(ValueError):
            TestCodeCreate(test_case_id=uuid.uuid4(), framework="pytest", language="python", code="")
