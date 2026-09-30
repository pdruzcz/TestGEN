"""Testy klienta TestRail API v2 — Story 8.8 (AC1, AC2; Task 5.1).

httpx mockowany transportem (wzorzec test_github_service). Osobna uwaga idzie
na dwie pułapki TestRaila: dławienie tempa i dwa kształty odpowiedzi
(lista w starszych instancjach, obiekt z paginacją od 6.7).
"""

import base64

import httpx
import pytest

from app.core.exceptions import ValidationError
from app.services.export.testrail_service import (
    MIN_REQUEST_INTERVAL_SECONDS,
    TestRailClient,
    TestRailError,
    normalize_url,
)

URL = "https://firma.testrail.io"
EMAIL = "qa@firma.pl"
API_KEY = "klucz-api"


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


# Oryginalna metoda zapamiętana przed podmianą — test dławienia woła ją wprost.
_REAL_THROTTLE = TestRailClient._throttle


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    """Dławienie testujemy osobno — reszta testów nie ma na nie czekać."""

    async def _instant(self) -> None:
        return None

    monkeypatch.setattr(TestRailClient, "_throttle", _instant)


def _client() -> TestRailClient:
    return TestRailClient(URL, EMAIL, API_KEY)


# ── adres instancji ──────────────────────────────────────────────────────────


def test_normalize_obcina_sciezke_i_ukosnik():
    assert normalize_url("https://firma.testrail.io/index.php?/x") == URL
    assert normalize_url("https://firma.testrail.io/") == URL


@pytest.mark.parametrize("bad", ["http://firma.testrail.io", "firma.testrail.io", ""])
def test_normalize_wymaga_https(bad):
    """Tym kanałem leci klucz API w nagłówku Basic Auth."""
    with pytest.raises(ValidationError):
        normalize_url(bad)


# ── uwierzytelnianie ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_uzywa_basic_auth_z_email_i_kluczem(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"name": "Projekt"}))

    await _client().test_connection(12)

    header = seen[0].headers["Authorization"]
    assert header.startswith("Basic ")
    decoded = base64.b64decode(header.removeprefix("Basic ")).decode()
    assert decoded == f"{EMAIL}:{API_KEY}"


@pytest.mark.asyncio
async def test_sciezka_api_v2_przez_index_php(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"name": "P"}))

    await _client().test_connection(12)

    assert str(seen[0].url) == f"{URL}/index.php?/api/v2/get_project/12"


@pytest.mark.asyncio
async def test_test_connection_zwraca_nazwe_projektu(monkeypatch):
    _patch_transport(
        monkeypatch, lambda r: httpx.Response(200, json={"name": "Mój projekt", "is_completed": False})
    )

    result = await _client().test_connection(12)

    assert result["connected"] is True
    assert result["project_name"] == "Mój projekt"


@pytest.mark.asyncio
async def test_zle_poswiadczenia_daja_czytelny_komunikat(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(401, json={"error": "Bad key"}))

    with pytest.raises(TestRailError, match="poświadczenia"):
        await _client().test_connection(12)


@pytest.mark.asyncio
async def test_brak_uprawnien_daje_czytelny_komunikat(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(403))

    with pytest.raises(TestRailError, match="uprawnień"):
        await _client().test_connection(12)


@pytest.mark.asyncio
async def test_limit_tempa_po_stronie_instancji_jest_rozpoznawany(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(429))

    with pytest.raises(TestRailError, match="tempo"):
        await _client().test_connection(12)


@pytest.mark.asyncio
async def test_komunikat_bledu_z_ciala_trafia_do_wyjatku(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(400, json={"error": "Field :title is required"}))

    with pytest.raises(TestRailError, match="title"):
        await _client().test_connection(12)


@pytest.mark.asyncio
async def test_blad_bez_ciala_nie_zaslania_kodu_http(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(500, text="<html>Server Error</html>"))

    with pytest.raises(TestRailError, match="HTTP 500"):
        await _client().test_connection(12)


@pytest.mark.asyncio
async def test_brak_polaczenia_z_instancja(monkeypatch):
    def _boom(request):
        raise httpx.ConnectError("DNS")

    _patch_transport(monkeypatch, _boom)

    with pytest.raises(TestRailError, match="Brak połączenia"):
        await _client().test_connection(12)


# ── sekcje ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sekcje_z_odpowiedzi_bedacej_lista(monkeypatch):
    """Instancje starsze niż 6.7 zwracają gołą listę."""
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json=[{"id": 1, "name": "A"}]))

    sections = await _client().get_sections(12)

    assert sections[0]["name"] == "A"


@pytest.mark.asyncio
async def test_sekcje_z_odpowiedzi_opakowanej(monkeypatch):
    """Od 6.7 wynik jest w obiekcie z paginacją."""
    _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(200, json={"offset": 0, "sections": [{"id": 2, "name": "B"}]}),
    )

    sections = await _client().get_sections(12)

    assert sections[0]["id"] == 2


@pytest.mark.asyncio
async def test_tworzenie_sekcji_przekazuje_nazwe(monkeypatch):
    import json

    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"id": 5}))

    created = await _client().create_section(12, "Moduł logowania")

    assert created["id"] == 5
    assert seen[0].url.path.endswith("index.php")
    assert json.loads(seen[0].content)["name"] == "Moduł logowania"


@pytest.mark.asyncio
async def test_sekcja_w_trybie_multi_suite_niesie_suite_id(monkeypatch):
    import json

    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"id": 5}))

    await _client().create_section(12, "Moduł", suite_id=3)

    assert json.loads(seen[0].content)["suite_id"] == 3


# ── przypadki i paginacja ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pobieranie_przypadkow_przechodzi_po_stronach(monkeypatch):
    pages = [
        {"cases": [{"id": i} for i in range(250)]},
        {"cases": [{"id": 999}]},
    ]

    def _handler(request):
        return httpx.Response(200, json=pages.pop(0) if pages else {"cases": []})

    seen = _patch_transport(monkeypatch, _handler)

    cases = await _client().get_cases(12)

    assert len(cases) == 251
    assert "offset=250" in str(seen[1].url)


@pytest.mark.asyncio
async def test_pobieranie_konczy_sie_na_niepelnej_stronie(monkeypatch):
    """Krótsza strona oznacza koniec — kolejne żądanie byłoby marnotrawstwem."""
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"cases": [{"id": 1}]}))

    await _client().get_cases(12)

    assert len(seen) == 1


@pytest.mark.asyncio
async def test_dodanie_przypadku_trafia_do_sekcji(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"id": 77}))

    created = await _client().add_case(5, {"title": "Test"})

    assert created["id"] == 77
    assert "add_case/5" in str(seen[0].url)


@pytest.mark.asyncio
async def test_aktualizacja_przypadku_trafia_do_case_id(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"id": 77}))

    await _client().update_case(77, {"title": "Nowy"})

    assert "update_case/77" in str(seen[0].url)


@pytest.mark.asyncio
async def test_pusta_odpowiedz_nie_wywraca_klienta(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, content=b""))

    assert await _client().update_case(77, {}) == {}


# ── dławienie tempa ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pierwsze_zadanie_nie_czeka(monkeypatch):
    """Odstęp ma dzielić żądania, nie opóźniać startu eksportu."""
    import app.services.export.testrail_service as module

    sleeps: list[float] = []
    monkeypatch.setattr(module.asyncio, "sleep", lambda s: sleeps.append(s) or _noop())

    await _REAL_THROTTLE(_client())

    assert sleeps == []


@pytest.mark.asyncio
async def test_kolejne_zadanie_odczekuje_zadany_odstep(monkeypatch):
    """Eksport setki przypadków to setka wywołań — bez odstępu instancja dławi."""
    import app.services.export.testrail_service as module

    sleeps: list[float] = []
    monkeypatch.setattr(module.asyncio, "sleep", lambda s: sleeps.append(s) or _noop())

    client = _client()
    await _REAL_THROTTLE(client)
    await _REAL_THROTTLE(client)

    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= MIN_REQUEST_INTERVAL_SECONDS


async def _noop() -> None:
    """Zastępnik ``asyncio.sleep`` — zwraca coś, co da się awaitować."""
    return None
