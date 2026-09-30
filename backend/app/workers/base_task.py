"""Base Celery task class with RLS tenant context, retry, and timeout handling.

Every Celery task that touches the database should inherit from
:class:`TenantTask` so that Row-Level Security is automatically applied.
"""

import contextlib
import json
import logging
from typing import Any

import redis
from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.core.database import get_sync_session, set_rls_context
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def _update_task_progress(task_id: str, progress: int, current_step: str) -> None:
    """Update task progress in Redis (key: ``task:{task_id}:progress``)."""
    r = _get_redis()
    r.hset(
        f"task:{task_id}:progress",
        mapping={"progress": str(progress), "current_step": current_step},
    )


def _update_task_status(task_id: str, status: str, **extra: Any) -> None:
    """Update task status in Redis (key: ``task:{task_id}:status``)."""
    r = _get_redis()
    data = {"status": status, **{k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in extra.items()}}
    r.hset(f"task:{task_id}:status", mapping=data)


class TenantTask(celery_app.Task):
    """Base task that sets RLS tenant context before execution.

    Usage::

        @celery_app.task(bind=True, base=TenantTask)
        def my_task(self, tenant_id: str, **kwargs):
            # RLS is already set — just use self.session
            ...
    """

    abstract = True
    _session = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        tenant_id = kwargs.get("tenant_id") or (args[0] if args else None)
        if tenant_id is None:
            raise ValueError("TenantTask requires tenant_id as first positional arg or keyword arg")

        ctx = contextlib.closing(get_sync_session())
        session_gen = ctx.__enter__()
        self._session = next(session_gen)
        try:
            set_rls_context(self._session, str(tenant_id))
            logger.info("task=%s tenant=%s — RLS context set", self.name, tenant_id)
            return super().__call__(*args, **kwargs)
        finally:
            ctx.__exit__(None, None, None)
            self._session = None

    def on_retry(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        logger.warning(
            "task=%s id=%s retry — %s",
            self.name,
            task_id,
            exc,
            extra={"tenant_id": kwargs.get("tenant_id", args[0] if args else None)},
        )
        _update_task_status(task_id, "retry", error=str(exc))

    def on_failure(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        logger.error(
            "task=%s id=%s failed — %s",
            self.name,
            task_id,
            exc,
            extra={"tenant_id": kwargs.get("tenant_id", args[0] if args else None)},
        )
        _update_task_status(task_id, "failed", error=str(exc))

    def on_success(self, retval: Any, task_id: str, args: Any, kwargs: Any) -> None:
        logger.info(
            "task=%s id=%s completed",
            self.name,
            task_id,
            extra={"tenant_id": kwargs.get("tenant_id", args[0] if args else None)},
        )
        _update_task_status(task_id, "completed", result=json.dumps(retval) if isinstance(retval, (dict, list)) else str(retval))
