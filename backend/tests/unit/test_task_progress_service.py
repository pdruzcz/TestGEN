"""Tests for TaskProgressService — Redis-based task progress tracking (Story 1.10 Task 5)."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.services.task_progress_service import (
    TaskProgressService,
    get_task_progress_service,
)


@pytest.fixture
def mock_redis():
    return MagicMock()


@pytest.fixture
def service(mock_redis):
    return TaskProgressService(redis_client=mock_redis)


@pytest.fixture
def task_id():
    return str(uuid.uuid4())


@pytest.fixture
def tenant_id():
    return str(uuid.uuid4())


class TestInitTask:
    def test_init_task_sets_pending_status(self, service, mock_redis, task_id, tenant_id):
        mock_redis.hset.return_value = None
        mock_redis.expire.return_value = None

        service.init_task(task_id, tenant_id)

        mock_redis.hset.assert_called_once()
        call_args = mock_redis.hset.call_args
        assert call_args[0][0] == f"task:{task_id}:status"
        mapping = call_args[1].get("mapping") or call_args[0][1]
        assert mapping["status"] == "pending"
        assert mapping["tenant_id"] == tenant_id

    def test_init_task_sets_ttl(self, service, mock_redis, task_id, tenant_id):
        mock_redis.hset.return_value = None
        mock_redis.expire.return_value = None

        service.init_task(task_id, tenant_id)

        # TTL set on status key (24h = 86400s)
        expire_calls = mock_redis.expire.call_args_list
        assert any(c[0][0] == f"task:{task_id}:status" for c in expire_calls)


class TestUpdateProgress:
    def test_update_progress_sets_progress_hash(self, service, mock_redis, task_id):
        mock_redis.hset.return_value = None

        service.update_progress(task_id, 50, "Parsowanie AST")

        hset_calls = mock_redis.hset.call_args_list
        progress_call = [c for c in hset_calls if f"task:{task_id}:progress" in str(c)]
        assert len(progress_call) == 1
        mapping = progress_call[0][1].get("mapping") or progress_call[0][0][1]
        assert mapping["progress"] == "50"
        assert mapping["current_step"] == "Parsowanie AST"

    def test_update_progress_also_updates_status(self, service, mock_redis, task_id):
        mock_redis.hset.return_value = None

        service.update_progress(task_id, 50, "Parsowanie AST")

        # Should also update status to running
        hset_calls = mock_redis.hset.call_args_list
        status_call = [c for c in hset_calls if f"task:{task_id}:status" in str(c)]
        assert len(status_call) > 0


class TestCompleteTask:
    def test_complete_task_sets_completed(self, service, mock_redis, task_id):
        mock_redis.hset.return_value = None
        mock_redis.expire.return_value = None

        service.complete_task(task_id, result_url="/api/v1/results/abc")

        hset_calls = mock_redis.hset.call_args_list
        status_call = [c for c in hset_calls if f"task:{task_id}:status" in str(c)]
        assert len(status_call) > 0
        mapping = status_call[0][1].get("mapping") or status_call[0][0][1]
        assert mapping["status"] == "completed"
        assert mapping["result_url"] == "/api/v1/results/abc"

    def test_complete_task_sets_ttl(self, service, mock_redis, task_id):
        mock_redis.hset.return_value = None
        mock_redis.expire.return_value = None

        service.complete_task(task_id, result_url="/api/v1/results/abc")

        expire_calls = mock_redis.expire.call_args_list
        assert any(f"task:{task_id}:status" in str(c) for c in expire_calls)
        assert any(f"task:{task_id}:progress" in str(c) for c in expire_calls)


class TestFailTask:
    def test_fail_task_sets_failed_status(self, service, mock_redis, task_id):
        mock_redis.hset.return_value = None
        mock_redis.expire.return_value = None

        service.fail_task(task_id, "AST parsing failed: syntax error")

        hset_calls = mock_redis.hset.call_args_list
        status_call = [c for c in hset_calls if f"task:{task_id}:status" in str(c)]
        mapping = status_call[0][1].get("mapping") or status_call[0][0][1]
        assert mapping["status"] == "failed"
        assert mapping["error"] == "AST parsing failed: syntax error"


class TestTimeoutTask:
    def test_timeout_task_sets_timeout_status(self, service, mock_redis, task_id):
        mock_redis.hset.return_value = None
        mock_redis.expire.return_value = None

        service.timeout_task(task_id, last_progress=75)

        hset_calls = mock_redis.hset.call_args_list
        status_call = [c for c in hset_calls if f"task:{task_id}:status" in str(c)]
        mapping = status_call[0][1].get("mapping") or status_call[0][0][1]
        assert mapping["status"] == "timeout"

    def test_timeout_task_saves_last_progress(self, service, mock_redis, task_id):
        mock_redis.hset.return_value = None
        mock_redis.expire.return_value = None

        service.timeout_task(task_id, last_progress=75)

        hset_calls = mock_redis.hset.call_args_list
        progress_call = [c for c in hset_calls if f"task:{task_id}:progress" in str(c)]
        assert len(progress_call) == 1
        mapping = progress_call[0][1].get("mapping") or progress_call[0][0][1]
        assert mapping["progress"] == "75"

    def test_timeout_task_no_progress_when_zero(self, service, mock_redis, task_id):
        mock_redis.hset.return_value = None
        mock_redis.expire.return_value = None

        service.timeout_task(task_id, last_progress=0)

        hset_calls = mock_redis.hset.call_args_list
        progress_call = [c for c in hset_calls if f"task:{task_id}:progress" in str(c)]
        assert len(progress_call) == 0


class TestGetTaskStatus:
    def test_get_task_status_returns_full_status(self, service, mock_redis, task_id):
        mock_redis.hgetall.side_effect = [
            {"status": "running", "tenant_id": str(uuid.uuid4()), "error": "", "result_url": ""},
            {"progress": "50", "current_step": "Parsowanie AST"},
        ]

        result = service.get_task_status(task_id)

        assert result["status"] == "running"
        assert result["progress"] == 50
        assert result["current_step"] == "Parsowanie AST"

    def test_get_task_status_pending_no_progress(self, service, mock_redis, task_id):
        mock_redis.hgetall.side_effect = [
            {"status": "pending", "tenant_id": str(uuid.uuid4()), "error": "", "result_url": ""},
            {},
        ]

        result = service.get_task_status(task_id)

        assert result["status"] == "pending"
        assert result["progress"] == 0
        assert result["current_step"] == ""

    def test_get_task_status_nonexistent(self, service, mock_redis, task_id):
        mock_redis.hgetall.return_value = {}

        result = service.get_task_status(task_id)

        assert result is None


class TestPartialFailure:
    def test_partial_failure_sets_status(self, service, mock_redis, task_id):
        mock_redis.hset.return_value = None
        mock_redis.expire.return_value = None

        service.partial_failure(task_id, "AST parsing failed", completed_steps=["preprocessing"])

        hset_calls = mock_redis.hset.call_args_list
        status_call = [c for c in hset_calls if f"task:{task_id}:status" in str(c)]
        mapping = status_call[0][1].get("mapping") or status_call[0][0][1]
        assert mapping["status"] == "partial_failure"
        assert mapping["error"] == "AST parsing failed"


class TestGetService:
    def test_get_task_progress_service_returns_instance(self):
        svc = get_task_progress_service()
        assert isinstance(svc, TaskProgressService)
