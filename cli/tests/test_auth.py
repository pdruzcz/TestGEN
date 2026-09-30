"""Przechowywanie poświadczeń — Story 8.10 (AC1)."""

import json
import stat

import pytest

from testgen import auth
from testgen.errors import AuthError, CliError


@pytest.fixture(autouse=True)
def auth_path(tmp_path, monkeypatch):
    path = tmp_path / ".testgen" / "auth"
    monkeypatch.setattr(auth, "AUTH_PATH", path)
    return path


def test_zapis_ustawia_prawa_600(auth_path):
    auth.save_credentials("tgn_abc", api_url="https://api.example")

    mode = stat.S_IMODE(auth_path.stat().st_mode)
    assert mode == 0o600
    assert json.loads(auth_path.read_text())["token"] == "tgn_abc"


def test_odczyt_zwraca_zapisane_dane(auth_path):
    auth.save_credentials("tgn_abc", api_url="https://api.example", kind="api_key")

    stored = auth.load_credentials()

    assert stored["token"] == "tgn_abc"
    assert stored["kind"] == "api_key"


def test_brak_pliku_to_brak_danych():
    assert auth.load_credentials() is None


def test_uszkodzony_plik_daje_czytelny_blad(auth_path):
    auth_path.parent.mkdir(parents=True)
    auth_path.write_text("to nie jest json")

    with pytest.raises(CliError, match="uszkodzony"):
        auth.load_credentials()


def test_logout_zwraca_false_gdy_nie_bylo_poswiadczen():
    assert auth.clear_credentials() is False


def test_logout_usuwa_plik(auth_path):
    auth.save_credentials("tgn_abc", api_url="https://api.example")

    assert auth.clear_credentials() is True
    assert not auth_path.exists()


def test_klucz_z_konfiguracji_wygrywa_z_zapisanym(auth_path):
    auth.save_credentials("tgn_zapisany", api_url="https://api.example")

    assert auth.resolve_token("tgn_z_konfiguracji") == "tgn_z_konfiguracji"


def test_brak_poswiadczen_daje_blad_autoryzacji():
    with pytest.raises(AuthError, match="Brak poświadczeń"):
        auth.resolve_token(None)
