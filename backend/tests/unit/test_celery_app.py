"""Unit tests for Celery app configuration and TenantTask base class (Story 1.8).

These tests mock database connections and only verify configuration and behavior,
not actual connectivity.
"""

from unittest.mock import MagicMock, patch

import pytest


# Import celery_app with DB mocking to avoid connection attempts
@patch("app.core.database.create_async_engine", return_value=MagicMock())
@patch("app.core.database.create_engine", return_value=MagicMock())
class TestCeleryAppConfig:
    def test_serialization_is_json(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"
        assert "json" in celery_app.conf.accept_content

    def test_timezone_is_utc(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        assert celery_app.conf.timezone == "UTC"
        assert celery_app.conf.enable_utc is True

    def test_queues_defined(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        queue_names = [q.name for q in celery_app.conf.task_queues]
        assert "default" in queue_names
        assert "analysis" in queue_names
        assert "export" in queue_names
        assert "security" in queue_names

    def test_default_queue_is_default(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        assert celery_app.conf.task_default_queue == "default"

    def test_task_routing_analysis(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        route = celery_app.conf.task_routes.get("app.workers.tasks.analysis_tasks.*")
        assert route is not None
        assert route["queue"] == "analysis"

    def test_task_routing_pipeline(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        route = celery_app.conf.task_routes.get("analysis.run_pipeline")
        assert route is not None
        assert route["queue"] == "analysis"

    def test_task_routing_export(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        route = celery_app.conf.task_routes.get("app.workers.tasks.export_tasks.*")
        assert route is not None
        assert route["queue"] == "export"

    def test_task_routing_security(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        route = celery_app.conf.task_routes.get("app.workers.tasks.security_tasks.*")
        assert route is not None
        assert route["queue"] == "security"

    def test_beat_schedule_has_cleanup(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert "cleanup-source-files-daily" in schedule
        task = schedule["cleanup-source-files-daily"]
        assert task["task"] == "app.workers.tasks.cleanup_tasks.cleanup_source_files"
        assert task["options"]["queue"] == "default"

    def test_beat_schedule_has_cve(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert "cve-update-database-monthly" in schedule
        task = schedule["cve-update-database-monthly"]
        assert task["task"] == "security.update_cve_database"
        assert task["options"]["queue"] == "security"

    def test_ack_late_enabled(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        assert celery_app.conf.task_acks_late is True

    def test_track_started_enabled(self, _mock_sync, _mock_async):
        from app.workers.celery_app import celery_app

        assert celery_app.conf.task_track_started is True


class TestTaskRegistration:
    """Regresja (2026-09-14, sandbox): moduł tasków bez wpisu w
    ``app/workers/tasks/__init__.py`` jest na workerze „unregistered" —
    ``.delay()`` publikuje wiadomość, worker rzuca ``Received unregistered
    task`` (KeyError) i zadanie ginie. Tak padły: faktura VAT bez PDF
    (FV/2026/09/0001), odnowienia subskrypcji, progi limitów, snapshoty
    zużycia, gap/healing/recommendations. Każdy publiczny moduł pakietu
    MUSI być zaimportowany w ``__init__.py``.
    """

    def test_every_task_module_imported_in_package_init(self):
        import inspect
        import pkgutil
        import re

        from app.workers import tasks as tasks_pkg

        source = inspect.getsource(tasks_pkg)
        imported = set(re.findall(r"from app\.workers\.tasks\.(\w+) import", source))

        modules = {m.name for m in pkgutil.iter_modules(tasks_pkg.__path__) if not m.name.startswith("_")}

        missing = sorted(modules - imported)
        assert not missing, (
            f"Moduły tasków bez star-importu w app/workers/tasks/__init__.py "
            f"— worker rzuci 'unregistered task': {missing}"
        )


class TestTenantTask:
    def test_abstract_is_true(self):
        from app.workers.base_task import TenantTask

        assert TenantTask.abstract is True

    def test_raises_without_tenant_id(self):
        from app.workers.base_task import TenantTask
        from app.workers.celery_app import celery_app

        @celery_app.task(base=TenantTask, bind=True, name="test.no_tenant")
        def _test_task(self, **kwargs):
            return {"done": True}

        with pytest.raises(ValueError, match="tenant_id"):
            _test_task()

    @patch("app.workers.base_task.get_sync_session")
    @patch("app.workers.base_task.set_rls_context")
    def test_sets_rls_on_call(self, mock_rls, mock_session_gen):
        from app.workers.base_task import TenantTask
        from app.workers.celery_app import celery_app

        mock_session = MagicMock()

        def _session_gen():
            yield mock_session

        mock_session_gen.return_value = _session_gen()

        @celery_app.task(base=TenantTask, bind=True, name="test.rls_set")
        def _test_task(self, tenant_id, **kwargs):
            return {"tenant_id": str(tenant_id), "done": True}

        tenant_id = "11111111-1111-1111-1111-111111111111"
        result = _test_task(tenant_id)
        mock_rls.assert_called_once_with(mock_session, tenant_id)
        assert result["done"] is True

    @patch("app.workers.base_task._update_task_status")
    def test_on_failure_updates_status(self, mock_update):
        from app.workers.base_task import TenantTask
        from app.workers.celery_app import celery_app

        @celery_app.task(base=TenantTask, bind=True, name="test.on_fail")
        def _test_task(self, tenant_id, **kwargs):
            return {"done": True}

        _test_task.on_failure(ValueError("boom"), "task-123", [], {}, MagicMock())
        mock_update.assert_called_once_with("task-123", "failed", error="boom")

    @patch("app.workers.base_task._update_task_status")
    def test_on_success_updates_status(self, mock_update):
        from app.workers.base_task import TenantTask
        from app.workers.celery_app import celery_app

        @celery_app.task(base=TenantTask, bind=True, name="test.on_ok")
        def _test_task(self, tenant_id, **kwargs):
            return {"ok": True}

        _test_task.on_success({"ok": True}, "task-456", [], {})
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == "task-456"
        assert call_args[0][1] == "completed"

    @patch("app.workers.base_task._update_task_status")
    def test_on_retry_updates_status(self, mock_update):
        from app.workers.base_task import TenantTask
        from app.workers.celery_app import celery_app

        @celery_app.task(base=TenantTask, bind=True, name="test.on_retry")
        def _test_task(self, tenant_id, **kwargs):
            return {"done": True}

        _test_task.on_retry(ConnectionError("timeout"), "task-789", [], {"tenant_id": "t1"}, MagicMock())
        mock_update.assert_called_once_with("task-789", "retry", error="timeout")


class TestTaskProgress:
    @patch("app.workers.base_task._get_redis")
    def test_update_task_progress(self, mock_redis):
        from app.workers.base_task import _update_task_progress

        mock_r = MagicMock()
        mock_redis.return_value = mock_r

        _update_task_progress("task-1", 50, "Parsing AST")
        mock_r.hset.assert_called_once_with(
            "task:task-1:progress",
            mapping={"progress": "50", "current_step": "Parsing AST"},
        )

    @patch("app.workers.base_task._get_redis")
    def test_update_task_status(self, mock_redis):
        from app.workers.base_task import _update_task_status

        mock_r = MagicMock()
        mock_redis.return_value = mock_r

        _update_task_status("task-2", "completed", result="done")
        mock_r.hset.assert_called_once()
        # hset is called with (key, mapping=...) keyword args
        call_kwargs = mock_r.hset.call_args
        assert call_kwargs[0][0] == "task:task-2:status"
        mapping = call_kwargs[1]["mapping"]
        assert mapping["status"] == "completed"
