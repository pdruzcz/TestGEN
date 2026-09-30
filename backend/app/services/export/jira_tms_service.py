"""Klient Jira dla systemów zarządzania testami — Epic 8, Story 8.9.

Osobny moduł od ``services/integrations/jira_service.py`` (Story 5.8), który
zakłada w Jirze **zgłoszenia** z luk funkcjonalnych: tamten jest synchroniczny,
operuje na ``IntegrationConfig`` i ma zupełnie inny kontrakt. Tutaj chodzi
o eksport przypadków testowych przez wtyczki Xray i Zephyr Scale — kształt
bliźniaczy do ``testrail_service`` (Story 8.8), żeby obie ścieżki eksportu
zachowywały się tak samo.

Obie wtyczki żyją w tej samej instancji Jiry, ale mają rozłączne API:

* **Xray** trzyma testy jako zgłoszenia Jiry, więc szukamy ich JQL-em,
  a aktualizujemy zwykłym ``PUT /issue/{key}``. Znacznik TestGEN idzie
  w etykiecie, bo etykiety są przeszukiwalne JQL-em bez konfigurowania
  pola własnego w instancji klienta.
* **Zephyr Scale** ma własny magazyn testów pod ``/rest/atm/1.0`` i własne
  klucze — tam znacznik trafia do pola własnego.
"""

import asyncio
import base64
import logging
import time
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.core.exceptions import TestGENError, ValidationError

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
# Jira Cloud dławi przy gęstych seriach; eksport setki testów to setka wywołań.
MIN_REQUEST_INTERVAL_SECONDS = 0.5

JIRA_API = "/rest/api/3"
XRAY_API = "/rest/raven/1.0"
ZEPHYR_API = "/rest/atm/1.0"

# Prefiks etykiety wiążącej zgłoszenie Xray z przypadkiem TestGEN.
XRAY_LABEL_PREFIX = "testgen-"
# Pole własne Zephyra z identyfikatorem TestGEN.
ZEPHYR_TESTGEN_FIELD = "testgen_id"

_MAX_SEARCH_RESULTS = 50


class JiraTmsError(TestGENError):
    """Błąd komunikacji z Jirą lub jej wtyczką — mapowany na 502."""

    status_code = 502
    error_type = "jira-tms-error"
    title = "Jira TMS API Error"


def normalize_url(url: str) -> str:
    """Sprowadza adres instancji do ``https://host``.

    Wymuszamy HTTPS — tym kanałem leci token w nagłówku Basic Auth.
    """
    candidate = (url or "").strip().rstrip("/")
    if not candidate:
        raise ValidationError("Adres instancji Jira jest wymagany")
    if not candidate.startswith("https://"):
        raise ValidationError("Adres instancji Jira musi zaczynać się od https://")
    parsed = urlparse(candidate)
    if not parsed.netloc:
        raise ValidationError("Nieprawidłowy adres instancji Jira")
    return f"https://{parsed.netloc}"


def testgen_label(test_case_id: str) -> str:
    """Etykieta Jiry z identyfikatorem TestGEN.

    Jira nie dopuszcza spacji w etykietach, a myślniki i owszem — UUID
    przechodzi bez zmian.
    """
    return f"{XRAY_LABEL_PREFIX}{test_case_id}"


class JiraTmsClient:
    """Klient jednej instancji Jiry. Jedna instancja na jeden eksport."""

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self.base_url = normalize_url(base_url)
        self._email = email
        self._api_token = api_token
        self._last_request_at = 0.0

    @property
    def _headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self._email}:{self._api_token}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            await asyncio.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        await self._throttle()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                response = await client.request(
                    method, f"{self.base_url}{path}", headers=self._headers, **kwargs
                )
            except httpx.HTTPError as exc:
                raise JiraTmsError(f"Brak połączenia z Jira: {exc}") from exc

        if response.status_code == 401:
            raise JiraTmsError("Jira odrzuciła poświadczenia — sprawdź e-mail i token API")
        if response.status_code == 403:
            raise JiraTmsError("Brak uprawnień w Jirze do tej operacji")
        if response.status_code == 404:
            raise JiraTmsError(
                "Zasób nie istnieje albo wtyczka nie jest zainstalowana w tej instancji Jiry"
            )
        if response.status_code == 429:
            raise JiraTmsError("Jira ograniczyła tempo żądań — spróbuj ponownie za chwilę")
        if response.status_code >= 400:
            raise JiraTmsError(_error_message(response))

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    # ── wspólne ─────────────────────────────────────────────────────────────

    async def test_connection(self, project_key: str) -> dict[str, Any]:
        """Sprawdza poświadczenia i dostęp do projektu Jiry (AC1)."""
        me = await self._request("GET", f"{JIRA_API}/myself")
        project = await self._request("GET", f"{JIRA_API}/project/{quote(project_key)}")
        return {
            "connected": True,
            "account": me.get("displayName") or me.get("emailAddress") or "",
            "project_key": project.get("key") or project_key,
            "project_name": project.get("name") or "",
        }

    # ── Xray ────────────────────────────────────────────────────────────────

    async def xray_import_tests(self, tests: list[dict[str, Any]]) -> dict[str, Any]:
        """Import wsadowy testów do Xraya (AC2)."""
        return await self._request("POST", f"{XRAY_API}/import/test", json={"tests": tests})

    async def xray_find_by_testgen_id(
        self, project_key: str, test_case_id: str
    ) -> dict[str, Any] | None:
        """Szuka zgłoszenia Xray po etykiecie TestGEN (AC4)."""
        jql = f'project = "{project_key}" AND labels = "{testgen_label(test_case_id)}"'
        result = await self._request(
            "GET",
            f"{JIRA_API}/search",
            params={"jql": jql, "maxResults": 1, "fields": "summary,labels"},
        )
        issues = result.get("issues") or []
        return issues[0] if issues else None

    async def xray_find_all_testgen(self, project_key: str) -> dict[str, dict[str, Any]]:
        """Indeks zgłoszeń Xray oznaczonych TestGEN, po identyfikatorze przypadku.

        Jedno zapytanie zamiast jednego na przypadek — przy limicie tempa Jiry
        różnica to minuty.
        """
        index: dict[str, dict[str, Any]] = {}
        start_at = 0
        # JQL nie ma operatora „etykieta zaczyna się od", więc pobieramy testy
        # projektu i filtrujemy po prefiksie po naszej stronie.
        jql = f'project = "{project_key}" AND issuetype = Test'

        while True:
            result = await self._request(
                "GET",
                f"{JIRA_API}/search",
                params={
                    "jql": jql,
                    "startAt": start_at,
                    "maxResults": _MAX_SEARCH_RESULTS,
                    # ``updated``/``description``/``priority`` są potrzebne
                    # synchronizacji (Story 8.11) — bez nich kierunek
                    # TMS → TestGEN nie miałby czego porównać ani wnieść.
                    "fields": "summary,labels,updated,description,priority",
                },
            )
            issues = result.get("issues") or []
            for issue in issues:
                for label in (issue.get("fields") or {}).get("labels") or []:
                    if label.startswith(XRAY_LABEL_PREFIX):
                        index[label.removeprefix(XRAY_LABEL_PREFIX)] = issue
            if len(issues) < _MAX_SEARCH_RESULTS:
                break
            start_at += _MAX_SEARCH_RESULTS
        return index

    async def xray_update_test(self, issue_key: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Aktualizuje zgłoszenie testu w Jirze (AC4)."""
        await self._request("PUT", f"{JIRA_API}/issue/{quote(issue_key)}", json={"fields": fields})
        return {"key": issue_key}

    async def xray_link_to_requirement(self, test_key: str, requirement_key: str) -> dict[str, Any]:
        """Wiąże test z wymaganiem/historyjką w Jirze (AC2)."""
        return await self._request(
            "POST", f"{XRAY_API}/link/{quote(test_key)}/{quote(requirement_key)}"
        )

    # ── Zephyr Scale ────────────────────────────────────────────────────────

    async def zephyr_create_testcase(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"{ZEPHYR_API}/testcase", json=payload)

    async def zephyr_update_testcase(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        await self._request("PUT", f"{ZEPHYR_API}/testcase/{quote(key)}", json=payload)
        return {"key": key}

    async def zephyr_find_all_testgen(self, project_key: str) -> dict[str, dict[str, Any]]:
        """Indeks przypadków Zephyra po polu własnym ``testgen_id`` (AC4)."""
        result = await self._request(
            "GET",
            f"{ZEPHYR_API}/testcase/search",
            params={"query": f'projectKey = "{project_key}"', "maxResults": 1000},
        )
        cases = result if isinstance(result, list) else (result.get("results") or [])
        index: dict[str, dict[str, Any]] = {}
        for case in cases:
            marker = (case.get("customFields") or {}).get(ZEPHYR_TESTGEN_FIELD)
            if marker:
                index[str(marker)] = case
        return index

    async def zephyr_get_folders(self, project_key: str) -> list[dict[str, Any]]:
        result = await self._request(
            "GET", f"{ZEPHYR_API}/folder", params={"projectKey": project_key, "type": "TEST_CASE"}
        )
        return result if isinstance(result, list) else (result.get("results") or [])

    async def zephyr_create_folder(self, project_key: str, name: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"{ZEPHYR_API}/folder",
            json={"projectKey": project_key, "name": name, "type": "TEST_CASE"},
        )

    async def zephyr_link_issue(self, testcase_key: str, issue_key: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"{ZEPHYR_API}/testcase/{quote(testcase_key)}/issuelinks",
            json={"issueKey": issue_key},
        )


def _error_message(response: httpx.Response) -> str:
    """Wyciąga komunikat Jiry; jego brak nie może zasłonić kodu HTTP."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    detail = ""
    if isinstance(body, dict):
        messages = body.get("errorMessages") or []
        if messages:
            detail = "; ".join(str(m) for m in messages)
        elif body.get("message"):
            detail = str(body["message"])
    return f"Jira zwróciła błąd (HTTP {response.status_code})" + (f": {detail}" if detail else "")
