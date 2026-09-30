"""Ścieżka end-to-end: login → analyze → generate → export — Story 8.10 (Task 7.5).

Test przechodzi przez prawdziwą warstwę Typer i prawdziwą konfigurację;
podstawiony jest wyłącznie klient HTTP, bo serwera TestGEN w testach nie ma.
"""

import json

import pytest

from testgen import main as main_module
from testgen.errors import EXIT_OK
from tests.conftest import FakeClient

PROJECT_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr("testgen.config.USER_CONFIG_PATH", tmp_path / "user.yaml")
    monkeypatch.setattr("testgen.auth.AUTH_PATH", tmp_path / "auth")
    for name in ("TESTGEN_API_KEY", "TESTGEN_API_URL", "TESTGEN_PROJECT_ID"):
        monkeypatch.delenv(name, raising=False)

    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "main.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / ".testgen.yaml").write_text(
        f"project_id: {PROJECT_ID}\nengine_mode: native\ndefault_framework: pytest\n"
        "severity_threshold: critical\napi_url: https://api.example.test\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    return repo


def _run(monkeypatch, argv: list[str]) -> int:
    monkeypatch.setattr("sys.argv", ["testgen", *argv])
    return main_module.run()


def test_pelna_sciezka_dewelopera(workspace, monkeypatch, capsys):
    client = FakeClient(
        whoami={"email": "dev@example.pl", "id": "u1", "tenant_id": "t1", "name": "Deweloper"},
        list_test_cases={
            "items": [
                {
                    "id": "aaaaaaaa-0000-0000-0000-000000000000",
                    "title": "Dodawanie zwraca sumę",
                    "language": "python",
                    "imports": "import pytest",
                    "test_code": "def test_add():\n    assert add(2, 2) == 4",
                }
            ]
        },
    )
    monkeypatch.setattr("testgen.commands.login.TestGENClient", lambda *a, **k: client)
    monkeypatch.setattr(main_module.Context, "client", property(lambda self: client))

    # 1. Logowanie kluczem API — poświadczenia lądują na dysku.
    assert _run(monkeypatch, ["--quiet", "login", "--api-key", "tgn_e2e"]) == EXIT_OK
    capsys.readouterr()

    # 2. Analiza z czekaniem — konfiguracja czytana z .testgen.yaml.
    assert _run(monkeypatch, ["--json", "analyze", ".", "--wait"]) == EXIT_OK
    analiza = json.loads(capsys.readouterr().out)
    assert analiza["project_id"] == PROJECT_ID
    assert analiza["summary"]["should_fail"] is False

    # 3. Generowanie testów na dysk.
    assert _run(monkeypatch, ["--json", "generate", "--output-dir", "wygenerowane"]) == EXIT_OK
    generacja = json.loads(capsys.readouterr().out)
    assert generacja["files_written"] == 1
    assert (workspace / "wygenerowane").is_dir()

    # 4. Eksport raportu do pliku.
    assert _run(monkeypatch, ["--json", "export", "--format", "pdf", "-o", "raport.pdf"]) == EXIT_OK
    eksport = json.loads(capsys.readouterr().out)
    assert eksport["format"] == "pdf"
    assert (workspace / "raport.pdf").exists()

    # Framework wzięty z .testgen.yaml, nie z argumentu.
    assert client.named("list_test_cases")[0][2]["framework"] == "pytest"


def test_bez_logowania_kazda_komenda_konczy_sie_kodem_2(workspace, monkeypatch):
    from testgen.errors import EXIT_ERROR

    for argv in (["whoami"], ["analyze", "."], ["generate"], ["export"], ["scan"]):
        assert _run(monkeypatch, argv) == EXIT_ERROR
