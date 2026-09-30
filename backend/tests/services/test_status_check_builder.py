"""Testy budowania status checków — Story 8.3 (AC1, AC3, AC5; Task 7.1).

Moduł jest czysty, więc testy nie potrzebują ani bazy, ani sieci. Nacisk
idzie na decyzję „przepuścić czy zablokować merge" — to ona wstrzymuje
ludziom pracę, więc musi być jednoznaczna na każdej granicy progu.
"""

import pytest

from app.services.integrations.status_check_builder import (
    ALLOWED_THRESHOLDS,
    DEFAULT_THRESHOLD,
    SEVERITY_ORDER,
    STATUS_CONTEXT,
    AnalysisOutcome,
    FindingSummary,
    build_pr_comment,
    build_status_description,
    normalize_threshold,
    outcome_from_rows,
    severity_rank,
)

REPORT_URL = "https://app.testgen.io/projects/abc/results"


class _Row:
    """Minimalny zastępnik wiersza ORM — builder czyta tylko atrybuty."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _outcome(counts: dict[str, int], **kwargs) -> AnalysisOutcome:
    return AnalysisOutcome(counts=counts, **kwargs)


# ── skala wag ────────────────────────────────────────────────────────────────


def test_skala_wag_rosnie_od_info_do_critical():
    assert SEVERITY_ORDER == ("info", "low", "medium", "high", "critical")
    assert severity_rank("critical") > severity_rank("high") > severity_rank("medium")
    assert severity_rank("medium") > severity_rank("low") > severity_rank("info")


def test_nieznana_waga_traktowana_najlagodniej():
    """Nieznana wartość nie może przypadkiem zablokować merge'a."""
    assert severity_rank("wymyslona") == 0
    assert severity_rank("") == 0
    assert severity_rank(None) == 0


def test_normalize_threshold_przepuszcza_tylko_dozwolone():
    for value in ALLOWED_THRESHOLDS:
        assert normalize_threshold(value) == value
    assert normalize_threshold("CRITICAL") == "critical"


@pytest.mark.parametrize("bad", [None, "", "low", "info", "cokolwiek"])
def test_normalize_threshold_spada_na_domyslny(bad):
    assert normalize_threshold(bad) == DEFAULT_THRESHOLD


def test_count_at_or_above_liczy_od_progu_w_gore():
    outcome = _outcome({"critical": 1, "high": 2, "medium": 3, "low": 4})

    assert outcome.count_at_or_above("critical") == 1
    assert outcome.count_at_or_above("high") == 3
    assert outcome.count_at_or_above("medium") == 6
    assert outcome.total == 10


# ── decyzja success/failure (AC3) ────────────────────────────────────────────


def test_brak_znalezisk_to_sukces():
    state, description = build_status_description(_outcome({}))

    assert state == "success"
    assert description == "Analiza zakończona — brak problemów krytycznych"


def test_znalezisko_na_progu_blokuje():
    state, description = build_status_description(_outcome({"critical": 1}), "critical")

    assert state == "failure"
    assert "1 krytyczny" in description


def test_znaleziska_ponizej_progu_nie_blokuja():
    state, description = build_status_description(_outcome({"high": 5, "medium": 9}), "critical")

    assert state == "success"
    assert "powyżej progu" in description
    assert "14" in description  # pozostałe znaleziska nadal widoczne


def test_prog_high_lapie_takze_critical():
    """Próg jest granicą dolną — „co najmniej tak poważne"."""
    state, description = build_status_description(_outcome({"critical": 2, "high": 1}), "high")

    assert state == "failure"
    assert "2 krytyczne" in description
    assert "1 wysoki" in description


def test_prog_medium_lapie_wszystko_powyzej():
    state, _ = build_status_description(_outcome({"medium": 1}), "medium")
    assert state == "failure"


def test_fail_on_threshold_false_zostawia_zielony_status():
    """Zespół chce widzieć liczby, ale nie blokować merge'a."""
    state, description = build_status_description(
        _outcome({"critical": 3}), "critical", fail_on_threshold=False
    )

    assert state == "success"
    assert "3 krytyczne" in description
    assert "nie blokuje" in description


def test_pipeline_failed_to_zawsze_failure():
    state, description = build_status_description(
        _outcome({}, pipeline_status="failed"), "critical"
    )

    assert state == "failure"
    assert "nie powiodła się" in description


def test_pipeline_partial_failure_bez_znalezisk_to_sukces_z_adnotacja():
    state, description = build_status_description(_outcome({}, pipeline_status="partial_failure"))

    assert state == "success"
    assert "częściowo" in description


@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "1 krytyczny"), (2, "2 krytyczne"), (5, "5 krytycznych"), (12, "12 krytycznych"), (22, "22 krytyczne")],
)
def test_polska_odmiana_liczebnikow(count, expected):
    _, description = build_status_description(_outcome({"critical": count}), "critical")
    assert expected in description


def test_opis_miesci_sie_w_limicie_githuba():
    """GitHub obcina description do 140 znaków — przycinamy sami, po słowie."""
    counts = {"critical": 123456, "high": 999999, "medium": 888888}
    _, description = build_status_description(counts and _outcome(counts), "medium")

    assert len(description) <= 140


def test_nazwa_kontekstu_jest_stala():
    """Zmiana zerwie skonfigurowane u klientów required status checks (AC4)."""
    assert STATUS_CONTEXT == "TestGEN / Code Analysis"


# ── komentarz na PR (AC5) ────────────────────────────────────────────────────


def test_komentarz_bez_znalezisk_jest_krotki_i_zawiera_link():
    body = build_pr_comment(_outcome({}), REPORT_URL)

    assert body.startswith("## Analiza TestGEN")
    assert "Nie znaleziono żadnych problemów" in body
    assert f"]({REPORT_URL})" in body


def test_komentarz_ma_tabele_z_podzialem_na_wagi():
    outcome = _outcome({"critical": 2, "medium": 1})
    body = build_pr_comment(outcome, REPORT_URL, threshold="critical")

    assert "| Waga | Liczba |" in body
    assert "| Krytyczne | 2 |" in body
    assert "| Średnie | 1 |" in body
    # Wagi bez znalezisk nie zaśmiecają tabeli
    assert "Wysokie" not in body


def test_komentarz_wymienia_trzy_najpowazniejsze_z_lokalizacja():
    outcome = AnalysisOutcome(
        counts={"critical": 1, "high": 1, "low": 1},
        top_findings=[
            FindingSummary("critical", "SQL Injection", "app/db.py", 42),
            FindingSummary("high", "XSS", "app/views.py", 7),
            FindingSummary("low", "Martwy kod", "app/util.py"),
        ],
    )

    body = build_pr_comment(outcome, REPORT_URL)

    assert "### Najpoważniejsze znaleziska" in body
    assert "`app/db.py`:42" in body
    assert "**[krytyczny]** SQL Injection" in body
    assert "`app/util.py`" in body  # bez linii — bez dwukropka
    assert "app/util.py`:" not in body


def test_komentarz_pokazuje_ze_prog_blokuje():
    body = build_pr_comment(_outcome({"critical": 2}), REPORT_URL, threshold="critical")

    assert "Próg blokujący: `critical`" in body
    assert "2 znaleziska" in body


def test_komentarz_informuje_gdy_prog_nieprzekroczony():
    body = build_pr_comment(_outcome({"low": 4}), REPORT_URL, threshold="critical")

    assert "Brak znalezisk na poziomie `critical`" in body


def test_komentarz_ogranicza_liste_do_trzech():
    outcome = AnalysisOutcome(
        counts={"critical": 5},
        top_findings=[FindingSummary("critical", f"Problem {i}") for i in range(5)],
    )

    body = build_pr_comment(outcome, REPORT_URL)

    assert body.count("**[krytyczny]**") == 3


# ── składanie wyniku z wierszy bazy ──────────────────────────────────────────


def test_outcome_z_findings_bezpieczenstwa():
    rows = [
        _Row(severity="critical", vulnerability_type="SQL Injection", file_path="db.py", line_start=10),
        _Row(severity="high", vulnerability_type="XSS", file_path="v.py", line_start=3),
    ]

    outcome = outcome_from_rows(rows, [])

    assert outcome.counts == {"critical": 1, "high": 1}
    assert outcome.top_findings[0].title == "SQL Injection"
    assert outcome.top_findings[0].line == 10


def test_bledy_kodu_sprowadzone_na_wspolna_skale():
    """CodeError ma trzy stopnie; jeden próg musi rządzić całym status checkiem."""
    rows = [
        _Row(severity="critical", message="Błąd składni", file_path="a.py", line_start=1),
        _Row(severity="warning", message="Podejrzana konstrukcja", file_path="b.py", line_start=2),
        _Row(severity="info", message="Drobiazg", file_path="c.py", line_start=3),
    ]

    outcome = outcome_from_rows([], rows)

    assert outcome.counts == {"critical": 1, "high": 1, "low": 1}


def test_nieznana_waga_bledu_kodu_ladnie_na_dol():
    outcome = outcome_from_rows([], [_Row(severity="dziwna", message="X")])
    assert outcome.counts == {"low": 1}


def test_najpowazniejsze_sortowane_malejaco_po_wadze():
    security = [_Row(severity="low", vulnerability_type="Drobiazg", file_path="a", line_start=1)]
    errors = [_Row(severity="critical", message="Krytyczny", file_path="b", line_start=2)]

    outcome = outcome_from_rows(security, errors)

    assert outcome.top_findings[0].severity == "critical"
    assert outcome.top_findings[-1].severity == "low"


def test_outcome_laczy_oba_zrodla_i_niesie_status_pipeline():
    outcome = outcome_from_rows(
        [_Row(severity="high", vulnerability_type="X", file_path=None, line_start=None)],
        [_Row(severity="critical", message="Y", file_path=None, line_start=None)],
        pipeline_status="partial_failure",
    )

    assert outcome.total == 2
    assert outcome.pipeline_status == "partial_failure"


def test_pusty_wynik_nie_wywraca_buildera():
    outcome = outcome_from_rows([], [])

    assert outcome.total == 0
    assert outcome.top_findings == []
    assert build_status_description(outcome)[0] == "success"
