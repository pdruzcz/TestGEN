"""Klient API i pakowanie kodu — Story 8.10 (AC2, AC6)."""

import httpx
import pytest

from testgen.client import DEFAULT_EXCLUDES, build_archive, iter_source_files

# Alias, bo pytest próbowałby zbierać `TestGENClient` jako klasę testową.
from testgen.client import TestGENClient as ApiClient
from testgen.errors import AuthError, CliError, ConnectionFailed


def test_brak_polaczenia_daje_komunikat_z_ac6(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("sieć niedostępna")

    client = ApiClient("https://api.example", "tgn_test")
    monkeypatch.setattr(httpx.Client, "request", boom)

    with pytest.raises(ConnectionFailed) as excinfo:
        client.whoami()

    assert "Brak połączenia z serwerem TestGEN" in excinfo.value.message


def test_timeout_jest_zglaszany_jako_brak_polaczenia(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ReadTimeout("za wolno")

    client = ApiClient("https://api.example", "tgn_test", timeout=5)
    monkeypatch.setattr(httpx.Client, "request", boom)

    with pytest.raises(ConnectionFailed) as excinfo:
        client.whoami()

    assert "5 s" in (excinfo.value.hint or "")


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(401, AuthError), (403, CliError), (404, CliError), (429, CliError), (500, CliError)],
)
def test_kody_bledow_maja_wlasne_komunikaty(monkeypatch, status_code, expected):
    def responder(*args, **kwargs):
        return httpx.Response(status_code, json={"detail": "coś poszło nie tak"})

    client = ApiClient("https://api.example", "tgn_test")
    monkeypatch.setattr(httpx.Client, "request", responder)

    with pytest.raises(expected):
        client.whoami()


def test_token_trafia_do_naglowka(monkeypatch):
    zapisane = {}

    def responder(self, method, url, **kwargs):
        zapisane.update(kwargs.get("headers") or {})
        return httpx.Response(200, json={"email": "a@b.pl"})

    monkeypatch.setattr(httpx.Client, "request", responder)
    ApiClient("https://api.example", "tgn_test").whoami()

    assert zapisane["Authorization"] == "Bearer tgn_test"


def test_pakowanie_pomija_katalogi_z_listy(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print(1)")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "big.js").write_text("x")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref")

    files = [p.name for p in iter_source_files(tmp_path, DEFAULT_EXCLUDES)]

    assert files == ["main.py"]


def test_archiwum_zawiera_sciezki_wzgledne(tmp_path):
    source = tmp_path / "projekt"
    (source / "pkg").mkdir(parents=True)
    (source / "pkg" / "kod.py").write_text("x = 1")
    archive = tmp_path / "out.zip"

    count = build_archive(source, archive, DEFAULT_EXCLUDES)

    import zipfile

    with zipfile.ZipFile(archive) as zf:
        assert zf.namelist() == ["pkg/kod.py"]
    assert count == 1


def test_pusty_katalog_jest_bledem(tmp_path):
    with pytest.raises(CliError):
        build_archive(tmp_path, tmp_path.parent / "pusty.zip", DEFAULT_EXCLUDES)
