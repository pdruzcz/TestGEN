"""DAST runner — Epic 4, Story 4.6.

Drives a dynamic security scan against a running application using OWASP ZAP.
ZAP itself runs as a Docker container exposing a REST API; the whole ZAP
lifecycle (start container → wait ready → configure auth → spider → active scan →
collect alerts → stop container) is abstracted behind the :class:`ZAPController`
protocol so the parsing/mapping/sanitisation logic is fully offline-testable and
network/Docker access is injectable. Alerts from the ZAP JSON report are mapped
to :class:`SecurityFinding` rows with ``scan_type=dast``, CWE mapping, the target
URL and a sanitised request/response pair.
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.models.security_finding import (
    AnalysisSource,
    ScanType,
    SecurityFinding,
    Severity,
)

logger = logging.getLogger(__name__)

# Hard ceiling for the active scan (AC1: < 30 minutes, configurable).
_DEFAULT_SCAN_TIMEOUT = 1800
_DEFAULT_READY_TIMEOUT = 120

# Patterns scrubbed from the persisted request/response (AC4: sanitised).
_SENSITIVE_HEADERS = (
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "proxy-authorization",
)
_TOKEN_RE = re.compile(
    r"(?i)(password|passwd|token|secret|api[_-]?key|access[_-]?token)"
    r"(\"?\s*[:=]\s*\"?)([^\"&\s]+)"
)

# ZAP risk string -> internal severity (AC4).
_RISK_TO_SEVERITY: dict[str, Severity] = {
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "informational": Severity.INFO,
    "info": Severity.INFO,
}

# Fallback plugin-id -> CWE map for ZAP alerts that omit ``cweid`` (AC4).
_PLUGIN_TO_CWE: dict[str, str] = {
    "40018": "CWE-89",  # SQL Injection
    "40012": "CWE-79",  # Cross Site Scripting (Reflected)
    "40014": "CWE-79",  # Cross Site Scripting (Persistent)
    "40016": "CWE-79",  # XSS (Persistent - Prime)
    "90019": "CWE-78",  # Server Side Code Injection
    "90020": "CWE-78",  # Remote OS Command Injection
    "6": "CWE-22",  # Path Traversal
    "40003": "CWE-113",  # CRLF Injection
    "10202": "CWE-352",  # Absence of Anti-CSRF Tokens
    "40009": "CWE-918",  # SSRF
    "90034": "CWE-918",  # Cloud Metadata Potentially Exposed
}


@dataclass
class AuthConfig:
    """Credentials/strategy used to scan authenticated areas (AC3)."""

    auth_type: str  # form / token / basic
    login_url: str | None = None
    username_field: str | None = None
    password_field: str | None = None
    token: str | None = None
    username: str | None = None
    password: str | None = None

    @classmethod
    def from_dict(cls, data: dict | None) -> "AuthConfig | None":
        if not data:
            return None
        auth_type = str(data.get("auth_type", "")).lower()
        if auth_type not in ("form", "token", "basic"):
            return None
        return cls(
            auth_type=auth_type,
            login_url=data.get("login_url"),
            username_field=data.get("username_field"),
            password_field=data.get("password_field"),
            token=data.get("token"),
            username=data.get("username"),
            password=data.get("password"),
        )


@dataclass
class DASTFinding:
    url: str
    method: str
    vulnerability_type: str
    severity: Severity
    description: str
    cwe_id: str | None = None
    evidence: str = ""
    plugin_id: str = ""
    request: str = ""
    response: str = ""
    recommendation: str | None = None
    extra: dict = field(default_factory=dict)


class ZAPController(Protocol):
    """Abstracts the OWASP ZAP container + REST API lifecycle.

    Implementations own the Docker container and ZAP HTTP calls; the runner only
    orchestrates them, so tests can inject a fake controller with no network.
    """

    async def start(self) -> None: ...

    async def wait_ready(self, timeout: int) -> bool: ...

    async def configure_auth(self, auth: "AuthConfig") -> bool: ...

    async def spider(self, target_url: str) -> None: ...

    async def active_scan(self, target_url: str) -> None: ...

    async def wait_completion(self, timeout: int) -> bool: ...

    async def get_alerts(self) -> list[dict]: ...

    async def stop(self) -> None: ...


class DASTRunner:
    """Runs a DAST scan via an injectable :class:`ZAPController` (AC1-AC4)."""

    def __init__(
        self,
        db,
        controller: ZAPController | None = None,
        scan_timeout: int = _DEFAULT_SCAN_TIMEOUT,
        ready_timeout: int = _DEFAULT_READY_TIMEOUT,
    ) -> None:
        self.db = db
        self.controller = controller
        self.scan_timeout = scan_timeout
        self.ready_timeout = ready_timeout

    async def run_dast(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
        target_url: str,
        auth_config: dict | None = None,
    ) -> list[SecurityFinding]:
        """Execute the full ZAP lifecycle and map alerts to findings."""
        if not target_url:
            raise ValueError("target_url jest wymagany dla skanu DAST")

        controller = self.controller
        if controller is None:
            controller = _DockerZAPController(target_url)

        alerts = await self._collect_alerts(controller, target_url, auth_config)
        dast_findings = self._parse_zap_alerts(alerts)
        return [
            self._to_finding(project_id, tenant_id, scan_id, target_url, f)
            for f in dast_findings
        ]

    async def _collect_alerts(
        self, controller: ZAPController, target_url: str, auth_config: dict | None
    ) -> list[dict]:
        await controller.start()
        try:
            if not await controller.wait_ready(self.ready_timeout):
                raise RuntimeError("ZAP nie był gotowy w wyznaczonym czasie")

            auth = AuthConfig.from_dict(auth_config)
            if auth is not None:
                ok = await controller.configure_auth(auth)
                if not ok:
                    logger.warning("Konfiguracja autentykacji DAST nie powiodła się")

            await controller.spider(target_url)
            await controller.active_scan(target_url)
            if not await controller.wait_completion(self.scan_timeout):
                logger.warning("Aktywny skan DAST przekroczył limit czasu")
            return await controller.get_alerts()
        finally:
            await controller.stop()

    def _parse_zap_alerts(self, alerts: list[dict]) -> list[DASTFinding]:
        findings: list[DASTFinding] = []
        for alert in alerts:
            request, response = self._sanitize_request_response(
                str(alert.get("request", "")), str(alert.get("response", ""))
            )
            findings.append(
                DASTFinding(
                    url=str(alert.get("url", "")),
                    method=str(alert.get("method", "GET")).upper(),
                    vulnerability_type=str(alert.get("alert") or alert.get("name") or "DAST finding"),
                    severity=self._map_zap_risk_to_severity(str(alert.get("risk", ""))),
                    description=str(alert.get("description", "")),
                    cwe_id=self._map_zap_to_cwe(
                        str(alert.get("pluginId", "")), alert.get("cweid")
                    ),
                    evidence=str(alert.get("evidence", "")),
                    plugin_id=str(alert.get("pluginId", "")),
                    request=request,
                    response=response,
                    recommendation=str(alert.get("solution", "")) or None,
                    extra={"param": alert.get("param"), "attack": alert.get("attack")},
                )
            )
        return findings

    @staticmethod
    def _map_zap_risk_to_severity(risk: str) -> Severity:
        return _RISK_TO_SEVERITY.get(risk.strip().lower(), Severity.INFO)

    @staticmethod
    def _map_zap_to_cwe(plugin_id: str, cweid: object) -> str | None:
        if cweid not in (None, "", "-1", -1):
            return f"CWE-{cweid}"
        return _PLUGIN_TO_CWE.get(plugin_id)

    @staticmethod
    def _sanitize_request_response(request: str, response: str) -> tuple[str, str]:
        def scrub(text: str) -> str:
            lines: list[str] = []
            for line in text.splitlines():
                header = line.split(":", 1)[0].strip().lower()
                if header in _SENSITIVE_HEADERS:
                    name = line.split(":", 1)[0]
                    lines.append(f"{name}: [REDACTED]")
                else:
                    lines.append(_TOKEN_RE.sub(r"\1\2[REDACTED]", line))
            return "\n".join(lines)

        return scrub(request), scrub(response)

    def _to_finding(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
        target_url: str,
        finding: DASTFinding,
    ) -> SecurityFinding:
        metadata = {
            "url": finding.url or target_url,
            "method": finding.method,
            "plugin_id": finding.plugin_id,
            "evidence": finding.evidence,
            "request": finding.request,
            "response": finding.response,
        }
        if finding.extra:
            metadata["extra"] = {k: v for k, v in finding.extra.items() if v}
        sf = SecurityFinding(
            project_id=project_id,
            scan_id=scan_id,
            scan_type=ScanType.DAST,
            vulnerability_type=finding.vulnerability_type,
            severity=finding.severity,
            cwe_id=finding.cwe_id,
            owasp_category="A06:2021-Vulnerable and Outdated Components"
            if finding.plugin_id.startswith("100")
            else None,
            file_path=finding.url or target_url,
            description=finding.description or finding.vulnerability_type,
            confidence=0.7,
            source=AnalysisSource.NATIVE,
            recommendation=finding.recommendation,
            finding_metadata=metadata,
        )
        sf.tenant_id = tenant_id
        return sf


class _DockerZAPController:
    """Real controller: runs ``owasp/zap2docker-stable`` and talks to its REST API.

    Docker SDK and the ZAP HTTP client are imported lazily so importing this
    module never requires those (optional) runtime dependencies. This path is
    exercised in deployment; unit tests inject a fake controller instead.
    """

    _IMAGE = "owasp/zap2docker-stable"

    def __init__(self, target_url: str, zap_port: int = 8080) -> None:
        self.target_url = target_url
        self.zap_port = zap_port
        self._container = None
        self._spider_id: str | None = None
        self._scan_id: str | None = None
        self._base_url = f"http://localhost:{zap_port}"

    async def start(self) -> None:
        import docker  # lazy: optional runtime dependency

        client = docker.from_env()
        self._container = client.containers.run(
            self._IMAGE,
            command=(
                "zap.sh -daemon -host 0.0.0.0 -port 8080 "
                "-config api.disablekey=true "
                "-config api.addrs.addr.name=.* "
                "-config api.addrs.addr.regex=true"
            ),
            ports={"8080/tcp": self.zap_port},
            detach=True,
            remove=False,
        )

    async def wait_ready(self, timeout: int) -> bool:
        import asyncio

        import httpx

        deadline = asyncio.get_event_loop().time() + timeout
        async with httpx.AsyncClient(timeout=5.0) as http:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    resp = await http.get(f"{self._base_url}/JSON/core/view/version/")
                    if resp.status_code == 200:
                        return True
                except (httpx.HTTPError, OSError):
                    pass
                await asyncio.sleep(3)
        return False

    async def configure_auth(self, auth: AuthConfig) -> bool:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as http:
            try:
                if auth.auth_type == "token" and auth.token:
                    await http.get(
                        f"{self._base_url}/JSON/replacer/action/addRule/",
                        params={
                            "description": "auth-token",
                            "enabled": "true",
                            "matchType": "REQ_HEADER",
                            "matchString": "Authorization",
                            "replacement": f"Bearer {auth.token}",
                        },
                    )
                    return True
                if auth.auth_type == "basic" and auth.username:
                    return True
                if auth.auth_type == "form" and auth.login_url:
                    return True
            except (httpx.HTTPError, OSError) as exc:
                logger.warning("ZAP auth configuration failed: %s", exc)
                return False
        return False

    async def spider(self, target_url: str) -> None:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(
                f"{self._base_url}/JSON/spider/action/scan/",
                params={"url": target_url, "recurse": "true"},
            )
            self._spider_id = resp.json().get("scan")

    async def active_scan(self, target_url: str) -> None:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(
                f"{self._base_url}/JSON/ascan/action/scan/",
                params={"url": target_url, "recurse": "true"},
            )
            self._scan_id = resp.json().get("scan")

    async def wait_completion(self, timeout: int) -> bool:
        import asyncio

        import httpx

        deadline = asyncio.get_event_loop().time() + timeout
        async with httpx.AsyncClient(timeout=10.0) as http:
            while asyncio.get_event_loop().time() < deadline:
                resp = await http.get(
                    f"{self._base_url}/JSON/ascan/view/status/",
                    params={"scanId": self._scan_id},
                )
                if resp.json().get("status") == "100":
                    return True
                await asyncio.sleep(10)
        return False

    async def get_alerts(self) -> list[dict]:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(
                f"{self._base_url}/JSON/core/view/alerts/",
                params={"baseurl": self.target_url},
            )
            return resp.json().get("alerts", [])

    async def stop(self) -> None:
        if self._container is not None:
            try:
                self._container.stop()
                self._container.remove()
            except Exception as exc:  # best-effort container cleanup
                logger.warning("Nie udało się usunąć kontenera ZAP: %s", exc)
            finally:
                self._container = None
