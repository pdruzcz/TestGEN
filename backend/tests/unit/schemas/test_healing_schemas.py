"""Tests for healing Pydantic schemas — Story 1.51."""

import uuid
from datetime import UTC, datetime

import pytest

from app.schemas.healing import (
    HealingDecisionRequest,
    HealingDecisionResponse,
    HealingItemResponse,
    HealingReportResponse,
    HealRequest,
    HealTriggerResponse,
)


class TestHealRequest:
    def test_valid(self):
        req = HealRequest(version_a="v1", version_b="v2")
        assert req.version_a == "v1"
        assert req.version_b == "v2"

    def test_equal_versions_rejected(self):
        with pytest.raises(ValueError, match="must differ"):
            HealRequest(version_a="same", version_b="same")

    def test_blank_version_rejected(self):
        with pytest.raises(ValueError):
            HealRequest(version_a="", version_b="v2")

    def test_extra_ignored(self):
        req = HealRequest(version_a="v1", version_b="v2", bogus="x")
        assert not hasattr(req, "bogus")


class TestHealingDecisionRequest:
    def test_accept(self):
        assert HealingDecisionRequest(action="accept").action == "accept"

    def test_reject(self):
        assert HealingDecisionRequest(action="reject").action == "reject"

    def test_invalid_action_rejected(self):
        with pytest.raises(ValueError):
            HealingDecisionRequest(action="maybe")


class TestHealingItemResponse:
    def test_from_attributes(self):
        data = {
            "id": uuid.uuid4(),
            "report_id": uuid.uuid4(),
            "test_code_id": uuid.uuid4(),
            "old_locator": "#old-btn",
            "old_strategy": "css",
            "new_locator": "[data-testid='login-btn']",
            "new_strategy": "data-testid",
            "confidence": 0.92,
            "healing_method": "hybrid",
            "status": "healed",
            "diff_preview": "- #old-btn\n+ [data-testid='login-btn']",
            "created_at": datetime.now(UTC),
        }
        item = HealingItemResponse.model_validate(data)
        assert item.confidence == 0.92
        assert item.status == "healed"
        assert item.new_strategy == "data-testid"


class TestHealingReportResponse:
    def test_from_attributes_with_items(self):
        item_id = uuid.uuid4()
        report_id = uuid.uuid4()
        project_id = uuid.uuid4()
        data = {
            "id": report_id,
            "project_id": project_id,
            "version_a": "abc123",
            "version_b": "def456",
            "status": "healed",
            "stats": {"total": 5, "healed": 3, "avg_confidence": 0.88},
            "created_at": datetime.now(UTC),
            "items": [
                {
                    "id": item_id,
                    "report_id": report_id,
                    "test_code_id": uuid.uuid4(),
                    "old_locator": "#x",
                    "old_strategy": "css",
                    "new_locator": "[data-testid='x']",
                    "new_strategy": "data-testid",
                    "confidence": 0.9,
                    "healing_method": "native",
                    "status": "healed",
                    "diff_preview": None,
                    "created_at": datetime.now(UTC),
                }
            ],
        }
        report = HealingReportResponse.model_validate(data)
        assert report.status == "healed"
        assert report.stats["healed"] == 3
        assert len(report.items) == 1
        assert report.items[0].confidence == 0.9


class TestHealTriggerResponse:
    def test_defaults(self):
        rid = uuid.uuid4()
        resp = HealTriggerResponse(task_id="task-1", report_id=rid)
        assert resp.task_id == "task-1"
        assert resp.report_id == rid
        assert resp.status == "pending"


class TestHealingDecisionResponse:
    def test_accept_applied(self):
        resp = HealingDecisionResponse(item_id=uuid.uuid4(), status="healed", applied=True)
        assert resp.applied is True
