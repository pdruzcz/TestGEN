from typing import Any


class TestGENError(Exception):
    """Base exception for TestGEN platform."""

    status_code: int = 500
    error_type: str = "internal-error"
    title: str = "Internal Server Error"

    def __init__(self, detail: str = "An unexpected error occurred", **kwargs: Any) -> None:
        self.detail = detail
        self.extra = kwargs
        super().__init__(detail)

    def to_rfc7807(self, instance: str = "") -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": f"https://testgen.io/errors/{self.error_type}",
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
            "instance": instance,
        }
        if self.extra:
            body.update(self.extra)
        return body


class AuthError(TestGENError):
    status_code = 401
    error_type = "auth-error"
    title = "Authentication Error"


class ForbiddenError(TestGENError):
    status_code = 403
    error_type = "forbidden"
    title = "Forbidden"


class NotFoundError(TestGENError):
    status_code = 404
    error_type = "not-found"
    title = "Not Found"


class ValidationError(TestGENError):
    status_code = 422
    error_type = "validation-error"
    title = "Validation Error"


class QuotaExceededError(TestGENError):
    status_code = 429
    error_type = "quota-exceeded"
    title = "Quota Exceeded"


class FeatureRequiresPlanError(TestGENError):
    """Story 7.13 — moduł gated poniżej progu planu (wzorzec widoczne-zablokowane).

    Body (RFC7807 + extra): ``error="feature_requires_plan"``, ``feature``,
    ``required_plan``, ``upgrade_url`` — wzorzec QuotaExceededError (7.8).
    """

    status_code = 402
    error_type = "feature-requires-plan"
    title = "Feature Requires Plan"


class ConflictError(TestGENError):
    status_code = 409
    error_type = "conflict"
    title = "Conflict"


class AnalysisError(TestGENError):
    status_code = 500
    error_type = "analysis-error"
    title = "Analysis Error"
