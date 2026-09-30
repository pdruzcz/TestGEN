"""Serwis dwukierunkowej synchronizacji z TMS — Story 8.11 (Task 6.1).

Funkcje decyzyjne (konflikt, zwycięzca, scalenie pól) są czyste i testowane
wprost; części rozmawiające z bazą dostają atrapę sesji.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ValidationError
from app.models.integration import SyncStatus
from app.models.sync_conflict import ConflictResolution
from app.models.sync_state import (
    DEGRADED_AFTER_FAILURES,
    ConflictStrategy,
    SyncDirection,
    SyncHealth,
    SyncState,
)
from app.models.test_case import TestCase, TestPriority
from app.services.export import sync_service as svc

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


def _state(**overrides) -> SyncState:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "integration_id": uuid.uuid4(),
        "project_id": uuid.uuid4(),
        "provider": "testrail",
        "direction": SyncDirection.BIDIRECTIONAL,
        "conflict_strategy": ConflictStrategy.LAST_WRITE_WINS,
        "interval_minutes": 15,
        "is_active": True,
        "last_sync_at": None,
        "consecutive_failures": 0,
        "health": SyncHealth.ACTIVE,
        "synced_count": 0,
    }
    defaults.update(overrides)
    return SyncState(**defaults)


def _test_case(**overrides) -> TestCase:
    defaults = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "analysis_result_id": uuid.uuid4(),
        "title": "Logowanie zwraca token",
        "description": "Opis z TestGEN",
        "priority": TestPriority.MEDIUM,
        "steps": {"items": ["Krok 1"]},
        "expected_result": "Token",
        "created_at": NOW - timedelta(days=1),
        "updated_at": NOW - timedelta(hours=1),
    }
    defaults.update(overrides)
    return TestCase(**defaults)


def _remote(**overrides) -> svc.RemoteCase:
    defaults = {
        "testgen_id": "tc-1",
        "external_id": "42",
        "title": "Logowanie zwraca token",
        "updated_at": NOW - timedelta(hours=2),
        "fields": {},
    }
    defaults.update(overrides)
    return svc.RemoteCase(**defaults)


# ── normalizacja odpowiedzi TMS ─────────────────────────────────────────────


def test_testrail_bez_znacznika_testgen_jest_pomijany():
    assert svc.remote_from_testrail({"id": 7, "title": "Obcy przypadek"}) is None


def test_testrail_czyta_sekundy_uniksowe():
    remote = svc.remote_from_testrail(
        {
            "id": 7,
            "title": "Tytuł",
            "custom_testgen_id": "tc-1",
            "updated_on": 1758801600,
            "custom_steps": "Krok 1\nKrok 2",
            "custom_expected": "Wynik",
        }
    )

    assert remote is not None
    assert remote.external_id == "7"
    assert remote.updated_at == datetime.fromtimestamp(1758801600, tz=UTC)
    assert remote.fields["steps"] == ["Krok 1", "Krok 2"]


def test_xray_wyciaga_identyfikator_z_etykiety():
    remote = svc.remote_from_xray(
        {
            "key": "QA-5",
            "fields": {
                "summary": "Tytuł",
                "labels": ["regresja", "testgen-tc-9"],
                "updated": "2026-09-25T10:00:00.000+0000",
                "priority": {"name": "High"},
            },
        }
    )

    assert remote is not None
    assert remote.testgen_id == "tc-9"
    assert remote.external_id == "QA-5"
    assert remote.fields["priority"] == "High"


def test_xray_bez_etykiety_testgen_jest_pomijany():
    assert svc.remote_from_xray({"key": "QA-1", "fields": {"labels": ["regresja"]}}) is None


def test_zephyr_czyta_kroki_ze_skryptu():
    remote = svc.remote_from_zephyr(
        {
            "key": "QA-T3",
            "name": "Tytuł",
            "customFields": {"testgen_id": "tc-3"},
            "updatedOn": "2026-09-25T10:00:00Z",
            "testScript": {"steps": [{"description": "Krok A"}, {"description": ""}]},
            "objective": "Cel",
        }
    )

    assert remote is not None
    assert remote.fields["steps"] == ["Krok A"]
    assert remote.fields["description"] == "Cel"


def test_nieczytelny_znacznik_czasu_nie_wysadza_synchronizacji():
    remote = svc.remote_from_testrail(
        {"id": 1, "custom_testgen_id": "tc-1", "updated_on": "wczoraj"}
    )

    assert remote is not None
    assert remote.updated_at is None


# ── wykrywanie konfliktów ───────────────────────────────────────────────────


def test_pierwszy_przebieg_nie_daje_konfliktu():
    # Bez punktu odniesienia „obie strony zmienione" nie ma znaczenia.
    assert (
        svc.detect_conflict(NOW, _remote(updated_at=NOW), last_sync_at=None) is False
    )


def test_konflikt_gdy_obie_strony_zmienione_po_ostatniej_synchronizacji():
    last = NOW - timedelta(hours=3)

    assert svc.detect_conflict(NOW - timedelta(hours=1), _remote(updated_at=NOW), last) is True


def test_brak_konfliktu_gdy_zmienil_sie_tylko_tms():
    last = NOW - timedelta(hours=3)

    assert svc.detect_conflict(last - timedelta(hours=1), _remote(updated_at=NOW), last) is False


def test_brak_konfliktu_gdy_tms_nie_podaje_znacznika():
    last = NOW - timedelta(hours=3)

    assert svc.detect_conflict(NOW, _remote(updated_at=None), last) is False


def test_nowszy_wygrywa():
    assert svc.choose_winner(NOW - timedelta(hours=1), _remote(updated_at=NOW)) == "tms"
    assert svc.choose_winner(NOW, _remote(updated_at=NOW - timedelta(hours=1))) == "testgen"


def test_brak_znacznika_w_tms_oddaje_wygrana_testgenowi():
    assert svc.choose_winner(None, _remote(updated_at=None)) == "testgen"


# ── scalanie pól ────────────────────────────────────────────────────────────


def test_scalenie_wnosi_zmienione_pola():
    test_case = _test_case()
    remote = _remote(
        title="Nowy tytuł",
        fields={"description": "Opis z TMS", "steps": ["Krok A"], "priority": "High"},
    )

    changed = svc.apply_remote(test_case, remote)

    assert set(changed) == {"title", "description", "steps", "priority"}
    assert test_case.title == "Nowy tytuł"
    assert test_case.steps == {"items": ["Krok A"]}
    assert test_case.priority is TestPriority.HIGH


def test_puste_pole_w_tms_nie_kasuje_wartosci():
    test_case = _test_case(description="Opis, którego nikt nie tknął")
    remote = _remote(title="", fields={"description": "", "steps": []})

    assert svc.apply_remote(test_case, remote) == []
    assert test_case.description == "Opis, którego nikt nie tknął"


def test_nierozpoznany_priorytet_nie_zmienia_przypadku():
    test_case = _test_case(priority=TestPriority.MEDIUM)

    svc.apply_remote(test_case, _remote(fields={"priority": "Bardzo pilne"}))

    assert test_case.priority is TestPriority.MEDIUM


def test_nazwy_priorytetow_testraila_sa_rozpoznawane():
    test_case = _test_case(priority=TestPriority.LOW)

    svc.apply_remote(test_case, _remote(fields={"priority": "Must Test"}))

    assert test_case.priority is TestPriority.CRITICAL


# ── harmonogram ─────────────────────────────────────────────────────────────


def test_nieaktywna_synchronizacja_nigdy_nie_jest_zalegla():
    assert svc.is_due(_state(is_active=False, last_sync_at=None), NOW) is False


def test_pierwszy_przebieg_jest_natychmiast_zalegly():
    assert svc.is_due(_state(last_sync_at=None), NOW) is True


def test_przebieg_przed_uplywem_odstepu_nie_jest_zalegly():
    state = _state(last_sync_at=NOW - timedelta(minutes=5), interval_minutes=15)

    assert svc.is_due(state, NOW) is False


def test_przebieg_po_uplywie_odstepu_jest_zalegly():
    state = _state(last_sync_at=NOW - timedelta(minutes=20), interval_minutes=15)

    assert svc.is_due(state, NOW) is True


def test_odstep_ponizej_minimum_jest_podnoszony_do_minimum():
    # Wiersz z zaniżonym odstępem (np. z migracji danych) nie może obejść
    # granicy, której broni walidacja konfiguracji.
    state = _state(last_sync_at=NOW - timedelta(minutes=2), interval_minutes=1)

    assert svc.is_due(state, NOW) is False


# ── zdrowie ─────────────────────────────────────────────────────────────────


def test_udany_przebieg_zeruje_licznik_i_przywraca_zdrowie():
    state = _state(consecutive_failures=4, health=SyncHealth.DEGRADED)
    outcome = svc.SyncOutcome(pushed=2, pulled=1)

    svc.record_success(state, outcome, NOW)

    assert state.consecutive_failures == 0
    assert state.health is SyncHealth.ACTIVE
    assert state.last_sync_status is SyncStatus.SUCCESS
    assert state.synced_count == 3


def test_degradacja_dopiero_po_trzeciej_porazce():
    state = _state()
    degraded = [svc.record_failure(state, "timeout", NOW) for _ in range(DEGRADED_AFTER_FAILURES)]

    assert degraded == [False, False, True]
    assert state.health is SyncHealth.DEGRADED


def test_kolejna_porazka_nie_powtarza_powiadomienia():
    state = _state(consecutive_failures=DEGRADED_AFTER_FAILURES, health=SyncHealth.DEGRADED)

    assert svc.record_failure(state, "timeout", NOW) is False


def test_porazka_przesuwa_termin_nastepnej_proby():
    # Inaczej beat podejmowałby zaległą synchronizację co pięć minut
    # i niedostępny TMS dostawałby lawinę żądań.
    state = _state(last_sync_at=NOW - timedelta(hours=2))

    svc.record_failure(state, "timeout", NOW)

    assert state.last_sync_at == NOW
    assert svc.is_due(state, NOW) is False


def test_status_przebiegu_z_konfliktami_jest_czesciowy():
    assert svc.SyncOutcome(pulled=1, conflicts=1).status is SyncStatus.PARTIAL
    assert svc.SyncOutcome(failed=1).status is SyncStatus.FAILED
    assert svc.SyncOutcome(pushed=3).status is SyncStatus.SUCCESS


# ── przebieg pull ───────────────────────────────────────────────────────────


def _db_with_test_cases(*test_cases) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(test_cases)
    db.execute.return_value = result
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_pull_wnosi_zmiany_z_tms():
    test_case = _test_case()
    db = _db_with_test_cases(test_case)
    state = _state(last_sync_at=None)
    remote = _remote(testgen_id=str(test_case.id), title="Tytuł z TMS")

    outcome = await svc.run_pull_sync(db, state, {str(test_case.id): remote})

    assert outcome.pulled == 1
    assert test_case.title == "Tytuł z TMS"


@pytest.mark.asyncio
async def test_pull_pomija_przypadek_nieobecny_w_testgen():
    db = _db_with_test_cases()
    outcome = await svc.run_pull_sync(db, _state(), {"tc-obcy": _remote()})

    assert outcome.skipped == 1
    assert outcome.pulled == 0


@pytest.mark.asyncio
async def test_pull_pomija_przypadek_niezmieniony_w_tms():
    test_case = _test_case()
    db = _db_with_test_cases(test_case)
    state = _state(last_sync_at=NOW - timedelta(minutes=30))
    remote = _remote(
        testgen_id=str(test_case.id),
        title="Inny tytuł",
        updated_at=NOW - timedelta(hours=5),
    )

    outcome = await svc.run_pull_sync(db, state, {str(test_case.id): remote})

    assert outcome.skipped == 1
    assert test_case.title == "Logowanie zwraca token"


@pytest.mark.asyncio
async def test_pull_przy_konflikcie_zapisuje_obie_wersje():
    last = NOW - timedelta(hours=3)
    test_case = _test_case(updated_at=NOW - timedelta(hours=1))
    db = _db_with_test_cases(test_case)
    state = _state(last_sync_at=last, conflict_strategy=ConflictStrategy.LAST_WRITE_WINS)
    remote = _remote(testgen_id=str(test_case.id), title="Wersja TMS", updated_at=NOW)

    outcome = await svc.run_pull_sync(db, state, {str(test_case.id): remote})

    assert outcome.conflicts == 1
    conflict = db.add.call_args[0][0]
    assert conflict.resolution is ConflictResolution.TMS_WINS
    assert conflict.testgen_version["title"] == "Logowanie zwraca token"
    assert conflict.tms_version["title"] == "Wersja TMS"
    # Nowszy wygrał, więc zmiana weszła.
    assert test_case.title == "Wersja TMS"


@pytest.mark.asyncio
async def test_pull_przy_wygranej_testgen_nie_nadpisuje_przypadku():
    last = NOW - timedelta(hours=3)
    test_case = _test_case(updated_at=NOW)
    db = _db_with_test_cases(test_case)
    state = _state(last_sync_at=last)
    remote = _remote(
        testgen_id=str(test_case.id), title="Wersja TMS", updated_at=NOW - timedelta(hours=1)
    )

    outcome = await svc.run_pull_sync(db, state, {str(test_case.id): remote})

    assert outcome.conflicts == 1
    assert db.add.call_args[0][0].resolution is ConflictResolution.TESTGEN_WINS
    assert test_case.title == "Logowanie zwraca token"


@pytest.mark.asyncio
async def test_strategia_reczna_zostawia_konflikt_nierozstrzygniety():
    last = NOW - timedelta(hours=3)
    test_case = _test_case(updated_at=NOW - timedelta(hours=1))
    db = _db_with_test_cases(test_case)
    state = _state(last_sync_at=last, conflict_strategy=ConflictStrategy.MANUAL)
    remote = _remote(testgen_id=str(test_case.id), title="Wersja TMS", updated_at=NOW)

    outcome = await svc.run_pull_sync(db, state, {str(test_case.id): remote})

    assert outcome.conflicts == 1
    assert db.add.call_args[0][0].resolution is ConflictResolution.PENDING
    # Przypadek czeka na decyzję człowieka — nic nie zostało nadpisane.
    assert test_case.title == "Logowanie zwraca token"


@pytest.mark.asyncio
async def test_pusty_indeks_tms_konczy_przebieg_bez_pracy():
    db = _db_with_test_cases()

    outcome = await svc.run_pull_sync(db, _state(), {})

    assert outcome.as_dict()["pulled"] == 0
    db.execute.assert_not_called()


# ── przebieg push ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_push_wysyla_tylko_zmienione_przypadki():
    test_case = _test_case()
    db = _db_with_test_cases(test_case)
    exporter = AsyncMock()
    exporter.export.return_value = MagicMock(created=1, updated=0, failed=0, items=[])

    outcome = await svc.run_push_sync(db, _state(last_sync_at=NOW - timedelta(hours=2)), exporter)

    assert outcome.pushed == 1
    rows = exporter.export.call_args[0][0]
    assert rows[0]["title"] == "Logowanie zwraca token"


@pytest.mark.asyncio
async def test_push_bez_zmian_nie_woła_tms():
    db = _db_with_test_cases()
    exporter = AsyncMock()

    outcome = await svc.run_push_sync(db, _state(), exporter)

    assert outcome.pushed == 0
    exporter.export.assert_not_called()


@pytest.mark.asyncio
async def test_push_zapisuje_powiazanie_z_tms_na_przypadku():
    test_case = _test_case()
    db = _db_with_test_cases(test_case)
    exporter = AsyncMock()
    item = MagicMock(
        action="created", test_case_id=str(test_case.id), external_key=None, testrail_case_id=1234
    )
    exporter.export.return_value = MagicMock(created=1, updated=0, failed=0, items=[item])

    await svc.run_push_sync(db, _state(), exporter)

    # Bez tego lista przypadków nie miałaby skąd wziąć plakietki
    # „zsynchronizowany z TestRail #1234".
    assert test_case.tms_external_id == "1234"
    assert test_case.tms_synced_at is not None


def test_powiazanie_pomija_przypadki_ktore_sie_nie_udaly():
    test_case = _test_case()
    failed = MagicMock(action="failed", test_case_id=str(test_case.id), external_key="QA-1")

    assert svc.link_test_cases([test_case], [failed]) == 0
    assert test_case.tms_external_id is None


def test_powiazanie_uzywa_klucza_jiry_gdy_jest():
    test_case = _test_case()
    item = MagicMock(action="updated", test_case_id=str(test_case.id), external_key="QA-7")

    svc.link_test_cases([test_case], [item])

    assert test_case.tms_external_id == "QA-7"


@pytest.mark.asyncio
async def test_pull_odswieza_powiazanie_nawet_bez_zmian():
    test_case = _test_case()
    db = _db_with_test_cases(test_case)
    remote = _remote(testgen_id=str(test_case.id), external_id="99", title="")

    await svc.run_pull_sync(db, _state(last_sync_at=None), {str(test_case.id): remote})

    # Plakietka ma mówić „widzieliśmy się", a nie „coś przepisaliśmy".
    assert test_case.tms_external_id == "99"
    assert test_case.tms_synced_at is not None


@pytest.mark.asyncio
async def test_push_raportuje_nieudane_przypadki():
    db = _db_with_test_cases(_test_case())
    exporter = AsyncMock()
    failed_item = MagicMock(action="failed", title="Zły przypadek", error="400 Bad Request")
    exporter.export.return_value = MagicMock(created=0, updated=0, failed=1, items=[failed_item])

    outcome = await svc.run_push_sync(db, _state(), exporter)

    assert outcome.failed == 1
    assert "400 Bad Request" in outcome.errors[0]


# ── konfiguracja i rozstrzyganie ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_odstep_ponizej_pieciu_minut_jest_odrzucany():
    db = AsyncMock()

    with pytest.raises(ValidationError, match="5 min"):
        await svc.configure_sync(
            db,
            uuid.uuid4(),
            uuid.uuid4(),
            direction=SyncDirection.PULL,
            interval_minutes=4,
            conflict_strategy=ConflictStrategy.MANUAL,
        )


@pytest.mark.asyncio
async def test_rozstrzygniecie_nie_moze_cofnac_konfliktu_do_oczekujacego():
    with pytest.raises(ValidationError):
        await svc.resolve_conflict(
            AsyncMock(), uuid.uuid4(), uuid.uuid4(), ConflictResolution.PENDING, uuid.uuid4()
        )


def test_kierunek_wyznacza_wykonywane_etapy():
    assert _state(direction=SyncDirection.PUSH).pushes is True
    assert _state(direction=SyncDirection.PUSH).pulls is False
    assert _state(direction=SyncDirection.PULL).pushes is False
    assert _state(direction=SyncDirection.BIDIRECTIONAL).pulls is True
