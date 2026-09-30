"""Testy orkiestracji eksportu do TestRaila — Story 8.8 (AC2-AC4; Task 5.2).

Najważniejsze zachowanie: ponowny eksport ma **aktualizować**, nie duplikować.
Duplikaty w TMS to najkosztowniejszy błąd tej funkcji — sprzątanie ich robi
się ręcznie, przypadek po przypadku.
"""

from unittest.mock import AsyncMock

import pytest

from app.services.export.tms_exporter import (
    DEFAULT_PRIORITY_ID,
    DEFAULT_PRIORITY_MAP,
    DEFAULT_TYPE_ID,
    TESTGEN_ID_FIELD,
    TestRailExporter,
    build_testrail_case,
    index_by_testgen_id,
    section_name_for,
)

TC_ID = "11111111-1111-1111-1111-111111111111"
CONFIG = {"testrail_project_id": 12}


def _row(**overrides) -> dict:
    row = {
        "id": TC_ID,
        "title": "Logowanie poprawnymi danymi",
        "preconditions": "Użytkownik ma konto",
        "steps": ["Otwórz stronę logowania", "Podaj dane", "Zatwierdź"],
        "expected_result": "Użytkownik zalogowany",
        "priority": "CRITICAL",
        "type": "FUNCTIONAL",
        "module": "AuthService",
        "source_function": "login",
    }
    row.update(overrides)
    return row


def _client(cases: list[dict] | None = None, sections: list[dict] | None = None) -> AsyncMock:
    client = AsyncMock()
    client.get_sections.return_value = sections or []
    client.get_cases.return_value = cases or []
    client.create_section.return_value = {"id": 100, "name": "AuthService"}
    client.add_case.return_value = {"id": 500}
    client.update_case.return_value = {"id": 500}
    return client


# ── mapowanie pól (AC2/AC4) ──────────────────────────────────────────────────


def test_domyslne_mapowanie_priorytetu_i_typu():
    payload = build_testrail_case(_row())

    assert payload["priority_id"] == DEFAULT_PRIORITY_MAP["CRITICAL"]
    assert payload["type_id"] == DEFAULT_TYPE_ID
    assert payload["title"] == "Logowanie poprawnymi danymi"


def test_nieznany_priorytet_spada_na_wartosc_domyslna():
    """Nowa wartość enuma nie może wywrócić eksportu całej paczki."""
    payload = build_testrail_case(_row(priority="WYMYSLONY"))

    assert payload["priority_id"] == DEFAULT_PRIORITY_ID


def test_wlasne_mapowanie_priorytetow_nadpisuje_domyslne():
    payload = build_testrail_case(_row(), {"priority_map": {"CRITICAL": 9}})

    assert payload["priority_id"] == 9


def test_wlasne_mapowanie_typow_nadpisuje_domyslne():
    payload = build_testrail_case(_row(type="SECURITY"), {"type_map": {"SECURITY": 42}})

    assert payload["type_id"] == 42


def test_mapowanie_jest_odporne_na_wielkosc_liter():
    payload = build_testrail_case(_row(), {"priority_map": {"critical": 9}})

    assert payload["priority_id"] == 9


def test_nieprawidlowa_wartosc_w_mapowaniu_jest_pomijana():
    """Literówka w konfiguracji nie może zablokować eksportu."""
    payload = build_testrail_case(_row(), {"priority_map": {"CRITICAL": "nie-liczba"}})

    assert payload["priority_id"] == DEFAULT_PRIORITY_MAP["CRITICAL"]


def test_kroki_ida_w_formacie_separated():
    """TestRail renderuje je wtedy jako tabelę, a nie jeden blok tekstu."""
    payload = build_testrail_case(_row())

    assert payload["custom_steps_separated"] == [
        {"content": "Otwórz stronę logowania", "expected": ""},
        {"content": "Podaj dane", "expected": ""},
        {"content": "Zatwierdź", "expected": ""},
    ]


def test_identyfikator_testgen_trafia_do_pola_wlasnego():
    """Bez niego deduplikacja nie ma się o co oprzeć."""
    assert build_testrail_case(_row())[TESTGEN_ID_FIELD] == TC_ID


def test_pusty_tytul_dostaje_zastepnik():
    """TestRail odrzuca przypadek bez tytułu — lepiej wyeksportować z etykietą."""
    payload = build_testrail_case(_row(title="   "))

    assert payload["title"] == "Przypadek testowy bez tytułu"


def test_dodatkowe_pola_wlasne_z_mapowania():
    payload = build_testrail_case(
        _row(), {"field_mapping": {"custom_moduł": "source_function"}}
    )

    assert payload["custom_moduł"] == "login"


def test_mapowanie_ignoruje_pola_bez_prefiksu_custom():
    """TestRail odrzuciłby nieznane pole systemowe — filtrujemy po prefiksie."""
    payload = build_testrail_case(_row(), {"field_mapping": {"refs": "source_function"}})

    assert "refs" not in payload


# ── sekcje (AC2) ─────────────────────────────────────────────────────────────


def test_nazwa_sekcji_z_modulu():
    assert section_name_for(_row()) == "AuthService"


def test_brak_modulu_daje_sekcje_zbiorcza():
    assert section_name_for(_row(module="")) == "TestGEN"


@pytest.mark.asyncio
async def test_sekcja_jest_tworzona_gdy_nie_istnieje():
    client = _client()

    await TestRailExporter(client, CONFIG).export([_row()])

    client.create_section.assert_awaited_once()
    assert client.create_section.await_args.args[1] == "AuthService"


@pytest.mark.asyncio
async def test_istniejaca_sekcja_nie_jest_tworzona_ponownie():
    client = _client(sections=[{"id": 100, "name": "AuthService"}])

    await TestRailExporter(client, CONFIG).export([_row()])

    client.create_section.assert_not_awaited()
    assert client.add_case.await_args.args[0] == 100


@pytest.mark.asyncio
async def test_sekcja_dopasowywana_bez_wzgledu_na_wielkosc_liter():
    client = _client(sections=[{"id": 100, "name": "authservice"}])

    await TestRailExporter(client, CONFIG).export([_row()])

    client.create_section.assert_not_awaited()


@pytest.mark.asyncio
async def test_sekcja_tworzona_raz_dla_wielu_przypadkow_z_modulu():
    """Inaczej TestRail dostałby tyle sekcji o tej samej nazwie, ile testów."""
    client = _client()
    rows = [_row(id=f"tc-{i}") for i in range(3)]

    await TestRailExporter(client, CONFIG).export(rows)

    assert client.create_section.await_count == 1
    assert client.add_case.await_count == 3


# ── deduplikacja (AC3) ───────────────────────────────────────────────────────


def test_indeks_buduje_sie_po_polu_testgen():
    cases = [
        {"id": 1, TESTGEN_ID_FIELD: "abc"},
        {"id": 2},  # bez znacznika — spoza TestGEN
        {"id": 3, TESTGEN_ID_FIELD: "def"},
    ]

    index = index_by_testgen_id(cases)

    assert set(index) == {"abc", "def"}
    assert index["abc"]["id"] == 1


@pytest.mark.asyncio
async def test_nowy_przypadek_jest_tworzony():
    client = _client()

    result = await TestRailExporter(client, CONFIG).export([_row()])

    assert (result.created, result.updated, result.failed) == (1, 0, 0)
    client.add_case.assert_awaited_once()
    client.update_case.assert_not_awaited()


@pytest.mark.asyncio
async def test_istniejacy_przypadek_jest_aktualizowany_nie_duplikowany():
    """Sedno AC3 — duplikaty w TMS sprząta się ręcznie, przypadek po przypadku."""
    client = _client(cases=[{"id": 777, TESTGEN_ID_FIELD: TC_ID}])

    result = await TestRailExporter(client, CONFIG).export([_row()])

    assert (result.created, result.updated, result.failed) == (0, 1, 0)
    client.update_case.assert_awaited_once()
    assert client.update_case.await_args.args[0] == 777
    client.add_case.assert_not_awaited()


@pytest.mark.asyncio
async def test_aktualizacja_nie_zaklada_nowej_sekcji():
    client = _client(cases=[{"id": 777, TESTGEN_ID_FIELD: TC_ID}])

    await TestRailExporter(client, CONFIG).export([_row()])

    client.create_section.assert_not_awaited()


@pytest.mark.asyncio
async def test_przypadki_spoza_testgen_nie_sa_ruszane():
    """Przypadek napisany ręcznie w TestRailu nie ma znacznika — zostawiamy go."""
    client = _client(cases=[{"id": 900, "title": "Ręczny test"}])

    result = await TestRailExporter(client, CONFIG).export([_row()])

    assert result.created == 1
    client.update_case.assert_not_awaited()


@pytest.mark.asyncio
async def test_lista_przypadkow_pobierana_raz_na_eksport():
    """Szukanie osobnym żądaniem per przypadek to N wywołań przy limicie 1/s."""
    client = _client()
    rows = [_row(id=f"tc-{i}") for i in range(5)]

    await TestRailExporter(client, CONFIG).export(rows)

    client.get_cases.assert_awaited_once()


# ── odporność i raport ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_blad_jednego_przypadku_nie_przerywa_pozostalych():
    client = _client()
    client.add_case.side_effect = [
        {"id": 1},
        RuntimeError("TestRail odrzucił przypadek"),
        {"id": 3},
    ]
    rows = [_row(id=f"tc-{i}", module="Wspolny") for i in range(3)]

    result = await TestRailExporter(client, CONFIG).export(rows)

    assert (result.created, result.failed) == (2, 1)
    failed = [i for i in result.items if i.action == "failed"]
    assert failed[0].error.startswith("TestRail odrzucił")


@pytest.mark.asyncio
async def test_pusta_lista_nie_woła_api():
    client = _client()

    result = await TestRailExporter(client, CONFIG).export([])

    assert result.total == 0
    client.get_cases.assert_not_awaited()
    client.get_sections.assert_not_awaited()


@pytest.mark.asyncio
async def test_postep_raportowany_po_kazdym_przypadku():
    """Eksport setki testów przy limicie tempa trwa minuty — bez postępu
    użytkownik nie wie, czy coś się dzieje."""
    client = _client()
    seen: list[tuple[int, int]] = []
    rows = [_row(id=f"tc-{i}") for i in range(3)]

    await TestRailExporter(client, CONFIG).export(rows, progress=lambda d, t: seen.append((d, t)))

    assert seen == [(1, 3), (2, 3), (3, 3)]


@pytest.mark.asyncio
async def test_raport_zawiera_identyfikatory_z_testrail():
    client = _client()

    result = await TestRailExporter(client, CONFIG).export([_row()])
    payload = result.as_dict()

    assert payload["created"] == 1
    assert payload["items"][0]["testrail_case_id"] == 500
    assert payload["items"][0]["test_case_id"] == TC_ID


@pytest.mark.asyncio
async def test_tryb_multi_suite_przekazuje_suite_id():
    client = _client()

    await TestRailExporter(client, {**CONFIG, "suite_id": 3}).export([_row()])

    assert client.get_sections.await_args.kwargs["suite_id"] == 3
    assert client.get_cases.await_args.kwargs["suite_id"] == 3


# ═══ Story 8.9: Xray i Zephyr Scale ══════════════════════════════════════════

from app.services.export.jira_tms_service import (  # noqa: E402
    ZEPHYR_TESTGEN_FIELD,
    testgen_label,
)
from app.services.export.tms_exporter import (  # noqa: E402
    DEFAULT_JIRA_PRIORITY_MAP,
    XrayExporter,
    ZephyrExporter,
    build_xray_test,
    build_xray_update_fields,
    build_zephyr_testcase,
    zephyr_folder_for,
)

JIRA_CONFIG = {"jira_project_key": "QA"}


def _jira_client(xray_index=None, zephyr_index=None, folders=None) -> AsyncMock:
    client = AsyncMock()
    client.xray_find_all_testgen.return_value = xray_index or {}
    client.xray_import_tests.return_value = {"testIssues": [{"key": "QA-1"}]}
    client.xray_update_test.return_value = {"key": "QA-1"}
    client.zephyr_find_all_testgen.return_value = zephyr_index or {}
    client.zephyr_get_folders.return_value = folders or []
    client.zephyr_create_testcase.return_value = {"key": "QA-T1"}
    client.zephyr_update_testcase.return_value = {"key": "QA-T1"}
    return client


# ── budowanie testu Xray (AC2) ───────────────────────────────────────────────


def test_xray_niesie_etykiete_testgen():
    """Bez niej ponowny eksport zrobiłby duplikat zamiast aktualizacji."""
    test = build_xray_test(_row())

    assert testgen_label(TC_ID) in test["fields"]["labels"]


def test_xray_mapuje_priorytet_na_nazwe_jiry():
    """Jira adresuje priorytety nazwą, nie liczbą jak TestRail."""
    test = build_xray_test(_row(priority="CRITICAL"))

    assert test["fields"]["priority"]["name"] == DEFAULT_JIRA_PRIORITY_MAP["CRITICAL"]


def test_xray_nieznany_priorytet_spada_na_medium():
    test = build_xray_test(_row(priority="WYMYSLONY"))

    assert test["fields"]["priority"]["name"] == "Medium"


def test_xray_typ_testu_trafia_do_etykiety():
    """Komponenty Jiry trzeba wcześniej założyć; etykiety powstają same."""
    test = build_xray_test(_row(type="SECURITY"))

    assert "typ-bezpieczenstwa" in test["fields"]["labels"]


def test_xray_wlasne_mapowanie_priorytetow():
    test = build_xray_test(_row(), {"jira_priority_map": {"CRITICAL": "Blocker"}})

    assert test["fields"]["priority"]["name"] == "Blocker"


def test_xray_kroki_w_formacie_wtyczki():
    test = build_xray_test(_row())

    assert [s["action"] for s in test["steps"]] == [
        "Otwórz stronę logowania",
        "Podaj dane",
        "Zatwierdź",
    ]


def test_xray_oczekiwany_rezultat_dopiety_do_ostatniego_kroku():
    """Xray wiąże rezultat z krokiem — inaczej zginąłby przy imporcie."""
    test = build_xray_test(_row())

    assert test["steps"][-1]["result"] == "Użytkownik zalogowany"
    assert test["steps"][0]["result"] == ""


def test_xray_pusty_tytul_dostaje_zastepnik():
    assert build_xray_test(_row(title=""))["fields"]["summary"] == "Przypadek testowy bez tytułu"


def test_xray_aktualizacja_zachowuje_cudze_etykiety():
    """Zespół mógł dodać własne — nadpisanie listy kasowałoby je co eksport."""
    fields = build_xray_update_fields(_row(), ["sprint-12", "regresja"])

    assert "sprint-12" in fields["labels"]
    assert "regresja" in fields["labels"]
    assert testgen_label(TC_ID) in fields["labels"]


def test_xray_aktualizacja_nie_duplikuje_etykiety_testgen():
    fields = build_xray_update_fields(_row(), [testgen_label(TC_ID)])

    assert fields["labels"].count(testgen_label(TC_ID)) == 1


# ── budowanie przypadku Zephyra (AC3) ────────────────────────────────────────


def test_zephyr_niesie_pole_wlasne_testgen():
    payload = build_zephyr_testcase(_row(), "QA")

    assert payload["customFields"][ZEPHYR_TESTGEN_FIELD] == TC_ID


def test_zephyr_mapuje_pola_na_slownik_wtyczki():
    payload = build_zephyr_testcase(_row(), "QA")

    assert payload["name"] == "Logowanie poprawnymi danymi"
    assert payload["precondition"] == "Użytkownik ma konto"
    assert payload["testScript"]["type"] == "STEP_BY_STEP"
    assert len(payload["testScript"]["steps"]) == 3


def test_zephyr_oczekiwany_rezultat_na_ostatnim_kroku():
    payload = build_zephyr_testcase(_row(), "QA")

    assert payload["testScript"]["steps"][-1]["expectedResult"] == "Użytkownik zalogowany"


def test_zephyr_folder_z_modulu():
    assert zephyr_folder_for(_row()) == "/TestGEN/AuthService"


def test_zephyr_brak_modulu_daje_folder_zbiorczy():
    assert zephyr_folder_for(_row(module="")) == "/TestGEN"


# ── eksport Xray (AC2/AC4) ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_xray_nowy_test_jest_importowany():
    client = _jira_client()

    result = await XrayExporter(client, JIRA_CONFIG).export([_row()])

    assert (result.created, result.updated, result.failed) == (1, 0, 0)
    client.xray_import_tests.assert_awaited_once()
    client.xray_update_test.assert_not_awaited()
    assert result.items[0].external_key == "QA-1"


@pytest.mark.asyncio
async def test_xray_istniejacy_test_jest_aktualizowany():
    client = _jira_client(
        xray_index={TC_ID: {"key": "QA-7", "fields": {"labels": [testgen_label(TC_ID)]}}}
    )

    result = await XrayExporter(client, JIRA_CONFIG).export([_row()])

    assert (result.created, result.updated) == (0, 1)
    assert client.xray_update_test.await_args.args[0] == "QA-7"
    client.xray_import_tests.assert_not_awaited()


@pytest.mark.asyncio
async def test_xray_import_dostaje_klucz_projektu():
    client = _jira_client()

    await XrayExporter(client, JIRA_CONFIG).export([_row()])

    sent = client.xray_import_tests.await_args.args[0][0]
    assert sent["fields"]["project"] == {"key": "QA"}


@pytest.mark.asyncio
async def test_xray_wiaze_test_z_wymaganiem_gdy_skonfigurowane():
    client = _jira_client()

    await XrayExporter(client, {**JIRA_CONFIG, "linked_issue": "QA-42"}).export([_row()])

    client.xray_link_to_requirement.assert_awaited_once_with("QA-1", "QA-42")


@pytest.mark.asyncio
async def test_xray_nieudane_powiazanie_nie_uniewaznia_testu():
    """Powiązanie jest dodatkiem — test został utworzony i to się liczy."""
    client = _jira_client()
    client.xray_link_to_requirement.side_effect = RuntimeError("brak uprawnień")

    result = await XrayExporter(client, {**JIRA_CONFIG, "linked_issue": "QA-42"}).export([_row()])

    assert result.created == 1
    assert result.failed == 0


@pytest.mark.asyncio
async def test_xray_blad_jednego_testu_nie_przerywa_pozostalych():
    client = _jira_client()
    client.xray_import_tests.side_effect = [
        {"testIssues": [{"key": "QA-1"}]},
        RuntimeError("Jira odrzuciła"),
        {"testIssues": [{"key": "QA-3"}]},
    ]
    rows = [_row(id=f"tc-{i}") for i in range(3)]

    result = await XrayExporter(client, JIRA_CONFIG).export(rows)

    assert (result.created, result.failed) == (2, 1)


@pytest.mark.asyncio
async def test_xray_indeks_pobierany_raz_na_eksport():
    client = _jira_client()
    rows = [_row(id=f"tc-{i}") for i in range(5)]

    await XrayExporter(client, JIRA_CONFIG).export(rows)

    client.xray_find_all_testgen.assert_awaited_once()


@pytest.mark.asyncio
async def test_xray_pusta_lista_nie_wola_api():
    client = _jira_client()

    result = await XrayExporter(client, JIRA_CONFIG).export([])

    assert result.total == 0
    client.xray_find_all_testgen.assert_not_awaited()


# ── eksport Zephyr (AC3/AC4) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zephyr_nowy_przypadek_jest_tworzony():
    client = _jira_client()

    result = await ZephyrExporter(client, JIRA_CONFIG).export([_row()])

    assert (result.created, result.updated) == (1, 0)
    assert result.items[0].external_key == "QA-T1"


@pytest.mark.asyncio
async def test_zephyr_istniejacy_przypadek_jest_aktualizowany():
    client = _jira_client(zephyr_index={TC_ID: {"key": "QA-T9"}})

    result = await ZephyrExporter(client, JIRA_CONFIG).export([_row()])

    assert (result.created, result.updated) == (0, 1)
    assert client.zephyr_update_testcase.await_args.args[0] == "QA-T9"
    client.zephyr_create_testcase.assert_not_awaited()


@pytest.mark.asyncio
async def test_zephyr_folder_jest_tworzony_raz():
    client = _jira_client()
    rows = [_row(id=f"tc-{i}") for i in range(3)]

    await ZephyrExporter(client, JIRA_CONFIG).export(rows)

    assert client.zephyr_create_folder.await_count == 1


@pytest.mark.asyncio
async def test_zephyr_istniejacy_folder_nie_jest_tworzony():
    client = _jira_client(folders=[{"name": "/TestGEN/AuthService"}])

    await ZephyrExporter(client, JIRA_CONFIG).export([_row()])

    client.zephyr_create_folder.assert_not_awaited()


@pytest.mark.asyncio
async def test_zephyr_odrzucony_duplikat_folderu_nie_przerywa_eksportu():
    """Zephyr odrzuca duplikat nazwy — to znaczy, że folder już jest."""
    client = _jira_client()
    client.zephyr_create_folder.side_effect = RuntimeError("folder already exists")

    result = await ZephyrExporter(client, JIRA_CONFIG).export([_row()])

    assert result.created == 1


@pytest.mark.asyncio
async def test_zephyr_wiaze_przypadek_ze_zgloszeniem():
    client = _jira_client()

    await ZephyrExporter(client, {**JIRA_CONFIG, "linked_issue": "QA-42"}).export([_row()])

    client.zephyr_link_issue.assert_awaited_once_with("QA-T1", "QA-42")


@pytest.mark.asyncio
async def test_zephyr_postep_raportowany_po_kazdym_przypadku():
    client = _jira_client()
    seen: list[tuple[int, int]] = []
    rows = [_row(id=f"tc-{i}") for i in range(2)]

    await ZephyrExporter(client, JIRA_CONFIG).export(rows, progress=lambda d, t: seen.append((d, t)))

    assert seen == [(1, 2), (2, 2)]
