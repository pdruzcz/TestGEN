"""Wspólne atrapy testów CLI — Story 8.10."""

from pathlib import Path
from typing import Any

import pytest

from testgen.config import Config
from testgen.output import OutputFormat, Printer


class FakeClient:
    """Atrapa klienta API — zapamiętuje wywołania i oddaje zaplanowane odpowiedzi."""

    def __init__(self, **responses: Any) -> None:
        self.responses = responses
        self.calls: list[tuple[str, tuple, dict]] = []
        # Kolejne statusy zadania: każde odpytanie zdejmuje jeden.
        self.task_states: list[dict[str, Any]] = responses.get(
            "task_states", [{"task_id": "t1", "status": "completed", "progress": 100}]
        )

    def _record(self, name: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((name, args, kwargs))
        return self.responses.get(name, {})

    def whoami(self):
        return self._record("whoami")

    def list_projects(self, page_size: int = 50):
        return self._record("list_projects", page_size)

    def upload_archive(self, project_id: str, archive: Path):
        return self._record("upload_archive", project_id, archive)

    def start_analysis(self, project_id: str, **kwargs: Any):
        self._record("start_analysis", project_id, **kwargs)
        return self.responses.get("start_analysis", {"task_id": "t1", "status": "pending"})

    def task_status(self, task_id: str):
        self.calls.append(("task_status", (task_id,), {}))
        return self.task_states.pop(0) if len(self.task_states) > 1 else self.task_states[0]

    def summary(self, project_id: str, threshold: str):
        self._record("summary", project_id, threshold)
        return self.responses.get(
            "summary",
            {
                "threshold": threshold,
                "counts": {},
                "total": 0,
                "blocking": 0,
                "should_fail": False,
                "description": "Brak znalezisk",
            },
        )

    def list_test_cases(self, project_id: str, **kwargs: Any):
        self._record("list_test_cases", project_id, **kwargs)
        return self.responses.get("list_test_cases", {"items": []})

    def start_security_scan(self, project_id: str, scan_type: str, target_url: str | None = None):
        self._record("start_security_scan", project_id, scan_type, target_url)
        return self.responses.get(
            "start_security_scan", {"scan_id": "s1", "task_id": "t1", "status": "pending"}
        )

    def list_findings(self, project_id: str, **kwargs: Any):
        self._record("list_findings", project_id, **kwargs)
        return self.responses.get("list_findings", {"findings": []})

    def request_export(self, project_id: str, report_type: str, export_format: str, report: dict):
        self._record("request_export", project_id, report_type, export_format, report)
        return self.responses.get("request_export", {"export_id": "e1", "status": "pending"})

    def export_status(self, export_id: str):
        self._record("export_status", export_id)
        return self.responses.get(
            "export_status", {"export_id": export_id, "status": "done", "export_format": "pdf"}
        )

    def download_export(self, export_id: str, destination: Path):
        self._record("download_export", export_id, destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"%PDF-1.4")
        return destination

    def named(self, name: str) -> list[tuple]:
        return [call for call in self.calls if call[0] == name]


@pytest.fixture
def printer() -> Printer:
    return Printer(fmt=OutputFormat.JSON, quiet=True)


@pytest.fixture
def config() -> Config:
    return Config(
        api_url="https://api.example.test",
        api_key="tgn_test",
        project_id="11111111-1111-1111-1111-111111111111",
    ).validate()


@pytest.fixture
def no_sleep():
    return lambda _seconds: None
