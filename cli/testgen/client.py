"""Klient HTTP API TestGEN — Story 8.10 (AC2, AC3, AC6).

Cienka warstwa nad ``httpx``: uwierzytelnianie, ścieżki, tłumaczenie błędów
na komunikaty zrozumiałe w terminalu. Logikę decyzji zostawiamy komendom.

Wszystkie błędy sieciowe lądują jako :class:`ConnectionFailed`, bo z punktu
widzenia użytkownika „DNS nie odpowiada" i „przekroczono limit czasu" wymagają
tej samej reakcji: sprawdzenia sieci i adresu.
"""

import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from testgen.errors import AuthError, CliError, ConnectionFailed

# Katalogi i pliki, których analiza nigdy nie potrzebuje — ich pakowanie
# wydłużałoby upload i analizę bez żadnego zysku.
DEFAULT_EXCLUDES: tuple[str, ...] = (
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "target",
    ".idea",
    ".vscode",
)
_EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".zip", ".log")
_EXCLUDED_NAMES = (".env", ".DS_Store")

# Frameworki mające własny endpoint generowania kodu. Pozostałe (pytest,
# junit, nunit, mocha, jest) powstają w pipelinie analizy — CLI mówi o tym
# wprost, zamiast odbijać się od 404.
CODEGEN_FRAMEWORKS: tuple[str, ...] = (
    "selenium",
    "playwright",
    "appium",
    "cypress",
    "sikulix",
    "phpunit",
    "pest",
    "unittest",
    "testng",
    "mstest",
    "database",
)
PIPELINE_FRAMEWORKS: tuple[str, ...] = ("pytest", "junit", "nunit", "mocha", "jest")


def iter_source_files(root: Path, excludes: tuple[str, ...]) -> Iterator[Path]:
    """Pliki do spakowania, z pominięciem katalogów bez wartości dla analizy."""
    skip = set(excludes)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip for part in path.relative_to(root).parts):
            continue
        if path.suffix in _EXCLUDED_SUFFIXES or path.name in _EXCLUDED_NAMES:
            continue
        yield path


def build_archive(root: Path, destination: Path, excludes: tuple[str, ...] = ()) -> int:
    """Pakuje katalog do archiwum ZIP. Zwraca liczbę spakowanych plików.

    Wysyłamy archiwum, a nie plik po pliku: serwer rozpakuje je po swojej
    stronie, więc zamiast setek żądań idzie jedno.
    """
    all_excludes = tuple(DEFAULT_EXCLUDES) + tuple(excludes)
    count = 0
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in iter_source_files(root, all_excludes):
            archive.write(path, path.relative_to(root).as_posix())
            count += 1
    if count == 0:
        raise CliError(
            f"Katalog {root} nie zawiera plików do analizy",
            hint="Sprawdź ścieżkę albo listę `exclude` w .testgen.yaml.",
        )
    return count


class TestGENClient:
    """Jedna sesja HTTP na jedno wywołanie CLI."""

    def __init__(self, api_url: str, token: str, timeout: int = 30) -> None:
        self.api_url = api_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.api_url}{path}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(method, url, headers=self._headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise ConnectionFailed(self.api_url, f"przekroczono limit {self._timeout} s") from exc
        except httpx.HTTPError as exc:
            raise ConnectionFailed(self.api_url, str(exc)) from exc

        return self._handle(response)

    def _handle(self, response: httpx.Response) -> Any:
        if response.status_code == 401:
            raise AuthError(
                "Serwer odrzucił poświadczenia",
                hint="Token mógł wygasnąć albo klucz został odwołany — zaloguj się ponownie.",
            )
        if response.status_code == 403:
            raise CliError(
                "Brak uprawnień do tej operacji",
                hint="Klucz o zakresie „tylko odczyt” nie może uruchamiać analiz ani wysyłać kodu.",
            )
        if response.status_code == 404:
            raise CliError(
                "Zasób nie istnieje albo należy do innej firmy",
                hint="Sprawdź identyfikator projektu.",
            )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            raise CliError(
                "Przekroczono limit żądań",
                hint=f"Spróbuj ponownie za {retry_after} s.",
            )
        if response.status_code >= 400:
            raise CliError(_problem_detail(response))

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    # ── operacje ────────────────────────────────────────────────────────────

    def whoami(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/users/me")

    def list_projects(self, page_size: int = 50) -> dict[str, Any]:
        return self._request(
            "GET", "/api/v1/projects", params={"page": 1, "page_size": page_size}
        )

    def upload_archive(self, project_id: str, archive: Path) -> dict[str, Any]:
        with archive.open("rb") as handle:
            return self._request(
                "POST",
                f"/api/v1/projects/{project_id}/upload",
                files={"files": (archive.name, handle, "application/zip")},
            )

    def start_analysis(
        self,
        project_id: str,
        *,
        engine_mode: str,
        modules: list[str],
        framework: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"engine_mode": engine_mode, "modules": modules}
        if framework:
            body["test_framework"] = framework
        return self._request("POST", f"/api/v1/projects/{project_id}/analyze", json=body)

    def task_status(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/tasks/{task_id}")

    def summary(self, project_id: str, threshold: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/v1/projects/{project_id}/ci-cd/summary",
            params={"threshold": threshold},
        )

    def list_test_cases(
        self, project_id: str, *, framework: str | None = None, page_size: int = 200
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"project_id": project_id, "page": 1, "page_size": page_size}
        if framework:
            params["framework"] = framework
        return self._request("GET", "/api/v1/test-cases", params=params)

    def start_security_scan(
        self, project_id: str, scan_type: str, target_url: str | None = None
    ) -> dict[str, Any]:
        # ``engine_mode`` celowo nie jest wysyłany — serwer bierze go z własnej
        # konfiguracji (routes/security_scan.py), więc pole i tak zostałoby
        # zignorowane, a sugerowałoby wpływ, którego CLI nie ma.
        body: dict[str, Any] = {"scan_type": scan_type}
        if target_url:
            body["target_url"] = target_url
        return self._request("POST", f"/api/v1/projects/{project_id}/security-scan", json=body)

    def list_findings(
        self, project_id: str, *, status: str | None = "open", page_size: int = 200
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": 1, "page_size": page_size}
        if status:
            params["status"] = status
        return self._request(
            "GET", f"/api/v1/projects/{project_id}/security-findings", params=params
        )

    def request_export(
        self, project_id: str, report_type: str, export_format: str, report: dict
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/projects/{project_id}/reports/export",
            json={"report_type": report_type, "format": export_format, "report": report},
        )

    def export_status(self, export_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/exports/{export_id}/status")

    def download_export(self, export_id: str, destination: Path) -> Path:
        url = f"{self.api_url}/api/v1/exports/{export_id}/download"
        try:
            with (
                httpx.Client(timeout=self._timeout) as client,
                client.stream("GET", url, headers=self._headers) as response,
            ):
                if response.status_code >= 400:
                    response.read()
                    self._handle(response)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        handle.write(chunk)
        except httpx.HTTPError as exc:
            raise ConnectionFailed(self.api_url, str(exc)) from exc
        return destination


def _problem_detail(response: httpx.Response) -> str:
    """Wyciąga ``detail`` z odpowiedzi RFC 7807; brak nie może zasłonić kodu."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    detail = body.get("detail") if isinstance(body, dict) else None
    return f"Serwer zwrócił błąd (HTTP {response.status_code})" + (f": {detail}" if detail else "")


def password_login(api_url: str, email: str, password: str, timeout: int = 30) -> dict[str, Any]:
    """Logowanie e-mailem — zwraca token dostępu albo listę organizacji.

    Serwer oddaje token w ciasteczku `access_token` (httpOnly), nie w treści
    odpowiedzi, bo endpoint powstał dla przeglądarki. CLI wyjmuje go z
    ciasteczka; to jedyna droga bez zmiany API.
    """
    base = api_url.rstrip("/")
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base}/api/v1/auth/login", json={"email": email, "password": password}
            )
            if response.status_code == 401:
                raise AuthError("Nieprawidłowy e-mail lub hasło")
            if response.status_code >= 400:
                raise CliError(_problem_detail(response))
            body = response.json()
            body["access_token"] = response.cookies.get("access_token")
            return body
    except httpx.TimeoutException as exc:
        raise ConnectionFailed(base, f"przekroczono limit {timeout} s") from exc
    except httpx.HTTPError as exc:
        raise ConnectionFailed(base, str(exc)) from exc


def select_tenant(api_url: str, pre_auth_token: str, tenant_id: str, timeout: int = 30) -> str:
    """Domyka logowanie użytkownika należącego do kilku organizacji."""
    base = api_url.rstrip("/")
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base}/api/v1/auth/select-tenant",
                json={"pre_auth_token": pre_auth_token, "tenant_id": tenant_id},
            )
            if response.status_code >= 400:
                raise CliError(_problem_detail(response))
            token = response.cookies.get("access_token")
    except httpx.TimeoutException as exc:
        raise ConnectionFailed(base, f"przekroczono limit {timeout} s") from exc
    except httpx.HTTPError as exc:
        raise ConnectionFailed(base, str(exc)) from exc

    if not token:
        raise AuthError("Serwer nie zwrócił tokenu dostępu")
    return token
