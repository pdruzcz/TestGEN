"""Tests for task and analysis schemas (Story 1.10, 6.3)."""

import pytest
from pydantic import ValidationError

from app.schemas.task_schemas import (
    AnalysisAcceptedResponse,
    AnalysisRequest,
    CancelTaskResponse,
    EngineMode,
    TaskStatusResponse,
)


class TestAnalysisRequest:
    """Story 6.3 — request accepts engine_mode + test_framework + LLM options."""

    def test_defaults(self):
        req = AnalysisRequest()
        assert req.modules == ["code_analysis"]
        assert req.engine_mode is None
        assert req.test_framework is None
        assert req.llm_model is None
        assert req.temperature is None
        assert req.max_tokens is None

    def test_custom_modules(self):
        req = AnalysisRequest(modules=["code_analysis", "security"])
        assert len(req.modules) == 2

    def test_engine_mode_enum_coercion(self):
        req = AnalysisRequest(engine_mode="llm")
        assert req.engine_mode == EngineMode.LLM

    def test_invalid_engine_mode_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(engine_mode="invalid")

    def test_temperature_range_enforced(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(temperature=3.0)
        with pytest.raises(ValidationError):
            AnalysisRequest(temperature=-0.1)
        # Boundary valid
        req = AnalysisRequest(temperature=2.0)
        assert req.temperature == 2.0

    def test_max_tokens_range_enforced(self):
        with pytest.raises(ValidationError):
            AnalysisRequest(max_tokens=0)
        with pytest.raises(ValidationError):
            AnalysisRequest(max_tokens=300_000)
        req = AnalysisRequest(max_tokens=4096)
        assert req.max_tokens == 4096

    def test_test_framework_accepts_e2e_values(self):
        """Story 1.56 (AC3) — AnalysisRequest przyjmuje selenium/playwright/appium."""
        for fw in ("selenium", "playwright", "appium"):
            req = AnalysisRequest(test_framework=fw)
            assert req.test_framework is not None
            assert req.test_framework.value == fw

    def test_test_framework_accepts_native_framework_values(self):
        """Story 1.57 (AC3) — AnalysisRequest przyjmuje unittest/testng/mstest."""
        for fw in ("unittest", "testng", "mstest"):
            req = AnalysisRequest(test_framework=fw)
            assert req.test_framework is not None
            assert req.test_framework.value == fw

    def test_test_framework_rejects_unknown_value(self):
        """Story 1.56 — walidacja wartości (422 na wejściu API)."""
        with pytest.raises(ValidationError):
            AnalysisRequest(test_framework="robotframework")


class TestAnalysisAcceptedResponse:
    def test_response_fields(self):
        resp = AnalysisAcceptedResponse(
            task_id="abc-123",
            status="pending",
            status_url="/api/v1/tasks/abc-123",
        )
        assert resp.task_id == "abc-123"
        assert resp.status == "pending"
        assert resp.status_url == "/api/v1/tasks/abc-123"

    def test_default_status(self):
        resp = AnalysisAcceptedResponse(
            task_id="x",
            status_url="/tasks/x",
        )
        assert resp.status == "pending"


class TestTaskStatusResponse:
    def test_full_response(self):
        resp = TaskStatusResponse(
            task_id="abc",
            status="running",
            progress=50,
            current_step="Parsowanie AST",
            result_url=None,
            error=None,
        )
        assert resp.status == "running"
        assert resp.progress == 50

    def test_completed_with_result(self):
        resp = TaskStatusResponse(
            task_id="abc",
            status="completed",
            progress=100,
            current_step="export",
            result_url="/api/v1/tasks/abc/result",
            error=None,
        )
        assert resp.result_url is not None

    def test_failed_with_error(self):
        resp = TaskStatusResponse(
            task_id="abc",
            status="failed",
            progress=30,
            current_step="ast_parsing",
            result_url=None,
            error="Syntax error in file",
        )
        assert resp.error is not None

    def test_defaults(self):
        resp = TaskStatusResponse(task_id="x", status="pending")
        assert resp.progress == 0
        assert resp.current_step == ""
        assert resp.result_url is None
        assert resp.error is None


class TestCancelTaskResponse:
    def test_default_status(self):
        resp = CancelTaskResponse(task_id="abc")
        assert resp.status == "cancelled"

    def test_explicit_fields(self):
        resp = CancelTaskResponse(task_id="abc", status="cancelled")
        assert resp.task_id == "abc"
