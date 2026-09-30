"""Unit tests for the DAST runner — Story 4.6.

The ZAP container + REST API is replaced by a ``FakeZAPController``, so these
tests exercise the lifecycle orchestration, ZAP-alert parsing, risk/CWE mapping,
request/response sanitisation and SecurityFinding mapping with no network.
"""

import json
import uuid
from pathlib import Path

import pytest

from app.models.security_finding import ScanType, Severity
from app.services.security_scan.dast_runner import (
    AuthConfig,
    DASTRunner,
)

_FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures"
    / "security"
    / "zap_report_sample.json"
)


def _load_alerts() -> list[dict]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))["alerts"]


class FakeZAPController:
    """Records the lifecycle calls and returns canned alerts."""

    def __init__(self, alerts: list[dict], ready: bool = True, completed: bool = True):
        self._alerts = alerts
        self._ready = ready
        self._completed = completed
        self.calls: list[str] = []
        self.auth: AuthConfig | None = None

    async def start(self) -> None:
        self.calls.append("start")

    async def wait_ready(self, timeout: int) -> bool:
        self.calls.append("wait_ready")
        return self._ready

    async def configure_auth(self, auth: AuthConfig) -> bool:
        self.calls.append("configure_auth")
        self.auth = auth
        return True

    async def spider(self, target_url: str) -> None:
        self.calls.append("spider")

    async def active_scan(self, target_url: str) -> None:
        self.calls.append("active_scan")

    async def wait_completion(self, timeout: int) -> bool:
        self.calls.append("wait_completion")
        return self._completed

    async def get_alerts(self) -> list[dict]:
        self.calls.append("get_alerts")
        return self._alerts

    async def stop(self) -> None:
        self.calls.append("stop")


_IDS = (uuid.uuid4(), uuid.uuid4(), uuid.uuid4())  # project, tenant, scan


async def _run(controller, auth_config=None):
    runner = DASTRunner(db=None, controller=controller)
    return await runner.run_dast(
        _IDS[0], _IDS[1], _IDS[2], "https://demo.example.com", auth_config
    )


class TestLifecycle:
    async def test_full_lifecycle_called_in_order(self):
        controller = FakeZAPController(_load_alerts())
        await _run(controller)
        assert controller.calls == [
            "start",
            "wait_ready",
            "spider",
            "active_scan",
            "wait_completion",
            "get_alerts",
            "stop",
        ]

    async def test_stop_called_even_when_not_ready(self):
        controller = FakeZAPController([], ready=False)
        with pytest.raises(RuntimeError):
            await _run(controller)
        assert controller.calls[-1] == "stop"

    async def test_missing_target_url_raises(self):
        runner = DASTRunner(db=None, controller=FakeZAPController([]))
        with pytest.raises(ValueError):
            await runner.run_dast(_IDS[0], _IDS[1], _IDS[2], "", None)


class TestParsing:
    async def test_maps_all_alerts_to_findings(self):
        controller = FakeZAPController(_load_alerts())
        findings = await _run(controller)
        assert len(findings) == 5
        assert all(f.scan_type == ScanType.DAST for f in findings)

    async def test_risk_to_severity_mapping(self):
        findings = await _run(FakeZAPController(_load_alerts()))
        by_type = {f.vulnerability_type: f for f in findings}
        assert by_type["SQL Injection"].severity == Severity.HIGH
        assert by_type["Cross Site Scripting (Reflected)"].severity == Severity.MEDIUM
        assert by_type["Absence of Anti-CSRF Tokens"].severity == Severity.LOW
        assert by_type["Timestamp Disclosure"].severity == Severity.INFO

    async def test_cwe_from_alert_field(self):
        findings = await _run(FakeZAPController(_load_alerts()))
        sqli = next(f for f in findings if f.vulnerability_type == "SQL Injection")
        assert sqli.cwe_id == "CWE-89"

    async def test_cwe_fallback_from_plugin_id(self):
        # CSRF alert has cweid "-1" → fall back to the plugin map (CWE-352).
        findings = await _run(FakeZAPController(_load_alerts()))
        csrf = next(
            f for f in findings if f.vulnerability_type == "Absence of Anti-CSRF Tokens"
        )
        assert csrf.cwe_id == "CWE-352"

    async def test_url_recorded_as_file_path_and_metadata(self):
        findings = await _run(FakeZAPController(_load_alerts()))
        sqli = next(f for f in findings if f.vulnerability_type == "SQL Injection")
        assert sqli.file_path == "https://demo.example.com/login"
        assert sqli.finding_metadata["url"] == "https://demo.example.com/login"
        assert sqli.finding_metadata["method"] == "POST"
        assert sqli.recommendation == "Use parameterized queries."


class TestSanitization:
    async def test_sensitive_headers_redacted(self):
        findings = await _run(FakeZAPController(_load_alerts()))
        sqli = next(f for f in findings if f.vulnerability_type == "SQL Injection")
        request = sqli.finding_metadata["request"]
        response = sqli.finding_metadata["response"]
        assert "eyJsupersecret" not in request
        assert "abc123" not in request
        assert "Authorization: [REDACTED]" in request
        assert "Cookie: [REDACTED]" in request
        assert "Set-Cookie: [REDACTED]" in response

    async def test_inline_secret_token_redacted(self):
        findings = await _run(FakeZAPController(_load_alerts()))
        sqli = next(f for f in findings if f.vulnerability_type == "SQL Injection")
        assert "secretpass" not in sqli.finding_metadata["request"]

    async def test_api_key_header_redacted(self):
        findings = await _run(FakeZAPController(_load_alerts()))
        cmd = next(
            f for f in findings if f.vulnerability_type == "Remote OS Command Injection"
        )
        assert "topsecretkey" not in cmd.finding_metadata["request"]


class TestAuth:
    async def test_auth_config_passed_to_controller(self):
        controller = FakeZAPController(_load_alerts())
        await _run(controller, {"auth_type": "token", "token": "abc"})
        assert "configure_auth" in controller.calls
        assert controller.auth is not None
        assert controller.auth.auth_type == "token"

    async def test_no_auth_skips_configure(self):
        controller = FakeZAPController(_load_alerts())
        await _run(controller, None)
        assert "configure_auth" not in controller.calls

    def test_auth_config_from_dict_rejects_unknown_type(self):
        assert AuthConfig.from_dict({"auth_type": "bogus"}) is None
        assert AuthConfig.from_dict(None) is None

    def test_auth_config_from_dict_parses_form(self):
        auth = AuthConfig.from_dict(
            {
                "auth_type": "form",
                "login_url": "https://app/login",
                "username_field": "user",
                "password_field": "pass",
            }
        )
        assert auth is not None
        assert auth.auth_type == "form"
        assert auth.login_url == "https://app/login"
