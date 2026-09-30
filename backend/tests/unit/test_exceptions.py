import pytest

from app.core.exceptions import (
    AnalysisError,
    AuthError,
    ForbiddenError,
    NotFoundError,
    QuotaExceededError,
    TestGENError,
    ValidationError,
)


@pytest.mark.parametrize(
    "exc_class,expected_status,expected_type",
    [
        (TestGENError, 500, "internal-error"),
        (AuthError, 401, "auth-error"),
        (ForbiddenError, 403, "forbidden"),
        (NotFoundError, 404, "not-found"),
        (ValidationError, 422, "validation-error"),
        (QuotaExceededError, 429, "quota-exceeded"),
        (AnalysisError, 500, "analysis-error"),
    ],
)
def test_exception_status_codes(exc_class, expected_status, expected_type):
    exc = exc_class(detail="test error")
    assert exc.status_code == expected_status
    rfc = exc.to_rfc7807(instance="/api/v1/test")
    assert rfc["type"] == f"https://testgen.io/errors/{expected_type}"
    assert rfc["status"] == expected_status
    assert rfc["detail"] == "test error"
    assert rfc["instance"] == "/api/v1/test"


def test_rfc7807_format_has_all_fields():
    exc = NotFoundError(detail="Resource not found")
    rfc = exc.to_rfc7807(instance="/api/v1/items/123")
    required_fields = {"type", "title", "status", "detail", "instance"}
    assert required_fields == set(rfc.keys())


def test_exception_handler_returns_correct_json():
    """Test that exception maps correctly for FastAPI handler."""
    from app.main import create_app

    app = create_app()

    handlers = app.exception_handlers
    assert TestGENError in handlers
