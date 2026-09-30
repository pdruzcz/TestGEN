"""Testy klienta GitHuba — Story 8.1 (AC1, AC2, AC5; Task 7.1).

httpx mockowany transportem (``MockTransport``) zamiast patchowania metod —
sprawdzamy również to, co faktycznie leci na sieć: URL, nagłówki i ciało.
"""

import hashlib
import hmac
import json

import httpx
import pytest

from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.services.integrations import github_service
from app.services.integrations.github_service import (
    GitHubError,
    delete_webhook,
    exchange_code_for_token,
    generate_webhook_secret,
    get_authorization_url,
    get_pull_request_diff,
    get_user_repos,
    is_configured,
    register_webhook,
    verify_webhook_signature,
)

TOKEN = "gho_testtoken"


@pytest.fixture
def configured(monkeypatch):
    """Ustawia poświadczenia OAuth App w cache'owanych Settings."""
    settings = get_settings()
    monkeypatch.setattr(settings, "github_client_id", "cid123", raising=False)

    class _Secret:
        @staticmethod
        def get_secret_value() -> str:
            return "csecret456"

    monkeypatch.setattr(settings, "github_client_secret", _Secret(), raising=False)
    monkeypatch.setattr(settings, "github_redirect_uri", "https://app.testgen.io/cb", raising=False)
    return settings


def _patch_transport(monkeypatch, handler) -> list[httpx.Request]:
    """Podstawia MockTransport pod AsyncClient; zwraca listę przechwyconych żądań."""
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


# --- konfiguracja i URL autoryzacji (AC1) ---


def test_is_configured_wymaga_obu_poswiadczen(configured):
    assert is_configured()


def test_authorization_url_zawiera_client_id_scope_i_state(configured):
    url = get_authorization_url("st4te")

    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=cid123" in url
    assert "scope=repo" in url
    assert "state=st4te" in url
    assert "redirect_uri=https%3A%2F%2Fapp.testgen.io%2Fcb" in url


def test_authorization_url_bez_konfiguracji_to_blad_walidacji(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "github_client_id", "", raising=False)

    with pytest.raises(ValidationError):
        get_authorization_url("st4te")


def test_generate_webhook_secret_jest_losowy_i_ma_256_bitow():
    first, second = generate_webhook_secret(), generate_webhook_secret()
    assert first != second
    assert len(first) == 64
    int(first, 16)


# --- wymiana kodu na token (AC1) ---


@pytest.mark.asyncio
async def test_exchange_code_zwraca_token(configured, monkeypatch):
    seen = _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(200, json={"access_token": "gho_abc", "scope": "repo"}),
    )

    payload = await exchange_code_for_token("kod123")

    assert payload["access_token"] == "gho_abc"
    assert seen[0].url.path == "/login/oauth/access_token"
    body = seen[0].content.decode()
    assert "code=kod123" in body
    assert "client_secret=csecret456" in body


@pytest.mark.asyncio
async def test_exchange_code_blad_w_ciele_mimo_http_200(configured, monkeypatch):
    """GitHub sygnalizuje odmowę polem ``error``, nie statusem HTTP."""
    _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(
            200, json={"error": "bad_verification_code", "error_description": "Kod wygasł"}
        ),
    )

    with pytest.raises(GitHubError, match="Kod wygasł"):
        await exchange_code_for_token("stary-kod")


@pytest.mark.asyncio
async def test_exchange_code_bez_tokenu_w_odpowiedzi(configured, monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"scope": "repo"}))

    with pytest.raises(GitHubError, match="nie zawiera tokenu"):
        await exchange_code_for_token("kod")


@pytest.mark.asyncio
async def test_exchange_code_http_500(configured, monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(500, text="oops"))

    with pytest.raises(GitHubError, match="HTTP 500"):
        await exchange_code_for_token("kod")


# --- repozytoria ---


@pytest.mark.asyncio
async def test_get_user_repos_wysyla_bearer_i_wersje_api(monkeypatch):
    seen = _patch_transport(
        monkeypatch, lambda r: httpx.Response(200, json=[{"full_name": "acme/app"}])
    )

    repos = await get_user_repos(TOKEN)

    assert repos == [{"full_name": "acme/app"}]
    assert seen[0].headers["Authorization"] == f"Bearer {TOKEN}"
    assert seen[0].headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert seen[0].url.params["sort"] == "updated"


@pytest.mark.asyncio
async def test_wygasly_token_daje_czytelny_komunikat(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(401, json={"message": "Bad credentials"}))

    with pytest.raises(GitHubError, match="wygasł"):
        await get_user_repos(TOKEN)


@pytest.mark.asyncio
async def test_brak_polaczenia_z_github(monkeypatch):
    def _boom(request):
        raise httpx.ConnectError("sieć padła")

    _patch_transport(monkeypatch, _boom)

    with pytest.raises(GitHubError, match="Brak połączenia"):
        await get_user_repos(TOKEN)


# --- rejestracja webhooka (AC2) ---


@pytest.mark.asyncio
async def test_register_webhook_subskrybuje_push_i_pull_request(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={"id": 42}))

    hook = await register_webhook(TOKEN, "acme/app", "https://api.testgen.io/hook", "s3cret")

    assert hook["id"] == 42
    assert seen[0].url.path == "/repos/acme/app/hooks"
    body = json.loads(seen[0].content)
    assert body["events"] == ["push", "pull_request"]
    assert body["config"]["url"] == "https://api.testgen.io/hook"
    assert body["config"]["secret"] == "s3cret"
    assert body["config"]["insecure_ssl"] == "0"
    assert body["active"] is True


@pytest.mark.asyncio
async def test_register_webhook_404_to_brak_uprawnien_admina(monkeypatch):
    """GitHub zwraca 404 zamiast 403, żeby nie ujawniać prywatnych repo."""
    _patch_transport(monkeypatch, lambda r: httpx.Response(404, json={"message": "Not Found"}))

    with pytest.raises(GitHubError, match="uprawnień administratora"):
        await register_webhook(TOKEN, "acme/app", "https://api.testgen.io/hook", "s3cret")


@pytest.mark.asyncio
async def test_register_webhook_422_gdy_juz_istnieje(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(422, json={"message": "Validation Failed"}))

    with pytest.raises(GitHubError, match="odrzucił konfigurację"):
        await register_webhook(TOKEN, "acme/app", "https://api.testgen.io/hook", "s3cret")


@pytest.mark.asyncio
async def test_delete_webhook_204(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(204))

    await delete_webhook(TOKEN, "acme/app", "42")

    assert seen[0].method == "DELETE"
    assert seen[0].url.path == "/repos/acme/app/hooks/42"


@pytest.mark.asyncio
async def test_delete_webhook_404_traktujemy_jak_sukces(monkeypatch):
    """Cel to brak webhooka — jeśli już go nie ma, nie ma czego naprawiać."""
    _patch_transport(monkeypatch, lambda r: httpx.Response(404))

    await delete_webhook(TOKEN, "acme/app", "42")


@pytest.mark.asyncio
async def test_delete_webhook_500_to_blad(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(500))

    with pytest.raises(GitHubError):
        await delete_webhook(TOKEN, "acme/app", "42")


# --- diff pull requesta (AC4) ---


@pytest.mark.asyncio
async def test_get_pull_request_diff_prosi_o_format_diff(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, text="diff --git a/x b/x"))

    diff = await get_pull_request_diff(TOKEN, "acme/app", 7)

    assert diff.startswith("diff --git")
    assert seen[0].headers["Accept"] == "application/vnd.github.v3.diff"
    assert seen[0].url.path == "/repos/acme/app/pulls/7"


# --- weryfikacja podpisu (AC5) ---


def _sign(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_podpis_poprawny():
    payload = b'{"zen":"Design for failure."}'
    assert verify_webhook_signature(payload, _sign(payload, "s3cret"), "s3cret")


def test_podpis_z_innym_sekretem_odrzucony():
    payload = b'{"a":1}'
    assert not verify_webhook_signature(payload, _sign(payload, "inny"), "s3cret")


def test_podpis_dla_zmodyfikowanego_ciala_odrzucony():
    signature = _sign(b'{"a":1}', "s3cret")
    assert not verify_webhook_signature(b'{"a":2}', signature, "s3cret")


@pytest.mark.parametrize("signature", [None, "", "abc", "sha1=deadbeef", "sha256="])
def test_brakujacy_lub_zly_format_podpisu_odrzucony(signature):
    assert not verify_webhook_signature(b'{"a":1}', signature, "s3cret")


def test_uzywamy_compare_digest(monkeypatch):
    """Porównanie musi być stałoczasowe — zwykłe == wycieka bajty przez czas."""
    called = {}
    original = hmac.compare_digest

    def _spy(a, b):
        called["hit"] = True
        return original(a, b)

    monkeypatch.setattr(github_service.hmac, "compare_digest", _spy)
    payload = b'{"a":1}'
    verify_webhook_signature(payload, _sign(payload, "s3cret"), "s3cret")

    assert called.get("hit")


# ── Story 8.3: status checki i komentarze ───────────────────────────────────

from app.services.integrations.github_service import (  # noqa: E402
    create_pr_comment,
    send_commit_status,
)

SHA = "a" * 40
TARGET = "https://app.testgen.io/projects/p1/results"


@pytest.mark.asyncio
async def test_send_commit_status_uzywa_stalej_nazwy_kontekstu(monkeypatch):
    """Nazwa trafia do branch protection — musi być identyczna za każdym razem."""
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={"id": 1}))

    await send_commit_status(TOKEN, "acme/app", SHA, "failure", "Znaleziono 2 krytyczne", TARGET)

    assert seen[0].url.path == f"/repos/acme/app/statuses/{SHA}"
    body = json.loads(seen[0].content)
    assert body["context"] == "TestGEN / Code Analysis"
    assert body["state"] == "failure"
    assert body["description"] == "Znaleziono 2 krytyczne"
    assert body["target_url"] == TARGET


@pytest.mark.parametrize(
    ("neutral", "github_state"),
    [("pending", "pending"), ("success", "success"), ("failure", "failure")],
)
@pytest.mark.asyncio
async def test_stany_neutralne_mapowane_na_slownik_githuba(monkeypatch, neutral, github_state):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={}))

    await send_commit_status(TOKEN, "acme/app", SHA, neutral, "opis", TARGET)

    assert json.loads(seen[0].content)["state"] == github_state


@pytest.mark.asyncio
async def test_nieznany_stan_ladnie_na_error(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={}))

    await send_commit_status(TOKEN, "acme/app", SHA, "cokolwiek", "opis", TARGET)

    assert json.loads(seen[0].content)["state"] == "error"


@pytest.mark.asyncio
async def test_blad_ustawienia_statusu_jest_zglaszany(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(500))

    with pytest.raises(GitHubError, match="statusu commita"):
        await send_commit_status(TOKEN, "acme/app", SHA, "success", "ok", TARGET)


@pytest.mark.asyncio
async def test_komentarz_idzie_na_endpoint_issues(monkeypatch):
    """PR to dla GitHuba issue; /pulls/{n}/comments dotyczy linii diffa."""
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={"id": 5}))

    await create_pr_comment(TOKEN, "acme/app", 7, "## Analiza TestGEN")

    assert seen[0].url.path == "/repos/acme/app/issues/7/comments"
    assert json.loads(seen[0].content)["body"] == "## Analiza TestGEN"


@pytest.mark.asyncio
async def test_blad_komentarza_jest_zglaszany(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(422))

    with pytest.raises(GitHubError, match="komentarza do PR #7"):
        await create_pr_comment(TOKEN, "acme/app", 7, "treść")
