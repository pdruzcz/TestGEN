"""Tests for QuotaExceededError RFC 7807 format (Story 1.10 Task 6)."""

from app.core.exceptions import QuotaExceededError


class TestQuotaExceededError:
    def test_rfc7807_includes_quota_fields(self):
        exc = QuotaExceededError(
            detail="Monthly analysis limit reached",
            limit=10,
            used=10,
            plan="basic",
            upgrade_url="/pricing",
        )
        body = exc.to_rfc7807(instance="/api/v1/projects/123/analyze")

        assert body["type"] == "https://testgen.io/errors/quota-exceeded"
        assert body["title"] == "Quota Exceeded"
        assert body["status"] == 429
        assert body["detail"] == "Monthly analysis limit reached"
        assert body["limit"] == 10
        assert body["used"] == 10
        assert body["plan"] == "basic"
        assert body["upgrade_url"] == "/pricing"

    def test_rfc7807_without_quota_fields(self):
        exc = QuotaExceededError(detail="Limit exceeded")
        body = exc.to_rfc7807()
        assert "limit" not in body
        assert "used" not in body
        assert "plan" not in body
        assert "upgrade_url" not in body

    def test_status_code_is_429(self):
        exc = QuotaExceededError(detail="test")
        assert exc.status_code == 429

    def test_retry_after_in_extra(self):
        exc = QuotaExceededError(
            detail="Rate limited",
            retry_after=3600,
        )
        assert exc.extra["retry_after"] == 3600
        body = exc.to_rfc7807()
        assert body["retry_after"] == 3600
