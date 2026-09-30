"""Test case review and editing service - Story 1.43

Provides UI and API for reviewing and editing generated test cases:
- View generated test cases
- Edit test code inline
- Approve/reject workflow
- Change tracking (diff from original)
- Bulk operations
- Review status management

Enables quality control over generated tests.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.core.database import get_sync_session
from app.models.test_case import TestCase, TestCaseStatus

logger = logging.getLogger(__name__)


class ReviewStatus(StrEnum):
    """Review status of test case."""
    PENDING = "pending"  # Not yet reviewed
    IN_REVIEW = "in_review"  # Currently being reviewed
    APPROVED = "approved"  # Approved without changes
    CHANGES_REQUESTED = "changes_requested"  # Needs modifications
    REJECTED = "rejected"  # Discarded
    AUTO_APPROVED = "auto_approved"  # Auto-approved by system


@dataclass
class TestCaseChange:
    """Track changes made to a test case."""
    test_case_id: UUID
    changed_at: datetime
    changed_by: UUID | None
    field_changes: dict[str, Any]  # field_name: {old: value, new: value}
    change_reason: str | None = None


class TestCaseReviewService:
    """Service for managing test case review and editing."""

    def get_pending_review(self, project_id: UUID, limit: int = 50) -> list[TestCase]:
        """Get test cases pending review."""
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                # Filter by draft status (pending review)
                tests = (
                    db.query(TestCase)
                    .filter(
                        TestCase.tenant_id == project_id,
                        TestCase.status == TestCaseStatus.DRAFT,
                    )
                    .order_by(TestCase.created_at.desc())
                    .limit(limit)
                    .all()
                )

                return tests
            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to get pending reviews: {e}")
            return []

    def approve_test(self, test_case_id: UUID, reviewer_id: UUID) -> TestCase | None:
        """Approve a test case for execution."""
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                test = (
                    db.query(TestCase)
                    .filter(TestCase.id == test_case_id)
                    .first()
                )

                if not test:
                    return None

                # Update status to ready
                test.status = TestCaseStatus.READY
                test.reviewed_at = datetime.utcnow()
                test.reviewed_by = reviewer_id

                db.commit()
                db.refresh(test)

                logger.info(f"Test case {test_case_id} approved by {reviewer_id}")
                return test

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to approve test case: {e}")
            return None

    def reject_test(self, test_case_id: UUID, reviewer_id: UUID, reason: str) -> TestCase | None:
        """Reject and delete a test case."""
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                test = (
                    db.query(TestCase)
                    .filter(TestCase.id == test_case_id)
                    .first()
                )

                if not test:
                    return None

                # Store rejection reason in meta before deleting
                if not test.meta:
                    test.meta = {}
                test.meta["rejection_reason"] = reason
                test.meta["rejected_by"] = str(reviewer_id)
                test.meta["rejected_at"] = datetime.utcnow().isoformat()

                db.delete(test)
                db.commit()

                logger.info(f"Test case {test_case_id} rejected by {reviewer_id}: {reason}")
                return test

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to reject test case: {e}")
            return None

    def update_test_code(
        self, test_case_id: UUID, new_code: str, editor_id: UUID
    ) -> TestCase | None:
        """Update test code with edits."""
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                test = (
                    db.query(TestCase)
                    .filter(TestCase.id == test_case_id)
                    .first()
                )

                if not test:
                    return None

                # Store original code for diff tracking
                if not test.meta:
                    test.meta = {}
                test.meta["original_code"] = test.test_code
                test.meta["last_edited_by"] = str(editor_id)
                test.meta["last_edited_at"] = datetime.utcnow().isoformat()

                # Update code
                test.test_code = new_code
                test.is_edited = True

                db.commit()
                db.refresh(test)

                logger.info(f"Test case {test_case_id} code updated by {editor_id}")
                return test

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to update test code: {e}")
            return None

    def bulk_approve(
        self, test_case_ids: list[UUID], reviewer_id: UUID
    ) -> int:
        """Bulk approve multiple test cases."""
        approved_count = 0

        for test_id in test_case_ids:
            if self.approve_test(test_id, reviewer_id):
                approved_count += 1

        logger.info(f"Bulk approved {approved_count}/{len(test_case_ids)} test cases")
        return approved_count

    def get_review_statistics(self, project_id: UUID) -> dict[str, Any]:
        """Get review statistics for a project."""
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                # Count by status
                from sqlalchemy import func

                status_counts = (
                    db.query(TestCase.status, func.count(TestCase.id))
                    .filter(TestCase.tenant_id == project_id)
                    .group_by(TestCase.status)
                    .all()
                )

                by_status = {status.value: count for status, count in status_counts}

                # Count edited tests
                edited_count = (
                    db.query(TestCase)
                    .filter(
                        TestCase.tenant_id == project_id,
                        TestCase.is_edited == True,
                    )
                    .count()
                )

                return {
                    "by_status": by_status,
                    "total_tests": sum(by_status.values()),
                    "edited_count": edited_count,
                    "pending_review": by_status.get("draft", 0),
                }

            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to get review statistics: {e}")
            return {}


def get_test_review_service() -> TestCaseReviewService:
    """Get or create test review service instance."""
    return TestCaseReviewService()
