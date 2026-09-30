"""Tests for TestCase API routes - Story 1.31"""

from uuid import uuid4

import pytest

from app.models.test_case import (
    GenerationEngine,
    TestCaseStatus,
    TestFramework,
    TestPriority,
    TestType,
)
from app.schemas.test_case import (
    BulkActionResponse,
    TestCaseBulkDeleteRequest,
    TestCaseBulkUpdateRequest,
    TestCaseCreate,
    TestCaseExecutionResponse,
    TestCaseHistoryEntry,
    TestCaseHistoryResponse,
    TestCaseListResponse,
    TestCaseResponse,
    TestCaseUpdate,
)


class TestTestCaseCreate:
    """Test TestCaseCreate schema."""

    def test_minimal_creation(self):
        """Test creating test case with minimal fields."""
        data = TestCaseCreate(
            analysis_result_id=uuid4(),
            title="Test example",
        )

        assert data.title == "Test example"
        assert data.priority == TestPriority.MEDIUM
        assert data.type == TestType.UNIT
        assert data.generation_engine == GenerationEngine.NATIVE

    def test_full_creation(self):
        """Test creating test case with all fields."""
        data = TestCaseCreate(
            analysis_result_id=uuid4(),
            source_file_id=uuid4(),
            title="Full test case",
            description="Complete test case example",
            priority=TestPriority.HIGH,
            type=TestType.POSITIVE,
            framework=TestFramework.PYTEST,
            language="python",
            generation_engine=GenerationEngine.LLM,
            source_function="test_func",
            test_code="def test(): pass",
            test_data={"input": "value"},
            confidence_score=0.9,
            tags=["unit", "fast"],
        )

        assert data.title == "Full test case"
        assert data.priority == TestPriority.HIGH
        assert data.framework == TestFramework.PYTEST
        assert data.confidence_score == 0.9

    def test_title_validation_blank(self):
        """Test title validation rejects blank."""
        with pytest.raises(ValueError, match="blank"):
            TestCaseCreate(
                analysis_result_id=uuid4(),
                title="   ",
            )

    def test_confidence_score_validation(self):
        """Test confidence score bounds."""
        with pytest.raises(ValueError):
            TestCaseCreate(
                analysis_result_id=uuid4(),
                title="Test",
                confidence_score=1.5,
            )

        with pytest.raises(ValueError):
            TestCaseCreate(
                analysis_result_id=uuid4(),
                title="Test",
                confidence_score=-0.1,
            )


class TestTestCaseUpdate:
    """Test TestCaseUpdate schema."""

    def test_partial_update(self):
        """Test updating only some fields."""
        data = TestCaseUpdate(
            title="Updated title",
            priority=TestPriority.CRITICAL,
        )

        assert data.title == "Updated title"
        assert data.priority == TestPriority.CRITICAL
        assert data.type is None


class TestSchemaTestCaseResponse:
    """Test TestCaseResponse schema."""

    def test_response_fields(self):
        """Test response has all required fields."""
        # Mock data matching the response schema
        data = {
            "id": uuid4(),
            "tenant_id": uuid4(),
            "analysis_result_id": uuid4(),
            "title": "Test",
            "priority": "high",
            "type": "unit",
            "generation_engine": "native",
            "status": "draft",
            "execution_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "is_edited": False,
        }

        response = TestCaseResponse(**data)

        assert response.title == "Test"
        assert response.priority == "high"
        assert response.status == "draft"


class TestSchemaTestCaseListResponse:
    """Test TestCaseListResponse schema."""

    def test_list_response(self):
        """Test list response structure."""
        data = {
            "test_cases": [
                {
                    "id": uuid4(),
                    "tenant_id": uuid4(),
                    "analysis_result_id": uuid4(),
                    "title": "Test 1",
                    "priority": "high",
                    "type": "unit",
                    "generation_engine": "native",
                    "status": "draft",
                    "execution_count": 0,
                    "pass_count": 0,
                    "fail_count": 0,
                    "is_edited": False,
                },
                {
                    "id": uuid4(),
                    "tenant_id": uuid4(),
                    "analysis_result_id": uuid4(),
                    "title": "Test 2",
                    "priority": "medium",
                    "type": "integration",
                    "generation_engine": "native",
                    "status": "ready",
                    "execution_count": 0,
                    "pass_count": 0,
                    "fail_count": 0,
                    "is_edited": False,
                },
            ],
            "total": 2,
        }

        response = TestCaseListResponse(**data)

        assert len(response.test_cases) == 2
        assert response.total == 2


class TestSchemaTestCaseExecutionResponse:
    """Test TestCaseExecutionResponse schema."""

    def test_execution_response(self):
        """Test execution response structure."""
        data = {
            "id": uuid4(),
            "test_case_id": uuid4(),
            "executed_at": "2026-01-01T00:00:00",
            "status": "passed",
            "execution_duration_ms": 100,
            "coverage_percentage": 85.5,
        }

        response = TestCaseExecutionResponse(**data)

        assert response.status == "passed"
        assert response.execution_duration_ms == 100
        assert response.coverage_percentage == 85.5

    def test_execution_response_with_error(self):
        """Test execution response with error."""
        data = {
            "id": uuid4(),
            "test_case_id": uuid4(),
            "executed_at": "2026-01-01T00:00:00",
            "status": "failed",
            "error_message": "Test failed",
            "error_stack_trace": "Traceback...",
        }

        response = TestCaseExecutionResponse(**data)

        assert response.status == "failed"
        assert response.error_message == "Test failed"


class TestBulkSchemas:
    """Test bulk action schemas - Story 6.5."""

    def test_bulk_update_request(self):
        ids = [uuid4(), uuid4()]
        data = TestCaseBulkUpdateRequest(
            ids=ids,
            status=TestCaseStatus.READY,
            priority=TestPriority.HIGH,
        )
        assert data.ids == ids
        assert data.status == TestCaseStatus.READY
        assert data.priority == TestPriority.HIGH

    def test_bulk_update_requires_ids(self):
        with pytest.raises(ValueError):
            TestCaseBulkUpdateRequest(ids=[], status=TestCaseStatus.READY)

    def test_bulk_update_max_ids(self):
        with pytest.raises(ValueError):
            TestCaseBulkUpdateRequest(ids=[uuid4() for _ in range(201)])

    def test_bulk_delete_request(self):
        ids = [uuid4()]
        data = TestCaseBulkDeleteRequest(ids=ids)
        assert data.ids == ids

    def test_bulk_action_response(self):
        response = BulkActionResponse(affected=5)
        assert response.affected == 5


class TestHistorySchemas:
    """Test history schemas - Story 6.5, AC7."""

    def test_history_entry(self):
        entry = TestCaseHistoryEntry(
            changed_at="2026-01-01T12:00:00",
            author="user@example.com",
            action="test_case.update",
            field="title",
            old_value="Old",
            new_value="New",
        )
        assert entry.field == "title"
        assert entry.old_value == "Old"
        assert entry.new_value == "New"

    def test_history_response(self):
        response = TestCaseHistoryResponse(
            entries=[
                TestCaseHistoryEntry(
                    changed_at="2026-01-01T12:00:00",
                    action="test_case.status",
                    field="status",
                    old_value="draft",
                    new_value="ready",
                )
            ],
            total=1,
        )
        assert response.total == 1
        assert response.entries[0].author is None


class TestListProjectFilter:
    """GET /api/v1/test-cases?project_id= — filtr przez AnalysisResult.project_id.

    Bug: widok /projects/{id}/test-cases listował cały tenant, bo endpoint
    nie miał parametru projektu (TestCase nie ma bezpośredniego project_id).
    Test przechwytuje SQL i asseruje JOIN + warunek projektu w liście ORAZ
    w zapytaniu liczników statusów (inaczej header liczyłby cały tenant).
    """

    @pytest.fixture
    def app_with_capture(self):
        from unittest.mock import AsyncMock

        from app.core.dependencies import get_current_user, get_db, get_tenant
        from app.main import create_app
        from app.models.test_case import TestCaseStatus
        from tests.factories import make_user

        captured: list[str] = []

        class _CountResult:
            def all(self):
                return [(TestCaseStatus.READY, 2)]

        class _PageResult:
            def scalars(self):
                return self

            def all(self):
                return []

        async def fake_execute(q, *args, **kwargs):
            captured.append(str(q))
            return _CountResult() if "GROUP BY test_cases.status" in str(q) else _PageResult()

        db = AsyncMock()
        db.execute = fake_execute
        user = make_user()
        tenant_id = uuid4()

        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_tenant] = lambda: tenant_id
        app.dependency_overrides[get_db] = lambda: db
        yield app, captured
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_project_filter_applies_to_list_and_counts(self, app_with_capture):
        from httpx import ASGITransport, AsyncClient

        app, captured = app_with_capture
        pid = uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/test-cases?project_id={pid}")

        assert resp.status_code == 200, resp.text
        assert len(captured) == 2, "lista + liczniki statusów"
        for sql in captured:
            assert "analysis_results.project_id" in sql, sql

    @pytest.mark.asyncio
    async def test_no_project_filter_keeps_tenant_scope(self, app_with_capture):
        from httpx import ASGITransport, AsyncClient

        app, captured = app_with_capture
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/test-cases")

        assert resp.status_code == 200, resp.text
        for sql in captured:
            assert "JOIN analysis_results" not in sql, sql
