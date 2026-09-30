"""Testy klienta Jiry dla Xraya i Zephyra — Story 8.9 (AC1-AC4; Task 8.1).

httpx mockowany transportem (wzorzec test_testrail_service). Nacisk idzie na
to, co różni obie wtyczki: Xray trzyma testy jako zgłoszenia Jiry (JQL,
etykiety), Zephyr ma własny magazyn pod ``/rest/atm/1.0`` i własne klucze.
"""

import base64
import json

import httpx
import pytest

from app.core.exceptions import ValidationError
from app.services.export.jira_tms_service import (
    MIN_REQUEST_INTERVAL_SECONDS,
    XRAY_LABEL_PREFIX,
    ZEPHYR_TESTGEN_FIELD,
    JiraTmsClient,
    JiraTmsError,
    normalize_url,
    testgen_label,
)

URL = "https://firma.atlassian.net"
EMAIL = "qa@firma.pl"
TOKEN = "token-atlassian"
PROJECT = "QA"
TC_ID = "11111111-1111-1111-1111-111111111111"

_REAL_THROTTLE = JiraTmsClient._throttle


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    """Dławienie testujemy osobno — reszta testów nie ma na nie czekać."""

    async def _instant(self) -> None:
        return None

    monkeypatch.setattr(JiraTmsClient, "_throttle", _instant)


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


def _client() -> JiraTmsClient:
    return JiraTmsClient(URL, EMAIL, TOKEN)


# ── adres i etykiety ─────────────────────────────────────────────────────────


def test_normalize_obcina_sciezke():
    assert normalize_url("https://firma.atlassian.net/jira/software/") == URL


@pytest.mark.parametrize("bad", ["http://firma.atlassian.net", "firma.atlassian.net", ""])
def test_normalize_wymaga_https(bad):
    with pytest.raises(ValidationError):
        normalize_url(bad)


def test_etykieta_nie_zawiera_spacji():
    """Jira odrzuca etykiety ze spacjami — UUID z prefiksem przechodzi."""
    label = testgen_label(TC_ID)

    assert label == f"{XRAY_LABEL_PREFIX}{TC_ID}"
    assert " " not in label


# ── uwierzytelnianie i błędy ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_uzywa_basic_auth_atlassian(monkeypatch):
    seen = _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(200, json={"displayName": "QA", "key": PROJECT, "name": "Projekt QA"}),
    )

    await _client().test_connection(PROJECT)

    decoded = base64.b64decode(seen[0].headers["Authorization"].removeprefix("Basic ")).decode()
    assert decoded == f"{EMAIL}:{TOKEN}"


@pytest.mark.asyncio
async def test_test_connection_sprawdza_konto_i_projekt(monkeypatch):
    seen = _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(
            200, json={"displayName": "Anna QA", "key": PROJECT, "name": "Projekt QA"}
        ),
    )

    result = await _client().test_connection(PROJECT)

    assert result["connected"] is True
    assert result["account"] == "Anna QA"
    assert result["project_name"] == "Projekt QA"
    assert seen[0].url.path.endswith("/myself")
    assert seen[1].url.path.endswith(f"/project/{PROJECT}")


@pytest.mark.asyncio
async def test_zle_poswiadczenia_daja_czytelny_komunikat(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(401))

    with pytest.raises(JiraTmsError, match="poświadczenia"):
        await _client().test_connection(PROJECT)


@pytest.mark.asyncio
async def test_404_wskazuje_na_brak_wtyczki(monkeypatch):
    """Najczęstsza przyczyna 404 na ścieżkach wtyczek to jej brak w instancji."""
    _patch_transport(monkeypatch, lambda r: httpx.Response(404))

    with pytest.raises(JiraTmsError, match="wtyczka"):
        await _client().xray_import_tests([])


@pytest.mark.asyncio
async def test_komunikat_bledu_jiry_trafia_do_wyjatku(monkeypatch):
    _patch_transport(
        monkeypatch,
        lambda r: httpx.Response(400, json={"errorMessages": ["Field 'summary' is required"]}),
    )

    with pytest.raises(JiraTmsError, match="summary"):
        await _client().xray_import_tests([])


@pytest.mark.asyncio
async def test_blad_bez_ciala_nie_zaslania_kodu(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(500, text="<html/>"))

    with pytest.raises(JiraTmsError, match="HTTP 500"):
        await _client().xray_import_tests([])


@pytest.mark.asyncio
async def test_brak_polaczenia(monkeypatch):
    def _boom(request):
        raise httpx.ConnectError("DNS")

    _patch_transport(monkeypatch, _boom)

    with pytest.raises(JiraTmsError, match="Brak połączenia"):
        await _client().test_connection(PROJECT)


# ── Xray (AC2/AC4) ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_xray_idzie_na_endpoint_raven(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"testIssues": []}))

    await _client().xray_import_tests([{"fields": {"summary": "Test"}}])

    assert seen[0].url.path == "/rest/raven/1.0/import/test"
    assert json.loads(seen[0].content)["tests"][0]["fields"]["summary"] == "Test"


@pytest.mark.asyncio
async def test_wyszukiwanie_po_etykiecie_uzywa_jql(monkeypatch):
    seen = _patch_transport(
        monkeypatch, lambda r: httpx.Response(200, json={"issues": [{"key": "QA-1"}]})
    )

    found = await _client().xray_find_by_testgen_id(PROJECT, TC_ID)

    assert found["key"] == "QA-1"
    jql = seen[0].url.params["jql"]
    assert f'project = "{PROJECT}"' in jql
    assert testgen_label(TC_ID) in jql


@pytest.mark.asyncio
async def test_wyszukiwanie_bez_wyniku_zwraca_none(monkeypatch):
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={"issues": []}))

    assert await _client().xray_find_by_testgen_id(PROJECT, TC_ID) is None


@pytest.mark.asyncio
async def test_indeks_xray_buduje_sie_z_etykiet(monkeypatch):
    """Jedno zapytanie zamiast jednego na przypadek — przy limicie tempa to minuty."""
    payload = {
        "issues": [
            {"key": "QA-1", "fields": {"labels": [testgen_label("aaa"), "inne"]}},
            {"key": "QA-2", "fields": {"labels": ["recznie-napisany"]}},
            {"key": "QA-3", "fields": {"labels": [testgen_label("bbb")]}},
        ]
    }
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json=payload))

    index = await _client().xray_find_all_testgen(PROJECT)

    assert set(index) == {"aaa", "bbb"}
    assert index["aaa"]["key"] == "QA-1"


@pytest.mark.asyncio
async def test_indeks_xray_przechodzi_po_stronach(monkeypatch):
    pages = [
        {"issues": [{"key": f"QA-{i}", "fields": {"labels": [testgen_label(str(i))]}} for i in range(50)]},
        {"issues": [{"key": "QA-99", "fields": {"labels": [testgen_label("99")]}}]},
    ]
    seen = _patch_transport(
        monkeypatch, lambda r: httpx.Response(200, json=pages.pop(0) if pages else {"issues": []})
    )

    index = await _client().xray_find_all_testgen(PROJECT)

    assert len(index) == 51
    assert seen[1].url.params["startAt"] == "50"


@pytest.mark.asyncio
async def test_aktualizacja_xray_idzie_przez_put_issue(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(204))

    result = await _client().xray_update_test("QA-1", {"summary": "Nowy"})

    assert result["key"] == "QA-1"
    assert seen[0].method == "PUT"
    assert seen[0].url.path.endswith("/issue/QA-1")
    assert json.loads(seen[0].content)["fields"]["summary"] == "Nowy"


@pytest.mark.asyncio
async def test_powiazanie_z_wymaganiem(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, json={}))

    await _client().xray_link_to_requirement("QA-1", "QA-42")

    assert seen[0].url.path == "/rest/raven/1.0/link/QA-1/QA-42"


# ── Zephyr Scale (AC3/AC4) ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tworzenie_przypadku_zephyra(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={"key": "QA-T1"}))

    created = await _client().zephyr_create_testcase({"name": "Test", "projectKey": PROJECT})

    assert created["key"] == "QA-T1"
    assert seen[0].url.path == "/rest/atm/1.0/testcase"


@pytest.mark.asyncio
async def test_aktualizacja_przypadku_zephyra(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(200, content=b""))

    result = await _client().zephyr_update_testcase("QA-T1", {"name": "Nowy"})

    assert result["key"] == "QA-T1"
    assert seen[0].method == "PUT"
    assert seen[0].url.path.endswith("/testcase/QA-T1")


@pytest.mark.asyncio
async def test_indeks_zephyra_po_polu_wlasnym(monkeypatch):
    payload = [
        {"key": "QA-T1", "customFields": {ZEPHYR_TESTGEN_FIELD: "aaa"}},
        {"key": "QA-T2", "customFields": {}},
        {"key": "QA-T3", "customFields": {ZEPHYR_TESTGEN_FIELD: "bbb"}},
    ]
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json=payload))

    index = await _client().zephyr_find_all_testgen(PROJECT)

    assert set(index) == {"aaa", "bbb"}


@pytest.mark.asyncio
async def test_indeks_zephyra_obsluguje_odpowiedz_opakowana(monkeypatch):
    """Instancje zwracają wynik raz jako listę, raz w obiekcie z ``results``."""
    payload = {"results": [{"key": "QA-T1", "customFields": {ZEPHYR_TESTGEN_FIELD: "aaa"}}]}
    _patch_transport(monkeypatch, lambda r: httpx.Response(200, json=payload))

    assert set(await _client().zephyr_find_all_testgen(PROJECT)) == {"aaa"}


@pytest.mark.asyncio
async def test_tworzenie_folderu_zephyra(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={"id": 1}))

    await _client().zephyr_create_folder(PROJECT, "/TestGEN/AuthService")

    body = json.loads(seen[0].content)
    assert body["projectKey"] == PROJECT
    assert body["name"] == "/TestGEN/AuthService"
    assert body["type"] == "TEST_CASE"


@pytest.mark.asyncio
async def test_powiazanie_przypadku_zephyra_ze_zgloszeniem(monkeypatch):
    seen = _patch_transport(monkeypatch, lambda r: httpx.Response(201, json={}))

    await _client().zephyr_link_issue("QA-T1", "QA-42")

    assert seen[0].url.path.endswith("/testcase/QA-T1/issuelinks")
    assert json.loads(seen[0].content)["issueKey"] == "QA-42"


# ── dławienie tempa ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pierwsze_zadanie_nie_czeka(monkeypatch):
    import app.services.export.jira_tms_service as module

    sleeps: list[float] = []
    monkeypatch.setattr(module.asyncio, "sleep", lambda s: sleeps.append(s) or _noop())

    await _REAL_THROTTLE(_client())

    assert sleeps == []


@pytest.mark.asyncio
async def test_kolejne_zadanie_odczekuje(monkeypatch):
    import app.services.export.jira_tms_service as module

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
