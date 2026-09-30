"""Komenda ``analyze`` — Story 8.10 (AC2, AC5).

Pełna ścieżka: spakowanie katalogu, wysłanie, uruchomienie analizy i —
opcjonalnie — oczekiwanie na wynik wraz z werdyktem progu.

Werdykt liczy serwer (`/ci-cd/summary`), a nie to narzędzie. Dzięki temu
`testgen analyze --wait` i status check na pull requeście dają ten sam wynik;
gdyby CLI liczyło próg po swojemu, te same zmiany mogłyby dostać dwa różne
werdykty i nie dałoby się rozstrzygnąć, który jest prawdziwy.
"""

import tempfile
import time
from pathlib import Path
from typing import Any

from testgen.client import TestGENClient, build_archive
from testgen.config import Config
from testgen.errors import CliError, ThresholdExceeded
from testgen.output import Printer, findings_table

# Odstęp odpytywania. Analiza trwa minuty, więc częstsze pytanie nie przyspiesza
# wyniku, a zużywa wspólny limit żądań firmy.
POLL_INTERVAL_SECONDS = 10
_DONE = {"completed", "success"}
# Wszystkie końcowe stany porażki z ``TaskProgressService``. Brak któregoś
# oznaczałby, że CLI odpytuje zadanie, które już się nie zmieni, aż do
# własnego limitu czasu — i zgłasza „nie zakończyła się" zamiast powodu.
_FAILED = {"failed", "error", "cancelled", "timeout", "partial_failure"}


def run(
    client: TestGENClient,
    config: Config,
    printer: Printer,
    *,
    path: Path,
    modules: list[str],
    wait: bool,
    framework: str | None = None,
    timeout_minutes: int = 30,
    sleep=time.sleep,
) -> dict[str, Any]:
    project_id = config.require_project_id()
    source = path.resolve()
    if not source.is_dir():
        raise CliError(f"Katalog {source} nie istnieje")

    with tempfile.TemporaryDirectory(prefix="testgen-cli-") as tmp:
        archive = Path(tmp) / "zrodla.zip"
        printer.info(f"Pakuję {source}…")
        files = build_archive(source, archive, tuple(config.exclude))
        size_mb = archive.stat().st_size / (1024 * 1024)
        printer.info(f"Spakowano {files} plików ({size_mb:.1f} MB)")

        printer.info("Wysyłam kod do TestGEN…")
        client.upload_archive(project_id, archive)

    printer.info("Uruchamiam analizę…")
    accepted = client.start_analysis(
        project_id,
        engine_mode=config.engine_mode,
        modules=modules,
        framework=framework or config.default_framework,
    )
    task_id = accepted.get("task_id", "")
    printer.success(f"Analiza uruchomiona (zadanie {task_id})")

    result: dict[str, Any] = {
        "project_id": project_id,
        "task_id": task_id,
        "files_uploaded": files,
        "status": accepted.get("status", "pending"),
    }

    if not wait:
        result["hint"] = f"Śledź postęp: testgen status {task_id} --watch"
        printer.result(result)
        return result

    status = wait_for_task(client, printer, task_id, timeout_minutes, sleep=sleep)
    result["status"] = status

    summary = client.summary(project_id, config.severity_threshold)
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
    if not printer.is_machine:
        printer.info(summary.get("description", ""))

    if summary.get("should_fail"):
        raise ThresholdExceeded(summary.get("description", "Znaleziska powyżej progu"))
    return result


def wait_for_task(
    client: TestGENClient,
    printer: Printer,
    task_id: str,
    timeout_minutes: int,
    *,
    sleep=time.sleep,
) -> str:
    """Odpytuje o status aż do zakończenia. Zwraca końcowy status."""
    attempts = max(1, timeout_minutes * 60 // POLL_INTERVAL_SECONDS)
    for _ in range(attempts):
        payload = client.task_status(task_id)
        status = str(payload.get("status", ""))
        step = payload.get("current_step") or ""
        progress = payload.get("progress")
        printer.info(f"  {status} {progress or ''}% {step}".rstrip())

        if status in _DONE:
            return status
        if status in _FAILED:
            raise CliError(
                "Analiza zakończona błędem",
                hint=str(payload.get("error") or "Sprawdź szczegóły w interfejsie TestGEN."),
            )
        sleep(POLL_INTERVAL_SECONDS)

    raise CliError(
        f"Analiza nie zakończyła się w ciągu {timeout_minutes} min",
        hint=f"Zadanie nadal działa — sprawdź: testgen status {task_id}",
    )
