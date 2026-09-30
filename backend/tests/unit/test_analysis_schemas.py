"""Tests for analysis Pydantic schemas (Story DEMO-001, Task 4, AC#1)."""

import uuid

import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisResponse, LLMError


def test_analysis_response_valid():
    file_id = uuid.uuid4()
    project_id = uuid.uuid4()
    resp = AnalysisResponse(
        analysis={"raw_response": '{"structures": []}', "model": "glm-5.1", "usage": {}},
        file_id=file_id,
        project_id=project_id,
    )
    assert resp.file_id == file_id
    assert resp.project_id == project_id
    assert resp.analysis["model"] == "glm-5.1"


def test_analysis_response_requires_fields():
    with pytest.raises(ValidationError):
        AnalysisResponse(analysis={}, file_id=uuid.uuid4())


def test_llm_error_defaults():
    err = LLMError(detail="LLM service unavailable")
    assert err.detail == "LLM service unavailable"
    assert err.status_code == 502
    assert err.error_type == "llm-error"
