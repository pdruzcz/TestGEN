"""Testy klienta GitLaba — Story 8.2 (AC1, AC2, AC5; Task 5.1).

httpx mockowany transportem, jak w ``test_github_service`` — sprawdzamy też
to, co faktycznie leci na sieć. Osobna uwaga idzie na self-hosted: adres
instancji jest parametrem każdego wywołania, więc testy pilnują, że trafia
do URL-a, a nie gubi się na rzecz gitlab.com.
"""

import json

import httpx
import pytest

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.services.integrations.gitlab_service import (
    GitLabError,
    delete_webhook,
    exchange_code_for_token,
    generate_webhook_secret,
    get_authorization_url,
    get_merge_request_diff,
    get_user_projects,
    host_of,
    is_configured,
    normalize_gitlab_url,
    register_webhook,
    verify_webhook_token,
)

TOKEN = "glpat-testtoken"
SELF_HOSTED = "https://git.firma.pl"


@pytest.fixture
def configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gitlab_client_id", "gl-cid", raising=False)

    class _Secret:
        @staticmethod
        def get_secret_value() -> str:
            return "gl-secret"

    monkeypatch.setattr(settings, "gitlab_client_secret", _Secret(), raising=False)
    monkeypatch.setattr(settings, "gitlab_redirect_uri", "https://app.testgen.io/gl", raising=False)
    return settings


def _patch_transport(monkeypatch, handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []
    original = httpx.AsyncClient

    def _factory(*args, **kwargs):
        def _handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        kwargs["transport"] = httpx.MockTransport(_handle)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)
    return seen


# --- adres instancji (AC1, self-hosted) ---


def test_normalize_przyjmuje_gitlab_com_i_self_hosted():
    assert normalize_gitlab_url("https://gitlab.com") == "https://gitlab.com"
    assert normalize_gitlab_url(SELF_HOSTED) == SELF_HOSTED


def test_normalize_obcina_koncowy_ukosnik_i_sciezke():
    assert normalize_gitlab_url("https://git.firma.pl/") == SELF_HOSTED


def test_normalize_pusty_adres_daje_domyslny():
    assert normalize_gitlab_url(None) == "https://gitlab.com"
    assert normalize_gitlab_url("   ") == "https://gitlab.com"


@pytest.mark.parametrize("bad", ["http://git.firma.pl", "git.firma.pl", "ftp://x"])
def test_normalize_wymaga_https(bad):
    """Po tym kanale leci token OAuth i sekret webhooka — HTTP odpada."""
    with pytest.raises(ValidationError):
        normalize_gitlab_url(bad)


def test_host_of_wyciaga_domene_instancji():
    assert host_of(SELF_HOSTED) == "git.firma.pl"
    assert host_of("https://gitlab.com") == "gitlab.com"


# --- URL autoryzacji (AC1) ---


def test_authorization_url_wskazuje_na_instancje(configured):
    url = get_authorization_url(SELF_HOSTED, "st4te")

    assert url.startswith(f"{SELF_HOSTED}/oauth/authorize?")
    assert "client_id=gl-cid" in url
    assert "scope=api" in url
    assert "response_type=code" in url
    assert "state=st4te" in url


def test_authorization_url_dla_gitlab_com(configured):
    assert get_authorization_url("https://gitlab.com", "s").startswith(
        "https://gitlab.com/oauth/authorize?"
    )


def test_authorization_url_bez_konfiguracji_to_blad(monkeypatch):
    monkeypatch.setattr(get_settings(), "gitlab_client_id", "", raising=False)
    with pytest.raises(ValidationError):
        get_authorization_url(SELF_HOSTED, "s")


def test_is_configured_wymaga_obu_poswiadczen(configured):
    assert is_configured()


def test_generate_webhook_secret_ma_256_bitow():
    secret = generate_webhook_secret()
    assert len(secret) == 64
    assert secret != generate_webhook_secret()
    int(secret, 16)


# --- wymiana kodu (AC1) ---


@pytest.mark.asyncio
async def test_exchange_code_uderza_w_instancje(configured, monkeypatch):
    seen = _patch_transport(
        monkeypatch, lambda r: httpx.Response(200, json={"access_token": "glpat-abc"})
    )

    payload = await exchange_code_for_token(SELF_HOSTED, "kod123")

    assert payload["access_token"] == "glpat-abc"
    assert str(seen[0].url) == f"{SELF_HOSTED}/oauth/token"
    body = seen[0].content.decode()
    assert "grant_type=authorization_code" in body
    assert "code=kod123" in body


@pytest.mark.asyncio
async def test_exchange_code_blad_statusu_z_opisem(configured, monkeypatch):
    """GitLab — w odróżnieniu od GitHuba — sygnalizuje odmowę statusem HTTP."""
    _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(
            401, json={"error": "invalid_grant", "error_description": "Kod wygasł"}
        ),
    )

    with pytest.raises(GitLabError, match="Kod wygasł"):
        await exchange_code_for_token(SELF_HOSTED, "stary")


@pytest.mark.asyncio
async def test_exchange_code_bez_tokenu(configured, monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"token_type": "bearer"}))

    with pytest.raises(GitLabError, match="nie zawiera tokenu"):
        await exchange_code_for_token(SELF_HOSTED, "kod")


# --- projekty ---


@pytest.mark.asyncio
async def test_get_user_projects_filtruje_po_czlonkostwie(monkeypatch):
    seen = _patch_transport(
        monkeypatch, lambda r: httpx.Response(200, json=[{"id": 7, "path_with_namespace": "grupa/app"}])
    )

    projects = await get_user_projects(TOKEN, SELF_HOSTED)

    assert projects[0]["id"] == 7
    assert seen[0].url.path == "/api/v4/projects"
    assert seen[0].url.params["membership"] == "true"
    assert seen[0].headers["Authorization"] == f"Bearer {TOKEN}"


@pytest.mark.asyncio
async def test_wygasly_token_daje_czytelny_komunikat(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(401, json={"message": "401 Unauthorized"}))

    with pytest.raises(GitLabError, match="wygasł"):
        await get_user_projects(TOKEN, SELF_HOSTED)


@pytest.mark.asyncio
async def test_brak_polaczenia_z_instancja(monkeypatch):
    def _boom(request):
        raise httpx.ConnectError("DNS")

    _patch_transport(monkeypatch, _boom)

    with pytest.raises(GitLabError, match="Brak połączenia"):
        await get_user_projects(TOKEN, SELF_HOSTED)


# --- webhooki (AC2) ---


@pytest.mark.asyncio
async def test_register_webhook_wlacza_push_i_merge_request(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={"id": 99}))

    hook = await register_webhook(TOKEN, SELF_HOSTED, 7, "https://api.testgen.io/hook", "s3cret")

    assert hook["id"] == 99
    assert seen[0].url.path == "/api/v4/projects/7/hooks"
    body = json.loads(seen[0].content)
    assert body["push_events"] is True
    assert body["merge_requests_events"] is True
    assert body["token"] == "s3cret"
    assert body["enable_ssl_verification"] is True


@pytest.mark.asyncio
async def test_register_webhook_403_to_brak_uprawnien(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(403, json={"message": "403 Forbidden"}))

    with pytest.raises(GitLabError, match="uprawnienia"):
        await register_webhook(TOKEN, SELF_HOSTED, 7, "https://api.testgen.io/hook", "s")


@pytest.mark.asyncio
async def test_register_webhook_404_wskazuje_na_maintainera(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(404, json={"message": "404"}))

    with pytest.raises(GitLabError, match="Maintainera"):
        await register_webhook(TOKEN, SELF_HOSTED, 7, "https://api.testgen.io/hook", "s")


@pytest.mark.asyncio
async def test_delete_webhook_204(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(204))

    await delete_webhook(TOKEN, SELF_HOSTED, 7, 99)

    assert seen[0].method == "DELETE"
    assert seen[0].url.path == "/api/v4/projects/7/hooks/99"


@pytest.mark.asyncio
async def test_delete_webhook_404_traktujemy_jak_sukces(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(404))
    await delete_webhook(TOKEN, SELF_HOSTED, 7, 99)


# --- diff merge requesta (AC4) ---


@pytest.mark.asyncio
async def test_merge_request_diff_sklejany_w_format_uniwersalny(monkeypatch):
    """GitLab oddaje listę zmian, nie gotowy diff — nagłówki dokładamy sami."""
    changes = {
        "changes": [
            {
                "old_path": "src/a.py",
                "new_path": "src/a.py",
                "diff": "@@ -1,3 +1,4 @@\n+import os\n",
            },
            {"old_path": "src/b.py", "new_path": "src/b.py", "diff": "@@ -5 +5 @@\n-x\n+y\n"},
        ]
    }
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json=changes))

    diff = await get_merge_request_diff(TOKEN, SELF_HOSTED, 7, 42)

    assert seen[0].url.path == "/api/v4/projects/7/merge_requests/42/changes"
    assert "diff --git a/src/a.py b/src/a.py" in diff
    assert "--- a/src/b.py" in diff
    assert "+++ b/src/b.py" in diff
    assert "+import os" in diff


@pytest.mark.asyncio
async def test_merge_request_diff_pomija_zmiany_bez_diffa(monkeypatch):
    """Zmiana binarna lub samo przeniesienie pliku nie niosą treści diffa."""
    _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(200, json={"changes": [{"old_path": "a.png", "new_path": "a.png"}]}),
    )

    assert await get_merge_request_diff(TOKEN, SELF_HOSTED, 7, 42) == ""


@pytest.mark.asyncio
async def test_merge_request_diff_blad_http(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(404))

    with pytest.raises(GitLabError, match="!42"):
        await get_merge_request_diff(TOKEN, SELF_HOSTED, 7, 42)


# --- weryfikacja tokenu webhooka (AC5) ---


def test_token_zgodny_przechodzi():
    assert verify_webhook_token("s3cret", "s3cret")


def test_token_niezgodny_odrzucony():
    assert not verify_webhook_token("inny", "s3cret")


@pytest.mark.parametrize("token", [None, ""])
def test_brak_tokenu_odrzucony(token):
    assert not verify_webhook_token(token, "s3cret")


def test_pusty_sekret_nigdy_nie_przechodzi():
    """Integracja bez zapisanego sekretu nie może akceptować dowolnych dostaw."""
    assert not verify_webhook_token("cokolwiek", "")


def test_prefiks_tokenu_nie_wystarcza():
    assert not verify_webhook_token("s3c", "s3cret")
    assert not verify_webhook_token("s3cretXX", "s3cret")


# ── Story 8.3: status checki i komentarze ───────────────────────────────────

from app.services.integrations.gitlab_service import (  # noqa: E402
    create_mr_note,
    send_commit_status,
)

SHA = "d" * 40
TARGET = "https://app.testgen.io/projects/p1/results"


@pytest.mark.asyncio
async def test_send_commit_status_uderza_w_instancje_z_nazwa_kontekstu(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={"id": 1}))

    await send_commit_status(
        TOKEN, SELF_HOSTED, 7, SHA, "failure", "Znaleziono 2 krytyczne", TARGET
    )

    assert seen[0].url.path == f"/api/v4/projects/7/statuses/{SHA}"
    body = json.loads(seen[0].content)
    assert body["name"] == "TestGEN / Code Analysis"
    assert body["description"] == "Znaleziono 2 krytyczne"
    assert body["target_url"] == TARGET


@pytest.mark.parametrize(
    ("neutral", "gitlab_state"),
    [("pending", "running"), ("success", "success"), ("failure", "failed")],
)
@pytest.mark.asyncio
async def test_stany_neutralne_mapowane_na_slownik_gitlaba(monkeypatch, neutral, gitlab_state):
    """GitLab nazywa je inaczej niż GitHub: running/failed zamiast pending/failure."""
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={}))

    await send_commit_status(TOKEN, SELF_HOSTED, 7, SHA, neutral, "opis", TARGET)

    assert json.loads(seen[0].content)["state"] == gitlab_state


@pytest.mark.asyncio
async def test_powtorzony_ten_sam_status_nie_jest_bledem(monkeypatch):
    """GitLab odrzuca powtórzenie stanu (400) — stan już jest, cel osiągnięty."""
    _patch_transport(monkeypatch, lambda r: httpx.Response(400, json={"message": "Cannot transition"}))

    assert await send_commit_status(TOKEN, SELF_HOSTED, 7, SHA, "success", "ok", TARGET) == {}


@pytest.mark.asyncio
async def test_blad_ustawienia_statusu_jest_zglaszany(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(500))

    with pytest.raises(GitLabError, match="statusu commita"):
        await send_commit_status(TOKEN, SELF_HOSTED, 7, SHA, "success", "ok", TARGET)


@pytest.mark.asyncio
async def test_komentarz_idzie_na_notes_merge_requesta(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={"id": 5}))

    await create_mr_note(TOKEN, SELF_HOSTED, 7, 42, "## Analiza TestGEN")

    assert seen[0].url.path == "/api/v4/projects/7/merge_requests/42/notes"
    assert json.loads(seen[0].content)["body"] == "## Analiza TestGEN"


@pytest.mark.asyncio
async def test_blad_komentarza_jest_zglaszany(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(403))

    with pytest.raises(GitLabError):
        await create_mr_note(TOKEN, SELF_HOSTED, 7, 42, "treść")
