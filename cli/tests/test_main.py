"""Warstwa Typer: opcje globalne, kody wyjścia, logowanie — Story 8.10 (AC1, AC5, AC6)."""

import json

import pytest

from testgen import main as main_module
from testgen.errors import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK
from tests.conftest import FakeClient


@pytest.fixture(autouse=True)
def izolowane_srodowisko(tmp_path, monkeypatch):
    """Testy nie mogą czytać konfiguracji ani poświadczeń uruchamiającego."""
    monkeypatch.setattr("testgen.config.USER_CONFIG_PATH", tmp_path / "user.yaml")
    monkeypatch.setattr("testgen.auth.AUTH_PATH", tmp_path / "auth")
    for name in ("TESTGEN_API_KEY", "TESTGEN_API_URL", "TESTGEN_PROJECT_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


def _run(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr("sys.argv", ["testgen", *argv])
    return main_module.run()


def test_version_konczy_sie_zerem(monkeypatch, capsys):
    assert _run(monkeypatch, ["--version"]) == EXIT_OK
    assert "testgen" in capsys.readouterr().out


def test_brak_poswiadczen_daje_kod_2(monkeypatch, capsys):
    code = _run(monkeypatch, ["--project-id", "p1", "whoami"])

    assert code == EXIT_ERROR
    assert "Brak poświadczeń" in capsys.readouterr().err


def test_dwa_formaty_naraz_sa_bledem(monkeypatch):
    assert _run(monkeypatch, ["--json", "--yaml", "whoami"]) == EXIT_ERROR


def test_zly_prog_w_konfiguracji_daje_kod_2(monkeypatch, tmp_path, capsys):
    (tmp_path / ".testgen.yaml").write_text("severity_threshold: wszystko\n", encoding="utf-8")

    code = _run(monkeypatch, ["--api-key", "tgn_x", "--project-id", "p1", "whoami"])

    assert code == EXIT_ERROR
    assert "Nieprawidłowy próg" in capsys.readouterr().err


def test_whoami_wypisuje_tozsamosc(monkeypatch, capsys):
    client = FakeClient(whoami={"email": "dev@example.pl", "id": "u1", "tenant_id": "t1"})
    monkeypatch.setattr(main_module.Context, "client", property(lambda self: client))

    code = _run(monkeypatch, ["--json", "--api-key", "tgn_x", "whoami"])

    assert code == EXIT_OK
    assert json.loads(capsys.readouterr().out)["email"] == "dev@example.pl"


def test_logout_bez_poswiadczen_konczy_sie_zerem(monkeypatch):
    assert _run(monkeypatch, ["logout"]) == EXIT_OK


def test_login_kluczem_zapisuje_poswiadczenia(monkeypatch, tmp_path):
    client = FakeClient(whoami={"email": "dev@example.pl", "id": "u1", "tenant_id": "t1"})
    monkeypatch.setattr(main_module, "TestGENClient", lambda *a, **k: client)
    monkeypatch.setattr("testgen.commands.login.TestGENClient", lambda *a, **k: client)

    code = _run(monkeypatch, ["--quiet", "login", "--api-key", "tgn_nowy"])

    assert code == EXIT_OK
    assert json.loads((tmp_path / "auth").read_text())["token"] == "tgn_nowy"


def test_login_nie_zapisuje_odrzuconego_klucza(monkeypatch, tmp_path):
    from testgen.errors import AuthError

    class Odrzucajacy:
        def whoami(self):
            raise AuthError("Serwer odrzucił poświadczenia")

    monkeypatch.setattr("testgen.commands.login.TestGENClient", lambda *a, **k: Odrzucajacy())

    code = _run(monkeypatch, ["login", "--api-key", "tgn_zly"])

    assert code == EXIT_ERROR
    assert not (tmp_path / "auth").exists()


def test_przekroczony_prog_daje_kod_1(monkeypatch, tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print(1)", encoding="utf-8")
    client = FakeClient(
        summary={
            "threshold": "critical",
            "counts": {"critical": 3},
            "total": 3,
            "blocking": 3,
            "should_fail": True,
            "description": "3 znaleziska krytyczne",
        }
    )
    monkeypatch.setattr(main_module.Context, "client", property(lambda self: client))

    code = _run(
        monkeypatch,
        ["--quiet", "--api-key", "tgn_x", "--project-id", "p1", "analyze", ".", "--wait"],
    )

    assert code == EXIT_FINDINGS


def test_analyze_bez_projektu_daje_kod_2(monkeypatch, capsys):
    client = FakeClient()
    monkeypatch.setattr(main_module.Context, "client", property(lambda self: client))

    code = _run(monkeypatch, ["--api-key", "tgn_x", "analyze", "."])

    assert code == EXIT_ERROR
    assert "Nie wskazano projektu" in capsys.readouterr().err


def test_engine_mode_z_argumentu_trafia_do_zadania(monkeypatch, tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print(1)", encoding="utf-8")
    client = FakeClient()
    monkeypatch.setattr(main_module.Context, "client", property(lambda self: client))

    code = _run(
        monkeypatch,
        ["--quiet", "--api-key", "tgn_x", "--project-id", "p1", "analyze", ".", "--engine-mode", "llm"],
    )

    assert code == EXIT_OK
    assert client.named("start_analysis")[0][2]["engine_mode"] == "llm"


def test_nieznana_komenda_daje_kod_2(monkeypatch):
    assert _run(monkeypatch, ["czaruj"]) == EXIT_ERROR
