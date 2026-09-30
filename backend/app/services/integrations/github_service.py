"""Klient GitHuba — OAuth, repozytoria, webhooki (Epic 8, Story 8.1).

Warstwa czysto transportowa: żadnego dostępu do bazy, żadnego kontekstu
tenanta. Dzięki temu da się ją testować bez DB, a Story 8.2 (GitLab)
dostanie bliźniaczy moduł o tym samym kształcie.

Podpisy webhooków porównujemy ``hmac.compare_digest`` — zwykłe ``==`` na
stringach kończy się na pierwszym różniącym bajcie i wycieka informację
czasem odpowiedzi.
"""

import hashlib
import hmac
import logging
import secrets
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import TestGENError, ValidationError
from app.services.integrations.status_check_builder import STATUS_CONTEXT

logger = logging.getLogger(__name__)

# Zdarzenia subskrybowane przy rejestracji webhooka (AC2). Filtrowanie akcji
# pull_requesta (opened/synchronize/reopened) robimy po stronie TestGEN —
# GitHub nie pozwala zawęzić subskrypcji do wybranych akcji.
WEBHOOK_EVENTS = ["push", "pull_request"]
OAUTH_SCOPES = "repo"
_TIMEOUT = 15.0


class GitHubError(TestGENError):
    """Błąd komunikacji z GitHubem — mapowany na 502 w warstwie API."""

    status_code = 502
    error_type = "github-error"
    title = "GitHub API Error"


def is_configured() -> bool:
    """Czy OAuth App jest skonfigurowana (client_id + secret w env)."""
    settings = get_settings()
    return bool(settings.github_client_id and settings.github_client_secret.get_secret_value())


def generate_webhook_secret() -> str:
    """Sekret HMAC dla pojedynczego webhooka — 256 bitów z CSPRNG."""
    return secrets.token_hex(32)


def get_authorization_url(state: str) -> str:
    """URL autoryzacji GitHuba; ``state`` chroni przed CSRF na callbacku (AC1)."""
    settings = get_settings()
    if not is_configured():
        raise ValidationError("Integracja z GitHub nie jest skonfigurowana na serwerze")
    params = httpx.QueryParams(
        {
            "client_id": settings.github_client_id,
            "redirect_uri": settings.github_redirect_uri,
            "scope": OAUTH_SCOPES,
            "state": state,
        }
    )
    return f"{settings.github_oauth_base_url}/login/oauth/authorize?{params}"


async def exchange_code_for_token(code: str) -> dict[str, Any]:
    """Wymienia ``code`` z callbacku na token dostępu (AC1).

    GitHub odpowiada HTTP 200 również na błąd — sygnalizuje go polem
    ``error`` w ciele, więc sam status nie wystarcza do walidacji.
    """
    settings = get_settings()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            f"{settings.github_oauth_base_url}/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret.get_secret_value(),
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
        )
    if response.status_code != 200:
        raise GitHubError(f"Wymiana kodu na token nie powiodła się (HTTP {response.status_code})")

    payload = response.json()
    if payload.get("error"):
        raise GitHubError(f"GitHub odrzucił kod autoryzacji: {payload.get('error_description') or payload['error']}")
    if not payload.get("access_token"):
        raise GitHubError("Odpowiedź GitHuba nie zawiera tokenu dostępu")
    return payload


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def _request(method: str, url: str, access_token: str, **kwargs: Any) -> httpx.Response:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            response = await client.request(method, url, headers=_headers(access_token), **kwargs)
        except httpx.HTTPError as exc:
            raise GitHubError(f"Brak połączenia z GitHub API: {exc}") from exc
    if response.status_code == 401:
        raise GitHubError("Token GitHuba wygasł lub został odwołany — połącz repozytorium ponownie")
    if response.status_code == 403:
        raise GitHubError("GitHub odmówił dostępu — sprawdź uprawnienia aplikacji do repozytorium")
    return response


async def get_user_repos(access_token: str, *, per_page: int = 100) -> list[dict[str, Any]]:
    """Repozytoria widoczne dla tokenu, posortowane wg ostatniej aktywności (AC1)."""
    settings = get_settings()
    response = await _request(
        "GET",
        f"{settings.github_api_url}/user/repos",
        access_token,
        params={"per_page": per_page, "sort": "updated", "affiliation": "owner,collaborator,organization_member"},
    )
    if response.status_code != 200:
        raise GitHubError(f"Nie udało się pobrać listy repozytoriów (HTTP {response.status_code})")
    return response.json()


async def register_webhook(
    access_token: str,
    repo_full_name: str,
    webhook_url: str,
    secret: str,
) -> dict[str, Any]:
    """Tworzy webhook na repozytorium (AC2).

    Wymaga uprawnień administratora repo — bez nich GitHub zwraca 404
    (celowo, żeby nie ujawniać istnienia prywatnych repozytoriów).
    """
    settings = get_settings()
    response = await _request(
        "POST",
        f"{settings.github_api_url}/repos/{repo_full_name}/hooks",
        access_token,
        json={
            "name": "web",
            "active": True,
            "events": WEBHOOK_EVENTS,
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        },
    )
    if response.status_code == 404:
        raise GitHubError(
            f"Brak uprawnień administratora do repozytorium {repo_full_name} — webhook nie został utworzony"
        )
    if response.status_code == 422:
        raise GitHubError(f"GitHub odrzucił konfigurację webhooka dla {repo_full_name} (być może już istnieje)")
    if response.status_code not in (200, 201):
        raise GitHubError(f"Nie udało się utworzyć webhooka (HTTP {response.status_code})")
    return response.json()


async def delete_webhook(access_token: str, repo_full_name: str, hook_id: str) -> None:
    """Usuwa webhook. Brak webhooka (404) traktujemy jak sukces — cel osiągnięty."""
    settings = get_settings()
    response = await _request(
        "DELETE",
        f"{settings.github_api_url}/repos/{repo_full_name}/hooks/{hook_id}",
        access_token,
    )
    if response.status_code not in (204, 404):
        raise GitHubError(f"Nie udało się usunąć webhooka (HTTP {response.status_code})")


async def get_pull_request_diff(access_token: str, repo_full_name: str, pr_number: int) -> str:
    """Unified diff pull requesta — wejście generatora regresji (Story 1.44, AC4).

    Pobranie diffa z API jest tańsze niż klonowanie obu gałęzi i liczenie go
    lokalnie; sam kod PR-a i tak klonujemy osobno, żeby zasilić analizę plików.
    """
    settings = get_settings()
    headers = _headers(access_token) | {"Accept": "application/vnd.github.v3.diff"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            response = await client.get(
                f"{settings.github_api_url}/repos/{repo_full_name}/pulls/{pr_number}",
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise GitHubError(f"Brak połączenia z GitHub API: {exc}") from exc
    if response.status_code != 200:
        raise GitHubError(f"Nie udało się pobrać diffa PR #{pr_number} (HTTP {response.status_code})")
    return response.text


def verify_webhook_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """Weryfikuje ``X-Hub-Signature-256`` (HMAC-SHA256 po surowym ciele), AC5.

    Porównanie ``compare_digest`` jest odporne na atak czasowy; brak nagłówka
    lub zły prefiks to od razu odrzucenie.
    """
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature[len("sha256=") :])


# ── Story 8.3: status checks i komentarze na PR ─────────────────────────────

# Neutralne stany z ``status_check_builder`` → słownik GitHuba.
_GITHUB_STATES = {"pending": "pending", "success": "success", "failure": "failure"}


async def send_commit_status(
    access_token: str,
    repo_full_name: str,
    commit_sha: str,
    state: str,
    description: str,
    target_url: str,
    context: str = STATUS_CONTEXT,
) -> dict[str, Any]:
    """Ustawia status commita widoczny na PR (AC1).

    Niepowodzenie zgłaszamy wyjątkiem, ale wywołujący traktuje je jako
    nieblokujące — analiza jest wykonana, a brak statusu to utrata
    informacji, nie utrata wyniku.
    """
    settings = get_settings()
    github_state = _GITHUB_STATES.get(state, "error")
    response = await _request(
        "POST",
        f"{settings.github_api_url}/repos/{repo_full_name}/statuses/{commit_sha}",
        access_token,
        json={
            "state": github_state,
            "target_url": target_url,
            "description": description,
            "context": context,
        },
    )
    if response.status_code not in (200, 201):
        raise GitHubError(
            f"Nie udało się ustawić statusu commita {commit_sha[:7]} (HTTP {response.status_code})"
        )
    return response.json()


async def create_pr_comment(
    access_token: str,
    repo_full_name: str,
    pr_number: int,
    body: str,
) -> dict[str, Any]:
    """Dodaje komentarz do PR (AC5).

    GitHub traktuje pull requesty jak issue, stąd endpoint ``/issues/``:
    ``/pulls/{n}/comments`` zakłada komentarz do konkretnej linii diffa,
    a my chcemy komentarz ogólny.
    """
    settings = get_settings()
    response = await _request(
        "POST",
        f"{settings.github_api_url}/repos/{repo_full_name}/issues/{pr_number}/comments",
        access_token,
        json={"body": body},
    )
    if response.status_code not in (200, 201):
        raise GitHubError(
            f"Nie udało się dodać komentarza do PR #{pr_number} (HTTP {response.status_code})"
        )
    return response.json()
