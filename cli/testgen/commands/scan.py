"""Komenda ``scan`` — Story 8.10 (AC3, AC5).

Uruchamia skan bezpieczeństwa i — po jego zakończeniu — sprawdza werdykt
progu tym samym endpointem co bramka CI/CD, więc `testgen scan` i pipeline
nie mogą się rozjechać.
"""

import time
from typing import Any

from testgen.client import TestGENClient
from testgen.commands.analyze import wait_for_task
from testgen.config import THRESHOLDS, Config
from testgen.errors import CliError, ThresholdExceeded
from testgen.output import Printer, findings_table

SCAN_TYPES = ("sast", "taint", "dependency", "config", "dast")


def run(
    client: TestGENClient,
    config: Config,
    printer: Printer,
    *,
    scan_type: str,
    severity_threshold: str | None = None,
    target_url: str | None = None,
    wait: bool = True,
    timeout_minutes: int = 30,
    sleep=time.sleep,
) -> dict[str, Any]:
    if scan_type not in SCAN_TYPES:
        raise CliError(
            f"Nieznany typ skanu: {scan_type}",
            hint="Dozwolone: " + ", ".join(SCAN_TYPES),
        )
    if scan_type == "dast" and not target_url:
        raise CliError("Skan DAST wymaga --target-url")

    threshold = severity_threshold or config.severity_threshold
    if threshold not in THRESHOLDS:
        raise CliError(
            f"Nieprawidłowy próg: {threshold}",
            hint="Dozwolone: " + ", ".join(THRESHOLDS),
        )
    project_id = config.require_project_id()

    printer.info(f"Uruchamiam skan {scan_type}…")
    accepted = client.start_security_scan(project_id, scan_type, target_url)
    task_id = accepted.get("task_id")
    result: dict[str, Any] = {
        "project_id": project_id,
        "scan_id": accepted.get("scan_id"),
        "task_id": task_id,
        "scan_type": scan_type,
        "status": accepted.get("status", "pending"),
    }

    if not wait or not task_id:
        # Część typów skanu nie ma jeszcze zadania w tle — wtedy nie ma na co
        # czekać i kończymy na potwierdzeniu przyjęcia.
        printer.result(result)
        return result

    result["status"] = wait_for_task(client, printer, task_id, timeout_minutes, sleep=sleep)

    summary = client.summary(project_id, threshold)
    result["summary"] = {
        "threshold": summary.get("threshold"),
        "counts": summary.get("counts", {}),
        "total": summary.get("total", 0),
        "blocking": summary.get("blocking", 0),
        "should_fail": summary.get("should_fail", False),
        "description": summary.get("description", ""),
    }

    printer.result(
        result if printer.is_machine else result["summary"],
        table=None if printer.is_machine else findings_table(summary.get("counts", {})),
    )
    if summary.get("should_fail"):
        raise ThresholdExceeded(summary.get("description", "Znaleziska powyżej progu"))
    return result
