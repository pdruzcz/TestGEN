"""Komendy CLI — Story 8.10 (AC2, AC3, AC5)."""

from pathlib import Path

import pytest

from testgen.commands import analyze as analyze_cmd
from testgen.commands import export as export_cmd
from testgen.commands import generate as generate_cmd
from testgen.commands import scan as scan_cmd
from testgen.commands import status as status_cmd
from testgen.errors import CliError, ThresholdExceeded
from tests.conftest import FakeClient


@pytest.fixture
def source_dir(tmp_path) -> Path:
    root = tmp_path / "projekt"
    (root / "app").mkdir(parents=True)
    (root / "app" / "main.py").write_text("print(1)", encoding="utf-8")
    return root


# ── analyze ─────────────────────────────────────────────────────────────────


def test_analyze_wysyla_kod_i_startuje_analize(config, printer, source_dir, no_sleep):
    client = FakeClient()

    result = analyze_cmd.run(
        client, config, printer, path=source_dir, modules=["security"], wait=False, sleep=no_sleep
    )

    assert result["task_id"] == "t1"
    assert client.named("upload_archive")
    start = client.named("start_analysis")[0]
    assert start[2]["modules"] == ["security"]
    assert start[2]["engine_mode"] == "native"
    # Bez --wait nie odpytujemy o status ani o werdykt.
    assert not client.named("task_status")
    assert not client.named("summary")


def test_analyze_bez_katalogu_konczy_sie_bledem(config, printer, tmp_path, no_sleep):
    with pytest.raises(CliError, match="nie istnieje"):
        analyze_cmd.run(
            FakeClient(),
            config,
            printer,
            path=tmp_path / "nie-ma",
            modules=[],
            wait=False,
            sleep=no_sleep,
        )


def test_analyze_z_wait_pobiera_werdykt_z_serwera(config, printer, source_dir, no_sleep):
    client = FakeClient(
        task_states=[
            {"task_id": "t1", "status": "running", "progress": 40},
            {"task_id": "t1", "status": "completed", "progress": 100},
        ]
    )

    result = analyze_cmd.run(
        client, config, printer, path=source_dir, modules=[], wait=True, sleep=no_sleep
    )

    assert result["status"] == "completed"
    assert result["summary"]["should_fail"] is False
    assert client.named("summary")[0][1][1] == "critical"


def test_analyze_zglasza_przekroczenie_progu(config, printer, source_dir, no_sleep):
    client = FakeClient(
        summary={
            "threshold": "critical",
            "counts": {"critical": 2},
            "total": 2,
            "blocking": 2,
            "should_fail": True,
            "description": "2 znaleziska krytyczne",
        }
    )

    with pytest.raises(ThresholdExceeded) as excinfo:
        analyze_cmd.run(
            client, config, printer, path=source_dir, modules=[], wait=True, sleep=no_sleep
        )

    assert excinfo.value.exit_code == 1


def test_analyze_zglasza_bledne_zadanie(config, printer, source_dir, no_sleep):
    client = FakeClient(task_states=[{"task_id": "t1", "status": "failed", "error": "OOM"}])

    with pytest.raises(CliError, match="błędem"):
        analyze_cmd.run(
            client, config, printer, path=source_dir, modules=[], wait=True, sleep=no_sleep
        )


@pytest.mark.parametrize("terminal", ["cancelled", "timeout", "partial_failure"])
def test_analyze_konczy_czekanie_na_kazdym_stanie_koncowym(
    config, printer, source_dir, no_sleep, terminal
):
    client = FakeClient(task_states=[{"task_id": "t1", "status": terminal}])

    with pytest.raises(CliError, match="błędem"):
        analyze_cmd.run(
            client, config, printer, path=source_dir, modules=[], wait=True, sleep=no_sleep
        )

    # Jedno odpytanie — zadanie w stanie końcowym już się nie zmieni.
    assert len(client.named("task_status")) == 1


def test_status_watch_konczy_na_anulowanym_zadaniu(printer, no_sleep):
    client = FakeClient(task_states=[{"task_id": "t1", "status": "cancelled"}])

    payload = status_cmd.run(client, printer, task_id="t1", watch=True, sleep=no_sleep)

    assert payload["status"] == "cancelled"


def test_analyze_konczy_czekanie_po_limicie(config, printer, source_dir, no_sleep):
    client = FakeClient(task_states=[{"task_id": "t1", "status": "running", "progress": 10}])

    with pytest.raises(CliError, match="nie zakończyła się"):
        analyze_cmd.run(
            client,
            config,
            printer,
            path=source_dir,
            modules=[],
            wait=True,
            timeout_minutes=1,
            sleep=no_sleep,
        )


# ── generate ────────────────────────────────────────────────────────────────


def test_generate_zapisuje_pliki(config, printer, tmp_path):
    client = FakeClient(
        list_test_cases={
            "items": [
                {
                    "id": "abcdef12-0000-0000-0000-000000000000",
                    "title": "Logowanie zwraca token",
                    "language": "python",
                    "imports": "import pytest",
                    "test_code": "def test_login():\n    assert True",
                }
            ]
        }
    )

    result = generate_cmd.run(
        client, config, printer, output_dir=tmp_path / "tests", framework="pytest"
    )

    assert result["files_written"] == 1
    written = Path(result["files"][0])
    assert written.suffix == ".py"
    assert "import pytest" in written.read_text(encoding="utf-8")


def test_generate_pomija_przypadki_bez_kodu(config, printer, tmp_path):
    client = FakeClient(
        list_test_cases={"items": [{"id": "1", "title": "Opisowy", "test_code": None}]}
    )

    result = generate_cmd.run(
        client, config, printer, output_dir=tmp_path / "tests", framework="pytest"
    )

    assert result["files_written"] == 0
    assert result["skipped_without_code"] == 1


def test_generate_bez_frameworka_konczy_sie_bledem(config, printer, tmp_path):
    with pytest.raises(CliError, match="frameworka"):
        generate_cmd.run(FakeClient(), config, printer, output_dir=tmp_path, framework=None)


def test_generate_bez_przypadkow_podpowiada_analize(config, printer, tmp_path):
    with pytest.raises(CliError, match="Brak przypadków") as excinfo:
        generate_cmd.run(FakeClient(), config, printer, output_dir=tmp_path, framework="pytest")

    assert "analyze" in (excinfo.value.hint or "")


def test_nazwa_pliku_zawiera_identyfikator(config):
    name = generate_cmd.file_name(
        {"id": "abcdef1234", "title": "Ten sam tytuł", "language": "java"}, "junit", None
    )

    assert name.endswith(".java")
    assert "abcdef12" in name


def test_rozszerzenie_wynika_z_frameworka_gdy_brak_jezyka():
    assert generate_cmd.file_name({"id": "x", "title": "t"}, "playwright", None).endswith(".ts")


# ── export ──────────────────────────────────────────────────────────────────


def test_export_pobiera_plik(config, printer, tmp_path, no_sleep):
    client = FakeClient()
    output = tmp_path / "raport.pdf"

    result = export_cmd.run(
        client, config, printer, export_format="pdf", output=output, sleep=no_sleep
    )

    assert output.exists()
    assert result["export_id"] == "e1"
    assert client.named("request_export")[0][1][2] == "pdf"


def test_export_odrzuca_nieznany_format(config, printer, no_sleep):
    with pytest.raises(CliError, match="Nieobsługiwany format"):
        export_cmd.run(
            FakeClient(), config, printer, export_format="docx", output=None, sleep=no_sleep
        )


def test_export_zglasza_blad_serwera(config, printer, no_sleep):
    client = FakeClient(export_status={"export_id": "e1", "status": "error", "error": "brak danych"})

    with pytest.raises(CliError, match="nie zdołał"):
        export_cmd.run(client, config, printer, export_format="pdf", output=None, sleep=no_sleep)


def test_raport_zawiera_znaleziska():
    report = export_cmd.build_report(
        "p1",
        {"counts": {"critical": 1}, "total": 1, "description": "1 krytyczne"},
        [{"id": "f1", "title": "SQLi", "severity": "critical", "cwe_id": "CWE-89"}],
    )

    assert report["kpis"]["critical_count"] == 1
    assert report["findings"][0]["cwe_id"] == "CWE-89"
    assert report["conclusions"] == ["1 krytyczne"]


# ── scan ────────────────────────────────────────────────────────────────────


def test_scan_uruchamia_i_sprawdza_prog(config, printer, no_sleep):
    client = FakeClient()

    result = scan_cmd.run(client, config, printer, scan_type="sast", sleep=no_sleep)

    assert result["scan_id"] == "s1"
    assert result["summary"]["should_fail"] is False


def test_scan_prog_z_argumentu_wygrywa(config, printer, no_sleep):
    client = FakeClient()

    scan_cmd.run(client, config, printer, scan_type="sast", severity_threshold="high", sleep=no_sleep)

    assert client.named("summary")[0][1][1] == "high"


def test_scan_odrzuca_nieznany_typ(config, printer, no_sleep):
    with pytest.raises(CliError, match="Nieznany typ skanu"):
        scan_cmd.run(FakeClient(), config, printer, scan_type="magia", sleep=no_sleep)


def test_scan_dast_wymaga_adresu(config, printer, no_sleep):
    with pytest.raises(CliError, match="target-url"):
        scan_cmd.run(FakeClient(), config, printer, scan_type="dast", sleep=no_sleep)


def test_scan_zglasza_przekroczenie_progu(config, printer, no_sleep):
    client = FakeClient(
        summary={
            "threshold": "critical",
            "counts": {"critical": 1},
            "total": 1,
            "blocking": 1,
            "should_fail": True,
            "description": "1 znalezisko krytyczne",
        }
    )

    with pytest.raises(ThresholdExceeded):
        scan_cmd.run(client, config, printer, scan_type="sast", sleep=no_sleep)


# ── status ──────────────────────────────────────────────────────────────────


def test_status_zwraca_biezacy_stan(printer, no_sleep):
    client = FakeClient(task_states=[{"task_id": "t1", "status": "running", "progress": 55}])

    payload = status_cmd.run(client, printer, task_id="t1", watch=False, sleep=no_sleep)

    assert payload["progress"] == 55
    assert len(client.named("task_status")) == 1


def test_status_watch_czeka_do_konca(printer, no_sleep):
    client = FakeClient(
        task_states=[
            {"task_id": "t1", "status": "running", "progress": 10},
            {"task_id": "t1", "status": "completed", "progress": 100},
        ]
    )

    payload = status_cmd.run(client, printer, task_id="t1", watch=True, sleep=no_sleep)

    assert payload["status"] == "completed"
