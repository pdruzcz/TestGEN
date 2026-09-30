"""Klient GitLaba — OAuth, projekty, webhooki (Epic 8, Story 8.2).

Kształt modułu jest bliźniaczy do ``github_service``, ale trzy rzeczy różnią
się na tyle, że nie dało się ich uwspólnić:

* **adres instancji** — GitLab bywa self-hosted, więc każda funkcja przyjmuje
  ``gitlab_url``; GitHub ma jeden adres w konfiguracji serwera,
* **identyfikator projektu** — GitLab adresuje projekty liczbą, GitHub nazwą
  ``owner/repo``,
* **uwierzytelnianie webhooka** — GitLab odsyła *ten sam* sekret w nagłówku
  ``X-Gitlab-Token``, zamiast podpisywać nim ciało (HMAC u GitHuba). Porównanie
  i tak robimy ``compare_digest``: sekret jest tajny, a zwykłe ``==`` wycieka
  jego prefiks przez czas odpowiedzi.
"""

import hmac
import logging
import secrets
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.exceptions import TestGENError, ValidationError
from app.services.integrations.status_check_builder import STATUS_CONTEXT

logger = logging.getLogger(__name__)

OAUTH_SCOPES = "api"
_TIMEOUT = 15.0
_PER_PAGE = 100


class GitLabError(TestGENError):
    """Błąd komunikacji z GitLabem — mapowany na 502 w warstwie API."""

    status_code = 502
    error_type = "gitlab-error"
    title = "GitLab API Error"


def is_configured() -> bool:
    """Czy aplikacja OAuth jest skonfigurowana (client_id + secret w env)."""
    settings = get_settings()
    return bool(settings.gitlab_client_id and settings.gitlab_client_secret.get_secret_value())


def default_gitlab_url() -> str:
    return get_settings().gitlab_default_url.rstrip("/")


def normalize_gitlab_url(gitlab_url: str | None) -> str:
    """Sprowadza adres instancji do postaci ``https://host`` bez końcowego ukośnika.

    Wymuszamy HTTPS — po tym kanale leci token OAuth i sekret webhooka.
    """
    candidate = (gitlab_url or "").strip() or default_gitlab_url()
    if not candidate.startswith("https://"):
        raise ValidationError("Adres instancji GitLab musi zaczynać się od https://")
    parsed = urlparse(candidate)
    if not parsed.hostname:
        raise ValidationError("Nieprawidłowy adres instancji GitLab")
    return f"https://{parsed.netloc}"


def host_of(gitlab_url: str) -> str:
    """Host instancji — potrzebny, by dopuścić self-hosted przy klonowaniu."""
    return urlparse(normalize_gitlab_url(gitlab_url)).hostname or ""


def generate_webhook_secret() -> str:
    """Token weryfikacyjny webhooka — 256 bitów z CSPRNG."""
    return secrets.token_hex(32)


def get_authorization_url(gitlab_url: str, state: str) -> str:
    """URL autoryzacji instancji GitLab; ``state`` chroni callback przed CSRF (AC1)."""
    settings = get_settings()
    if not is_configured():
        raise ValidationError("Integracja z GitLab nie jest skonfigurowana na serwerze")
    base = normalize_gitlab_url(gitlab_url)
    params = httpx.QueryParams(
        {
            "client_id": settings.gitlab_client_id,
            "redirect_uri": settings.gitlab_redirect_uri,
            "response_type": "code",
            "scope": OAUTH_SCOPES,
            "state": state,
        }
    )
    return f"{base}/oauth/authorize?{params}"


async def exchange_code_for_token(gitlab_url: str, code: str) -> dict[str, Any]:
    """Wymienia ``code`` z callbacku na token dostępu (AC1).

    W odróżnieniu od GitHuba, GitLab sygnalizuje odmowę statusem HTTP, więc
    tu status wystarcza — ale i tak sprawdzamy obecność tokenu w ciele.
    """
    settings = get_settings()
    base = normalize_gitlab_url(gitlab_url)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            response = await client.post(
                f"{base}/oauth/token",
                data={
                    "client_id": settings.gitlab_client_id,
                    "client_secret": settings.gitlab_client_secret.get_secret_value(),
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.gitlab_redirect_uri,
                },
            )
        except httpx.HTTPError as exc:
            raise GitLabError(f"Brak połączenia z instancją GitLab: {exc}") from exc

    if response.status_code != 200:
        detail = ""
        try:
            detail = response.json().get("error_description") or response.json().get("error") or ""
        except ValueError:
            detail = ""
        raise GitLabError(
            f"Wymiana kodu na token nie powiodła się (HTTP {response.status_code})"
            + (f": {detail}" if detail else "")
        )

    payload = response.json()
    if not payload.get("access_token"):
        raise GitLabError("Odpowiedź GitLaba nie zawiera tokenu dostępu")
    return payload


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


async def _request(
    method: str,
    gitlab_url: str,
    path: str,
    access_token: str,
    **kwargs: Any,
) -> httpx.Response:
    base = normalize_gitlab_url(gitlab_url)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            response = await client.request(
                method, f"{base}/api/v4{path}", headers=_headers(access_token), **kwargs
            )
        except httpx.HTTPError as exc:
            raise GitLabError(f"Brak połączenia z instancją GitLab: {exc}") from exc
    if response.status_code == 401:
        raise GitLabError("Token GitLaba wygasł lub został odwołany — połącz projekt ponownie")
    if response.status_code == 403:
        raise GitLabError("GitLab odmówił dostępu — sprawdź uprawnienia aplikacji do projektu")
    return response


async def get_user_projects(access_token: str, gitlab_url: str) -> list[dict[str, Any]]:
    """Projekty, w których użytkownik jest członkiem, wg ostatniej aktywności (AC1)."""
    response = await _request(
        "GET",
        gitlab_url,
        "/projects",
        access_token,
        params={
            "membership": "true",
            "per_page": _PER_PAGE,
            "order_by": "last_activity_at",
            "simple": "true",
        },
    )
    if response.status_code != 200:
        raise GitLabError(f"Nie udało się pobrać listy projektów (HTTP {response.status_code})")
    return response.json()


async def register_webhook(
    access_token: str,
    gitlab_url: str,
    project_id: int,
    webhook_url: str,
    secret: str,
) -> dict[str, Any]:
    """Tworzy webhook na projekcie: Push Events + Merge Request Events (AC2).

    Wymaga roli Maintainer/Owner — przy niższej GitLab zwraca 403, które
    ``_request`` tłumaczy na komunikat o uprawnieniach.
    """
    response = await _request(
        "POST",
        gitlab_url,
        f"/projects/{project_id}/hooks",
        access_token,
        json={
            "url": webhook_url,
            "token": secret,
            "push_events": True,
            "merge_requests_events": True,
            "enable_ssl_verification": True,
        },
    )
    if response.status_code == 404:
        raise GitLabError(
            f"Projekt {project_id} jest niedostępny lub brakuje uprawnień Maintainera — "
            "webhook nie został utworzony"
        )
    if response.status_code not in (200, 201):
        raise GitLabError(f"Nie udało się utworzyć webhooka (HTTP {response.status_code})")
    return response.json()


async def delete_webhook(
    access_token: str, gitlab_url: str, project_id: int, hook_id: int | str
) -> None:
    """Usuwa webhook. Brak webhooka (404) to sukces — cel osiągnięty."""
    response = await _request(
        "DELETE", gitlab_url, f"/projects/{project_id}/hooks/{hook_id}", access_token
    )
    if response.status_code not in (204, 404):
        raise GitLabError(f"Nie udało się usunąć webhooka (HTTP {response.status_code})")


async def get_merge_request_diff(
    access_token: str, gitlab_url: str, project_id: int, mr_iid: int
) -> str:
    """Unified diff merge requesta — wejście generatora regresji (Story 1.44, AC4).

    GitLab oddaje zmiany jako listę obiektów, nie gotowy tekst, więc sklejamy
    nagłówki ``diff --git`` sami — generator regresji parsuje format uniwersalny.
    """
    response = await _request(
        "GET",
        gitlab_url,
        f"/projects/{project_id}/merge_requests/{mr_iid}/changes",
        access_token,
    )
    if response.status_code != 200:
        raise GitLabError(f"Nie udało się pobrać zmian MR !{mr_iid} (HTTP {response.status_code})")

    parts: list[str] = []
    for change in response.json().get("changes") or []:
        diff = change.get("diff")
        if not diff:
            continue
        old_path = change.get("old_path") or change.get("new_path") or ""
        new_path = change.get("new_path") or old_path
        parts.append(f"diff --git a/{old_path} b/{new_path}")
        parts.append(f"--- a/{old_path}")
        parts.append(f"+++ b/{new_path}")
        parts.append(diff.rstrip("\n"))
    return "\n".join(parts)


def verify_webhook_token(token: str | None, secret: str) -> bool:
    """Porównuje ``X-Gitlab-Token`` z zapisanym sekretem (AC5).

    GitLab nie podpisuje ciała — odsyła sam sekret, więc jedyne, co możemy
    zrobić, to porównać go stałoczasowo.
    """
    if not token or not secret:
        return False
    return hmac.compare_digest(token, secret)


# ── Story 8.3: status checks i komentarze na MR ─────────────────────────────

# Neutralne stany z ``status_check_builder`` → słownik GitLaba: „w toku" to
# ``running``, a porażka ``failed`` (GitHub nazywa je pending/failure).
_GITLAB_STATES = {"pending": "running", "success": "success", "failure": "failed"}


async def send_commit_status(
    access_token: str,
    gitlab_url: str,
    project_id: int,
    commit_sha: str,
    state: str,
    description: str,
    target_url: str,
    name: str = STATUS_CONTEXT,
) -> dict[str, Any]:
    """Ustawia status commita widoczny na MR (AC2)."""
    gitlab_state = _GITLAB_STATES.get(state, "failed")
    response = await _request(
        "POST",
        gitlab_url,
        f"/projects/{project_id}/statuses/{commit_sha}",
        access_token,
        json={
            "state": gitlab_state,
            "name": name,
            "description": description,
            "target_url": target_url,
        },
    )
    # GitLab odrzuca powtórzone ustawienie tego samego stanu dla tej samej
    # nazwy (400) — to nie jest błąd z naszej perspektywy, stan już jest.
    if response.status_code == 400:
        logger.info("GitLab odrzucił powtórzony status %s dla %s", gitlab_state, commit_sha[:7])
        return {}
    if response.status_code not in (200, 201):
        raise GitLabError(
            f"Nie udało się ustawić statusu commita {commit_sha[:7]} (HTTP {response.status_code})"
        )
    return response.json()


async def create_mr_note(
    access_token: str,
    gitlab_url: str,
    project_id: int,
    mr_iid: int,
    body: str,
) -> dict[str, Any]:
    """Dodaje komentarz (note) do merge requesta (AC5)."""
    response = await _request(
        "POST",
        gitlab_url,
        f"/projects/{project_id}/merge_requests/{mr_iid}/notes",
        access_token,
        json={"body": body},
    )
    if response.status_code not in (200, 201):
        raise GitLabError(
            f"Nie udało się dodać komentarza do MR !{mr_iid} (HTTP {response.status_code})"
        )
    return response.json()
