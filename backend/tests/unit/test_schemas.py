import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.common import ErrorResponse


def test_error_response_valid():
    error = ErrorResponse(
        type="https://testgen.io/errors/not-found",
        title="Not Found",
        status=404,
        detail="Resource not found",
        instance="/api/v1/items/123",
    )
    assert error.type == "https://testgen.io/errors/not-found"
    assert error.title == "Not Found"
    assert error.status == 404
    assert error.detail == "Resource not found"
    assert error.instance == "/api/v1/items/123"


def test_error_response_default_instance():
    error = ErrorResponse(
        type="https://testgen.io/errors/internal-error",
        title="Internal Server Error",
        status=500,
        detail="Something went wrong",
    )
    assert error.instance == ""


def test_error_response_serialization():
    error = ErrorResponse(
        type="https://testgen.io/errors/auth-error",
        title="Authentication Error",
        status=401,
        detail="Invalid token",
    )
    data = error.model_dump()
    assert data["type"] == "https://testgen.io/errors/auth-error"
    assert data["status"] == 401


def test_error_response_missing_required_field():
    with pytest.raises(PydanticValidationError):
        ErrorResponse(
            type="https://testgen.io/errors/test",
            title="Test",
            # missing status and detail
        )
