"""Komenda ``export`` — Story 8.10 (AC3).

Eksport raportu wymaga danych raportu w żądaniu (`ReportExportRequest`) —
serwer renderuje to, co dostanie, zamiast samodzielnie agregować. CLI składa
więc ten sam kształt co interfejs: podsumowanie znalezisk z `/ci-cd/summary`
plus lista otwartych znalezisk.
"""

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from testgen.client import TestGENClient
from testgen.config import Config
from testgen.errors import CliError
from testgen.output import Printer

EXPORT_FORMATS = ("pdf", "html", "csv", "xlsx", "json", "yaml")
POLL_INTERVAL_SECONDS = 2
MAX_POLLS = 150


def run(
    client: TestGENClient,
    config: Config,
    printer: Printer,
    *,
    export_format: str,
    output: Path | None,
    report_type: str = "both",
    sleep=time.sleep,
) -> dict[str, Any]:
    if export_format not in EXPORT_FORMATS:
        raise CliError(
            f"Nieobsługiwany format: {export_format}",
            hint="Dozwolone: " + ", ".join(EXPORT_FORMATS),
        )
    project_id = config.require_project_id()

    printer.info("Zbieram dane raportu…")
    summary = client.summary(project_id, config.severity_threshold)
    findings = (client.list_findings(project_id).get("findings")) or []
    report = build_report(project_id, summary, findings)

    printer.info(f"Zlecam eksport ({export_format})…")
    accepted = client.request_export(project_id, report_type, export_format, report)
    export_id = accepted.get("export_id", "")

    status = _wait_for_export(client, export_id, sleep=sleep)
    destination = output or Path(f"raport_{project_id}.{status.get('export_format', export_format)}")
    client.download_export(export_id, destination)

    result = {
        "project_id": project_id,
        "export_id": export_id,
        "format": export_format,
        "output": str(destination),
        "findings_included": len(findings),
    }
    printer.result(result)
    printer.success(f"Zapisano raport: {destination}")
    return result


def _wait_for_export(client: TestGENClient, export_id: str, *, sleep) -> dict[str, Any]:
    for _ in range(MAX_POLLS):
        status = client.export_status(export_id)
        state = status.get("status")
        if state == "done":
            return status
        if state == "error":
            raise CliError(
                "Serwer nie zdołał wygenerować raportu",
                hint=str(status.get("error") or ""),
            )
        sleep(POLL_INTERVAL_SECONDS)
    raise CliError("Eksport nie zakończył się w oczekiwanym czasie")


def build_report(
    project_id: str, summary: dict[str, Any], findings: list[dict[str, Any]]
) -> dict[str, Any]:
    """Składa ładunek raportu w kształcie oczekiwanym przez `/reports/export`."""
    counts = summary.get("counts") or {}
    return {
        "project_id": project_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "kpis": {
            "total_findings": int(summary.get("total") or 0),
            "critical_count": int(counts.get("critical") or 0),
            "high_count": int(counts.get("high") or 0),
            "medium_count": int(counts.get("medium") or 0),
            "low_count": int(counts.get("low") or 0),
        },
        "severity_counts": {k: int(v) for k, v in counts.items()},
        "module_scores": [],
        "trend_points": [],
        "conclusions": [summary.get("description") or ""],
        "findings": [_finding(item) for item in findings],
    }


def _finding(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "source": "security",
        "title": str(item.get("title") or item.get("vulnerability_type") or ""),
        "description": str(item.get("description") or ""),
        "severity": str(item.get("severity") or "low"),
        "cwe_id": item.get("cwe_id"),
        "cvss_score": item.get("cvss_score"),
        "file_path": item.get("file_path"),
        "line_start": item.get("line_start"),
        "code_snippet": item.get("code_snippet"),
        "language": item.get("language"),
        "recommendation": item.get("recommendation"),
    }
