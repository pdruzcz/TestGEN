"""Klient TestRail API v2 — Epic 8, Story 8.8.

Warstwa transportowa: uwierzytelnianie, ścieżki, obsługa błędów. Decyzje
o tym, co utworzyć a co zaktualizować, podejmuje ``tms_exporter``.

Dwie właściwości TestRaila wymuszają kształt tego modułu:

* **limit tempa** — instancje TestRaila dławią klienta przy zbyt gęstych
  żądaniach, a eksport setek przypadków to setki wywołań. Klient odczekuje
  między żądaniami, zamiast liczyć na to, że serwer wytrzyma;
* **paginacja** — ``get_cases`` zwraca 250 pozycji na stronę i od wersji 6.7
  opakowuje wynik w obiekt z ``offset``/``_links``. Obsługujemy oba kształty,
  bo klienci bywają na starszych instancjach.
"""

import asyncio
import base64
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.exceptions import TestGENError, ValidationError

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
# Odstęp między żądaniami — TestRail Cloud dławi przy ~1 żądaniu na sekundę.
MIN_REQUEST_INTERVAL_SECONDS = 1.0
_MAX_PAGE_SIZE = 250
# Zabezpieczenie przed nieskończoną paginacją, gdyby instancja zwracała
# wciąż tę samą stronę.
_MAX_PAGES = 40


class TestRailError(TestGENError):
    """Błąd komunikacji z TestRailem — mapowany na 502 w warstwie API."""

    status_code = 502
    error_type = "testrail-error"
    title = "TestRail API Error"


def normalize_url(url: str) -> str:
    """Sprowadza adres instancji do ``https://host`` bez ścieżki.

    Wymuszamy HTTPS — tym kanałem leci klucz API w nagłówku Basic Auth.
    """
    candidate = (url or "").strip().rstrip("/")
    if not candidate:
        raise ValidationError("Adres instancji TestRail jest wymagany")
    if not candidate.startswith("https://"):
        raise ValidationError("Adres instancji TestRail musi zaczynać się od https://")
    parsed = urlparse(candidate)
    if not parsed.netloc:
        raise ValidationError("Nieprawidłowy adres instancji TestRail")
    return f"https://{parsed.netloc}"


class TestRailClient:
    """Cienki klient API v2. Jedna instancja na jeden eksport."""

    def __init__(self, base_url: str, email: str, api_key: str) -> None:
        self.base_url = normalize_url(base_url)
        self._email = email
        self._api_key = api_key
        self._last_request_at = 0.0

    @property
    def _headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self._email}:{self._api_key}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            await asyncio.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request_at = time.monotonic()

    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        await self._throttle()
        url = f"{self.base_url}/index.php?/api/v2/{endpoint}"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                response = await client.request(method, url, headers=self._headers, **kwargs)
            except httpx.HTTPError as exc:
                raise TestRailError(f"Brak połączenia z TestRail: {exc}") from exc

        if response.status_code == 401:
            raise TestRailError("TestRail odrzucił poświadczenia — sprawdź e-mail i klucz API")
        if response.status_code == 403:
            raise TestRailError("Brak uprawnień w TestRail do tej operacji")
        if response.status_code == 429:
            # Mimo dławienia po naszej stronie — instancja może mieć ostrzejszy limit.
            raise TestRailError("TestRail ograniczył tempo żądań — spróbuj ponownie za chwilę")
        if response.status_code >= 400:
            raise TestRailError(_error_message(response))

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    async def test_connection(self, project_id: int) -> dict[str, Any]:
        """Sprawdza poświadczenia i dostęp do projektu docelowego (AC1)."""
        project = await self._request("GET", f"get_project/{project_id}")
        return {
            "connected": True,
            "project_id": project_id,
            "project_name": project.get("name") or "",
            "is_completed": bool(project.get("is_completed")),
        }

    async def get_sections(self, project_id: int, suite_id: int | None = None) -> list[dict[str, Any]]:
        endpoint = f"get_sections/{project_id}"
        if suite_id:
            endpoint += f"&suite_id={suite_id}"
        return _as_list(await self._request("GET", endpoint), "sections")

    async def create_section(
        self,
        project_id: int,
        name: str,
        *,
        suite_id: int | None = None,
        parent_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name}
        if suite_id:
            payload["suite_id"] = suite_id
        if parent_id:
            payload["parent_id"] = parent_id
        return await self._request("POST", f"add_section/{project_id}", json=payload)

    async def get_cases(
        self,
        project_id: int,
        *,
        suite_id: int | None = None,
        section_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Wszystkie przypadki projektu, z przejściem po stronach."""
        cases: list[dict[str, Any]] = []
        offset = 0
        for _ in range(_MAX_PAGES):
            endpoint = f"get_cases/{project_id}&limit={_MAX_PAGE_SIZE}&offset={offset}"
            if suite_id:
                endpoint += f"&suite_id={suite_id}"
            if section_id:
                endpoint += f"&section_id={section_id}"

            page = _as_list(await self._request("GET", endpoint), "cases")
            cases.extend(page)
            if len(page) < _MAX_PAGE_SIZE:
                break
            offset += _MAX_PAGE_SIZE
        return cases

    async def add_case(self, section_id: int, data: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"add_case/{section_id}", json=data)

    async def update_case(self, case_id: int, data: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"update_case/{case_id}", json=data)

    async def get_priorities(self) -> list[dict[str, Any]]:
        return _as_list(await self._request("GET", "get_priorities"), "priorities")

    async def get_case_types(self) -> list[dict[str, Any]]:
        return _as_list(await self._request("GET", "get_case_types"), "case_types")


def _as_list(payload: Any, key: str) -> list[dict[str, Any]]:
    """Normalizuje odpowiedź: lista (TestRail < 6.7) albo obiekt z kluczem."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _error_message(response: httpx.Response) -> str:
    """Wyciąga komunikat TestRaila; jego brak nie może zasłonić kodu HTTP."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    detail = body.get("error") if isinstance(body, dict) else None
    return f"TestRail zwrócił błąd (HTTP {response.status_code})" + (f": {detail}" if detail else "")
