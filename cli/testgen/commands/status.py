"""Komenda ``status`` — Story 8.10 (AC3)."""

import time
from typing import Any

from testgen.client import TestGENClient
from testgen.commands.analyze import _DONE, _FAILED
from testgen.errors import CliError
from testgen.output import Printer

# Krótszy odstęp niż przy analizie: tu użytkownik patrzy na terminal
# i oczekuje reakcji, a nie odpala setek zapytań w tle.
WATCH_INTERVAL_SECONDS = 5


def run(
    client: TestGENClient,
    printer: Printer,
    *,
    task_id: str,
    watch: bool,
    max_checks: int = 720,
    sleep=time.sleep,
) -> dict[str, Any]:
    payload = client.task_status(task_id)
    if not watch:
        printer.result(_view(payload))
        return payload

    for _ in range(max_checks):
        status = str(payload.get("status", ""))
        progress = payload.get("progress") or ""
        step = payload.get("current_step") or ""
        printer.info(f"  {status} {progress}% {step}".rstrip())
        if status in _DONE or status in _FAILED:
            printer.result(_view(payload))
            return payload
        sleep(WATCH_INTERVAL_SECONDS)
        payload = client.task_status(task_id)

    raise CliError("Zadanie nie zakończyło się w oczekiwanym czasie")


def _view(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": payload.get("task_id"),
        "status": payload.get("status"),
        "progress": payload.get("progress"),
        "current_step": payload.get("current_step"),
        "error": payload.get("error"),
    }
