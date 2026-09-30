"""Konwersja Jira → wymagania TestGEN — Story 8.12 (Task 6.1, 6.2).

Wszystkie funkcje w tym module są czyste, więc testujemy je wprost, bez
atrapy Jiry.
"""

from datetime import UTC, datetime

import pytest

from app.services.integrations import jira_import_service as svc
from app.services.integrations.jira_service import JiraIssue, parse_issue

NOW = datetime(2026, 9, 25, 12, 30, tzinfo=UTC)


def _issue(**overrides) -> JiraIssue:
    defaults = {
        "key": "QA-1",
        "issue_type": "Story",
        "summary": "Użytkownik loguje się e-mailem",
        "description": "",
        "priority": "High",
        "labels": ["logowanie"],
        "status": "To Do",
        "updated": "2026-09-25T10:00:00.000+0000",
        "epic_key": None,
        "parent_key": None,
        "attachments": [],
    }
    defaults.update(overrides)
    return JiraIssue(**defaults)


# ── JQL ─────────────────────────────────────────────────────────────────────


def test_jql_zawiera_projekt_i_typy():
    jql = svc.build_jql("QA", ["Story", "Epic"], None)

    assert 'project = "QA"' in jql
    assert 'issuetype in ("Story", "Epic")' in jql
    assert "updated >=" not in jql


def test_jql_przyrostowy_dodaje_date_bez_strefy():
    # JQL nie przyjmuje ISO 8601 ze strefą — Jira czyta datę w strefie instancji.
    jql = svc.build_jql("QA", ["Story"], NOW)

    assert 'updated >= "2026-09-25 12:30"' in jql
    assert "+00:00" not in jql


def test_jql_bez_typow_nie_filtruje_po_typie():
    assert "issuetype" not in svc.build_jql("QA", [], None)


def test_jql_bez_projektu_jest_bledem():
    with pytest.raises(ValueError):
        svc.build_jql("", ["Story"], None)


def test_jql_sortuje_rosnaco_po_dacie_zmiany():
    # Rosnąco, bo przy przerwanym imporcie starsze zgłoszenia trafiają
    # do bazy jako pierwsze i to one nie wymagają ponownego pobrania.
    assert svc.build_jql("QA", [], None).endswith("ORDER BY updated ASC")


# ── kryteria akceptacji ─────────────────────────────────────────────────────


def test_kryteria_z_naglowka_angielskiego():
    description = (
        "Opis historyjki.\n\n"
        "h2. Acceptance Criteria\n"
        "* System przyjmuje e-mail\n"
        "* System odrzuca puste hasło\n"
    )

    assert svc.parse_acceptance_criteria(description) == [
        "System przyjmuje e-mail",
        "System odrzuca puste hasło",
    ]


def test_kryteria_z_naglowka_polskiego():
    description = "h3. Kryteria akceptacji\n- Pierwsze\n- Drugie\n"

    assert svc.parse_acceptance_criteria(description) == ["Pierwsze", "Drugie"]


def test_kryteria_koncza_sie_na_kolejnym_naglowku():
    description = (
        "h2. Acceptance Criteria\n* Pierwsze\n\nh2. Uwagi\n* To już nie jest kryterium\n"
    )

    assert svc.parse_acceptance_criteria(description) == ["Pierwsze"]


def test_brak_sekcji_daje_pusta_liste():
    assert svc.parse_acceptance_criteria("Zwykły opis bez sekcji.") == []


def test_pusty_opis_nie_wysadza_parsera():
    assert svc.parse_acceptance_criteria("") == []


def test_kryteria_zachowuja_znaczniki_inline_jako_markdown():
    assert svc.parse_acceptance_criteria("h2. AC\n* Pole {{email}} jest wymagane\n") == [
        "Pole `email` jest wymagane"
    ]


# ── konwersja opisu ─────────────────────────────────────────────────────────


def test_naglowki_wiki_staja_sie_naglowkami_markdown():
    assert svc.wiki_to_markdown("h2. Tytuł") == "## Tytuł"


def test_listy_zachowuja_zagniezdzenie():
    assert svc.wiki_to_markdown("* Pierwszy\n** Zagnieżdżony") == "- Pierwszy\n  - Zagnieżdżony"


def test_pogrubienie_i_kod_sa_tlumaczone():
    assert svc.wiki_to_markdown("To jest *ważne* i {{kod}}") == "To jest **ważne** i `kod`"


def test_odnosnik_wiki_staje_sie_odnosnikiem_markdown():
    assert svc.wiki_to_markdown("[dokumentacja|https://example.test]") == (
        "[dokumentacja](https://example.test)"
    )


def test_pusty_opis_daje_pusty_markdown():
    assert svc.wiki_to_markdown("") == ""


# ── mapowanie pól ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("issue_type", "expected"),
    [("Story", "functional"), ("Epic", "functional"), ("Bug", "negative"), ("Sub-task", "functional")],
)
def test_typ_zgloszenia_wyznacza_typ_wymagania(issue_type, expected):
    assert svc.requirement_type_for(issue_type) == expected


def test_nieznany_typ_traktujemy_jak_funkcjonalny():
    assert svc.requirement_type_for("Spike") == "functional"


@pytest.mark.parametrize(
    ("jira", "expected"),
    [("Highest", "critical"), ("Blocker", "critical"), ("High", "high"), ("Low", "low")],
)
def test_priorytet_jest_mapowany(jira, expected):
    assert svc.priority_for(jira) == expected


def test_brak_priorytetu_daje_sredni():
    assert svc.priority_for(None) == "medium"


def test_epik_jest_wlasnym_modulem():
    # Inaczej epik i jego historyjki trafiłyby do dwóch różnych grup.
    assert svc.module_for(_issue(key="QA-10", issue_type="Epic")) == "QA-10"


def test_historyjka_nalezy_do_modulu_swojego_epiku():
    assert svc.module_for(_issue(epic_key="QA-10")) == "QA-10"


def test_historyjka_bez_epiku_trafia_do_grupy_zbiorczej():
    assert svc.module_for(_issue()) == "(bez epiku)"


# ── konwersja zgłoszenia ────────────────────────────────────────────────────


def test_konwersja_przenosi_pola_zgloszenia():
    issue = _issue(
        description="Opis.\n\nh2. Acceptance Criteria\n* Kryterium\n",
        labels=["logowanie", "mvp"],
    )

    requirement = svc.convert_issue(issue)

    assert requirement["req_id"] == "QA-1"
    assert requirement["jira_key"] == "QA-1"
    assert requirement["text"] == "Użytkownik loguje się e-mailem"
    assert requirement["type"] == "functional"
    assert requirement["priority"] == "high"
    assert requirement["criteria"] == ["Kryterium"]
    assert requirement["tags"] == ["logowanie", "mvp"]
    assert requirement["extraction_method"] == "jira_import"
    # Wymaganie zostało przepisane z systemu, a nie wywnioskowane z tekstu.
    assert requirement["confidence"] == 1.0


def test_zgloszenie_bez_klucza_jest_bledem():
    with pytest.raises(ValueError):
        svc.convert_issue(_issue(key=""))


def test_zgloszenie_bez_streszczenia_uzywa_klucza_jako_tytulu():
    assert svc.convert_issue(_issue(summary=""))["text"] == "QA-1"


def test_konwersja_zbiorcza_pomija_zle_zgloszenia():
    outcome = svc.convert_all([_issue(), _issue(key="")])

    assert len(outcome.requirements) == 1
    assert outcome.skipped == 1
    assert outcome.errors


# ── import przyrostowy ──────────────────────────────────────────────────────


def test_scalanie_aktualizuje_istniejace_wymaganie():
    existing = [{"jira_key": "QA-1", "text": "Stara treść", "status": "accepted"}]
    imported = [{"jira_key": "QA-1", "text": "Nowa treść", "status": "extracted"}]

    merged = svc.merge_requirements(existing, imported)

    assert len(merged) == 1
    assert merged[0]["text"] == "Nowa treść"
    # Import nie może cofnąć decyzji, którą ktoś świadomie podjął.
    assert merged[0]["status"] == "accepted"


def test_scalanie_dopisuje_nowe_wymagania_na_koncu():
    merged = svc.merge_requirements(
        [{"jira_key": "QA-1", "text": "Pierwsze"}],
        [{"jira_key": "QA-2", "text": "Drugie"}],
    )

    assert [m["jira_key"] for m in merged] == ["QA-1", "QA-2"]


def test_scalanie_pomija_wpisy_bez_klucza():
    assert svc.merge_requirements([], [{"text": "Bez klucza"}]) == []


# ── załączniki i dokument ───────────────────────────────────────────────────


def test_zalaczniki_niosą_klucz_swojego_zgloszenia():
    issue = _issue(attachments=[{"id": "7", "filename": "diagram.png"}])

    assert svc.attachments_of([issue]) == [("QA-1", {"id": "7", "filename": "diagram.png"})]


def test_dokument_zawiera_kryteria_i_tytuly():
    requirements = [svc.convert_issue(_issue(description="h2. AC\n* Kryterium\n"))]

    document = svc.render_document("QA", requirements)

    assert "# Wymagania zaimportowane z Jiry (QA)" in document
    assert "## QA-1 — Użytkownik loguje się e-mailem" in document
    assert "- Kryterium" in document


def test_sekcje_powstaja_po_jednej_na_wymaganie():
    payload = svc.sections_payload([svc.convert_issue(_issue())])

    assert payload["document_structure"]["sections_count"] == 1
    assert payload["sections"][0]["section_id"] == "QA-1"


def test_ladunek_wymagan_ma_ksztalt_z_epiku_drugiego():
    payload = svc.requirements_payload([{"req_id": "QA-1"}])

    # Ekrany wymagań czytają dokładnie ten klucz.
    assert payload["requirements"][0]["req_id"] == "QA-1"
    assert "imported_at" in payload


# ── parsowanie odpowiedzi Jiry ──────────────────────────────────────────────


def test_parsowanie_rozroznia_epik_od_zadania_nadrzednego():
    epic_child = parse_issue(
        {
            "key": "QA-2",
            "fields": {
                "summary": "Historyjka",
                "issuetype": {"name": "Story"},
                "parent": {"key": "QA-1", "fields": {"issuetype": {"name": "Epic"}}},
            },
        }
    )
    subtask = parse_issue(
        {
            "key": "QA-3",
            "fields": {
                "summary": "Podzadanie",
                "issuetype": {"name": "Sub-task"},
                "parent": {"key": "QA-2", "fields": {"issuetype": {"name": "Story"}}},
            },
        }
    )

    assert epic_child.epic_key == "QA-1"
    assert epic_child.parent_key is None
    assert subtask.parent_key == "QA-2"
    assert subtask.epic_key is None


def test_parsowanie_pomija_zalaczniki_bez_nazwy():
    issue = parse_issue(
        {
            "key": "QA-1",
            "fields": {
                "summary": "X",
                "issuetype": {"name": "Story"},
                "attachment": [
                    {"id": "1", "filename": "ok.png", "size": 10},
                    {"id": "2"},
                ],
            },
        }
    )

    assert len(issue.attachments) == 1
    assert issue.attachments[0]["filename"] == "ok.png"


def test_parsowanie_pustej_odpowiedzi_nie_wysadza():
    issue = parse_issue({})

    assert issue.key == ""
    assert issue.attachments == []
