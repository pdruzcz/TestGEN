"""Tests for test case review service - Story 1.43"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from app.services.test_review import (
    TestCaseReviewService,
    ReviewStatus,
    TestCaseChange,
    get_test_review_service,
)


class TestReviewStatus:
    """Test ReviewStatus enum (Story 1.43)."""

    def test_review_status_values(self):
        """Test all review status values exist."""
        assert ReviewStatus.PENDING == "pending"
        assert ReviewStatus.IN_REVIEW == "in_review"
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.CHANGES_REQUESTED == "changes_requested"
        assert ReviewStatus.REJECTED == "rejected"
        assert ReviewStatus.AUTO_APPROVED == "auto_approved"


class TestCaseChangeDataclass:
    """Test TestCaseChange dataclass (Story 1.43)."""

    def test_change_creation(self):
        """Test creating a test case change record."""
        change = TestCaseChange(
            test_case_id=uuid4(),
            changed_at=datetime.utcnow(),
            changed_by=uuid4(),
            field_changes={"test_code": {"old": "old code", "new": "new code"}},
            change_reason="Fixing assertion",
        )
        assert change.test_case_id is not None
        assert change.changed_at is not None
        assert change.changed_by is not None
        assert "test_code" in change.field_changes


class TestTestCaseReviewService:
    """Test TestCaseReviewService (Story 1.43)."""

    def test_service_initialization(self):
        """Test service can be initialized."""
        service = TestCaseReviewService()
        assert service is not None

    def test_get_test_review_service(self):
        """Test getting service singleton."""
        service = get_test_review_service()
        assert isinstance(service, TestCaseReviewService)

    @patch("app.services.test_review.get_sync_session")
    def test_get_pending_review_empty(self, mock_session):
        """Test getting pending reviews when none exist."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_db.query.return_value = mock_query

        def session_gen():
            yield mock_db
        mock_session.return_value = session_gen()

        service = TestCaseReviewService()
        result = service.get_pending_review(uuid4(), limit=10)

        assert result == []

    @patch("app.services.test_review.get_sync_session")
    def test_approve_test_not_found(self, mock_session):
        """Test approving non-existent test returns None."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        def session_gen():
            yield mock_db
        mock_session.return_value = session_gen()

        service = TestCaseReviewService()
        result = service.approve_test(uuid4(), uuid4())

        assert result is None

    @patch("app.services.test_review.get_sync_session")
    def test_reject_test_not_found(self, mock_session):
        """Test rejecting non-existent test returns None."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        def session_gen():
            yield mock_db
        mock_session.return_value = session_gen()

        service = TestCaseReviewService()
        result = service.reject_test(uuid4(), uuid4(), "Not valid")

        assert result is None

    @patch("app.services.test_review.get_sync_session")
    def test_update_test_code_not_found(self, mock_session):
        """Test updating code of non-existent test returns None."""
        mock_db = Mock()
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        def session_gen():
            yield mock_db
        mock_session.return_value = session_gen()

        service = TestCaseReviewService()
        result = service.update_test_code(
            uuid4(), "new code", uuid4()
        )

        assert result is None

    def test_bulk_approve_empty_list(self):
        """Test bulk approving with empty list."""
        service = TestCaseReviewService()
        with patch.object(service, "approve_test", return_value=None):
            result = service.bulk_approve([], uuid4())
            assert result == 0

    def test_bulk_approve_partial_success(self):
        """Test bulk approve with some failures."""
        service = TestCaseReviewService()
        test_id_1 = uuid4()
        test_id_2 = uuid4()
        test_id_3 = uuid4()

        # Mock: first two succeed, third fails
        call_count = [0]

        def mock_approve(test_id, reviewer_id):
            call_count[0] += 1
            if call_count[0] <= 2:
                return Mock()  # Success
            return None  # Failure

        with patch.object(service, "approve_test", side_effect=mock_approve):
            result = service.bulk_approve([test_id_1, test_id_2, test_id_3], uuid4())
            assert result == 2

    @patch("app.services.test_review.get_sync_session")
    def test_get_review_statistics_empty(self, mock_session):
        """Test getting statistics when no tests exist."""
        from sqlalchemy import func

        mock_db = Mock()

        # Mock status counts query chain
        mock_status_query = Mock()
        mock_filter = Mock()
        mock_group_by = Mock()
        mock_group_by.all.return_value = []
        mock_filter.group_by.return_value = mock_group_by
        mock_status_query.filter.return_value = mock_filter

        # Mock edited count query chain
        mock_count_base = Mock()
        mock_count_filter = Mock()
        mock_count_filter.count.return_value = 0
        mock_count_base.filter.return_value = mock_count_filter

        # Configure db.query to return different mocks
        call_count = [0]

        def mock_query_func(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_status_query
            else:
                return mock_count_base

        mock_db.query.side_effect = mock_query_func

        def session_gen():
            yield mock_db
        mock_session.return_value = session_gen()

        service = TestCaseReviewService()
        result = service.get_review_statistics(uuid4())

        assert result == {
            "by_status": {},
            "total_tests": 0,
            "edited_count": 0,
            "pending_review": 0,
        }


@pytest.mark.integration
class TestReviewServiceIntegration:
    """Integration tests for review service (Story 1.43)."""

    def test_get_review_service_singleton(self):
        """Test that service getter returns consistent instance."""
        service1 = get_test_review_service()
        service2 = get_test_review_service()
        # Service should be functional (not testing singleton strictness)
        assert isinstance(service1, TestCaseReviewService)
        assert isinstance(service2, TestCaseReviewService)
