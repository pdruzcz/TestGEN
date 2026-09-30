"""Konfiguracja i jej pierwszeństwo — Story 8.10 (AC4)."""

import pytest

from testgen.config import Config, find_project_config, load_config
from testgen.errors import CliError


def _write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_czyta_plik_projektu(tmp_path, monkeypatch):
    monkeypatch.setattr("testgen.config.USER_CONFIG_PATH", tmp_path / "brak.yaml")
    _write(
        tmp_path / ".testgen.yaml",
        "project_id: abc\nengine_mode: llm\nseverity_threshold: high\n",
    )

    config = load_config(start=tmp_path)

    assert config.project_id == "abc"
    assert config.engine_mode == "llm"
    assert config.severity_threshold == "high"


def test_argumenty_wygrywaja_z_plikiem(tmp_path, monkeypatch):
    monkeypatch.setattr("testgen.config.USER_CONFIG_PATH", tmp_path / "brak.yaml")
    _write(tmp_path / ".testgen.yaml", "project_id: z-pliku\n")

    config = load_config(start=tmp_path, project_id="z-argumentu")

    assert config.project_id == "z-argumentu"


def test_zmienna_srodowiskowa_wygrywa_z_plikiem(tmp_path, monkeypatch):
    monkeypatch.setattr("testgen.config.USER_CONFIG_PATH", tmp_path / "brak.yaml")
    monkeypatch.setenv("TESTGEN_API_KEY", "tgn_ze_srodowiska")
    _write(tmp_path / ".testgen.yaml", "api_key: tgn_z_pliku\n")

    config = load_config(start=tmp_path)

    assert config.api_key == "tgn_ze_srodowiska"


def test_plik_projektu_wygrywa_z_globalnym(tmp_path, monkeypatch):
    user_config = tmp_path / "user.yaml"
    _write(user_config, "api_url: https://globalny.example\nengine_mode: hybrid\n")
    monkeypatch.setattr("testgen.config.USER_CONFIG_PATH", user_config)
    _write(tmp_path / ".testgen.yaml", "api_url: https://projekt.example\n")

    config = load_config(start=tmp_path)

    assert config.api_url == "https://projekt.example"
    # Wartość niepodana w projekcie zostaje z konfiguracji globalnej.
    assert config.engine_mode == "hybrid"


def test_szuka_konfiguracji_w_katalogach_nadrzednych(tmp_path):
    _write(tmp_path / ".testgen.yaml", "project_id: korzen\n")
    nested = tmp_path / "src" / "moduł"
    nested.mkdir(parents=True)

    assert find_project_config(nested) == tmp_path / ".testgen.yaml"


def test_nieznane_klucze_sa_pomijane(tmp_path, monkeypatch):
    monkeypatch.setattr("testgen.config.USER_CONFIG_PATH", tmp_path / "brak.yaml")
    _write(tmp_path / ".testgen.yaml", "project_id: abc\nnieistniejace_pole: 5\n")

    assert load_config(start=tmp_path).project_id == "abc"


def test_odrzuca_zly_tryb_silnika():
    with pytest.raises(CliError):
        Config(engine_mode="magiczny").validate()


def test_odrzuca_zly_prog():
    with pytest.raises(CliError):
        Config(severity_threshold="wszystko").validate()


def test_brak_projektu_daje_czytelny_blad():
    with pytest.raises(CliError, match="Nie wskazano projektu"):
        Config().validate().require_project_id()
