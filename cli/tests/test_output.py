"""Formaty wyjścia i kody wyjścia — Story 8.10 (AC5)."""

import json

import pytest
import yaml

from testgen.errors import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, CliError, ThresholdExceeded
from testgen.output import OutputFormat, Printer, findings_table


def test_json_jest_parsowalny(capsys):
    Printer(fmt=OutputFormat.JSON).result({"total": 3, "should_fail": True})

    parsed = json.loads(capsys.readouterr().out)

    assert parsed == {"total": 3, "should_fail": True}


def test_yaml_jest_parsowalny(capsys):
    Printer(fmt=OutputFormat.YAML).result({"prog": "critical", "znaleziska": [1, 2]})

    parsed = yaml.safe_load(capsys.readouterr().out)

    assert parsed == {"prog": "critical", "znaleziska": [1, 2]}


def test_quiet_nic_nie_wypisuje(capsys):
    printer = Printer(fmt=OutputFormat.JSON, quiet=True)
    printer.result({"a": 1})
    printer.info("postęp")
    printer.success("gotowe")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_komunikaty_pomocnicze_ida_na_stderr(capsys):
    printer = Printer(fmt=OutputFormat.HUMAN)
    printer.info("pakuję")
    printer.result({"a": 1})

    captured = capsys.readouterr()
    assert "pakuję" in captured.err
    assert "pakuję" not in captured.out


def test_tryb_maszynowy_nie_zaklóca_strumienia(capsys):
    printer = Printer(fmt=OutputFormat.JSON)
    printer.info("pakuję")
    printer.success("gotowe")
    printer.result({"a": 1})

    captured = capsys.readouterr()
    # Wynik na stdout musi zostać czystym JSON-em, żeby dało się go przepuścić
    # przez `jq` — diagnostyka nie może go zanieczyścić.
    assert json.loads(captured.out) == {"a": 1}
    assert captured.err == ""


def test_blad_zawsze_trafia_na_stderr_mimo_quiet(capsys):
    Printer(quiet=True).error("coś poszło nie tak", "sprawdź klucz")

    captured = capsys.readouterr()
    assert "coś poszło nie tak" in captured.err
    assert captured.out == ""


def test_tabela_znalezisk_pomija_zerowe_wagi():
    table = findings_table({"critical": 2, "high": 0, "low": 5})

    assert table.row_count == 2


def test_tabela_pokazuje_brak_znalezisk():
    assert findings_table({}).row_count == 1


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (ThresholdExceeded("2 krytyczne"), EXIT_FINDINGS),
        (CliError("brak klucza"), EXIT_ERROR),
    ],
)
def test_kody_wyjscia_rozroznia_znaleziska_od_awarii(exc, expected):
    assert exc.exit_code == expected


def test_sukces_ma_kod_zero():
    assert EXIT_OK == 0
