"""Task progress tracking in Redis — async for API, sync for Celery workers.

Redis key structure:
  - ``task:{task_id}:status`` — hash: status, tenant_id, error, result_url
  - ``task:{task_id}:progress`` — hash: progress, current_step

TTL: 24h (86400s) after task reaches a terminal state.
"""

import json
import logging
from typing import Any

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

STATUS_TTL_SECONDS = 86400  # 24h


class TaskProgressService:
    """Sync Redis task progress service (Celery workers)."""

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis = redis_client

    @property
    def redis(self) -> redis.Redis:
        if self._redis is None:
            settings = get_settings()
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def init_task(self, task_id: str, tenant_id: str) -> None:
        self.redis.hset(
            f"task:{task_id}:status",
            mapping={
                "status": "pending",
                "tenant_id": tenant_id,
                "error": "",
                "result_url": "",
            },
        )
        self.redis.expire(f"task:{task_id}:status", STATUS_TTL_SECONDS)

    def update_progress(self, task_id: str, progress: int, current_step: str) -> None:
        self.redis.hset(
            f"task:{task_id}:progress",
            mapping={"progress": str(progress), "current_step": current_step},
        )
        self.redis.hset(f"task:{task_id}:status", mapping={"status": "running"})

    def complete_task(self, task_id: str, result_url: str) -> None:
        self.redis.hset(
            f"task:{task_id}:status",
            mapping={"status": "completed", "result_url": result_url},
        )
        self._set_terminal_ttl(task_id)

    def fail_task(self, task_id: str, error: str) -> None:
        self.redis.hset(
            f"task:{task_id}:status",
            mapping={"status": "failed", "error": error},
        )
        self._set_terminal_ttl(task_id)

    def cancel_task(self, task_id: str) -> None:
        """Oznacz zadanie jako anulowane (Story 6.3 AC5). Samo przerwanie
        workera robi ``celery_app.control.revoke`` po stronie route'u."""
        self.redis.hset(
            f"task:{task_id}:status",
            mapping={"status": "cancelled"},
        )
        self._set_terminal_ttl(task_id)

    def timeout_task(self, task_id: str, last_progress: int = 0) -> None:
        self.redis.hset(
            f"task:{task_id}:status",
            mapping={"status": "timeout"},
        )
        if last_progress > 0:
            self.redis.hset(
                f"task:{task_id}:progress",
                mapping={"progress": str(last_progress)},
            )
        self._set_terminal_ttl(task_id)

    def partial_failure(self, task_id: str, error: str, completed_steps: list[str] | None = None) -> None:
        mapping: dict[str, Any] = {"status": "partial_failure", "error": error}
        if completed_steps:
            mapping["completed_steps"] = json.dumps(completed_steps)
        self.redis.hset(f"task:{task_id}:status", mapping=mapping)
        self._set_terminal_ttl(task_id)

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        try:
            status_data = self.redis.hgetall(f"task:{task_id}:status")
        except redis.ConnectionError:
            logger.error("Redis connection failed reading status for task=%s", task_id)
            return None
        if not status_data:
            return None

        try:
            progress_data = self.redis.hgetall(f"task:{task_id}:progress")
        except redis.ConnectionError:
            progress_data = {}

        return {
            "task_id": task_id,
            "status": status_data.get("status", "pending"),
            "tenant_id": status_data.get("tenant_id", ""),
            "progress": int(progress_data.get("progress", "0")),
            "current_step": progress_data.get("current_step", ""),
            "error": status_data.get("error", ""),
            "result_url": status_data.get("result_url", ""),
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _set_terminal_ttl(self, task_id: str) -> None:
        self.redis.expire(f"task:{task_id}:status", STATUS_TTL_SECONDS)
        self.redis.expire(f"task:{task_id}:progress", STATUS_TTL_SECONDS)


def get_task_progress_service() -> TaskProgressService:
    return TaskProgressService()
