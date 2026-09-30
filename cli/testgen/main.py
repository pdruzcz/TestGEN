"""Punkt wejścia CLI TestGEN — Story 8.10.

Wszystkie komendy dzielą jedną ścieżkę wyjścia: wyjątek `CliError` kończy
program kodem 2, `ThresholdExceeded` kodem 1, sukces kodem 0. Dzięki temu
kontrakt z pipeline'em CI/CD jest w jednym miejscu, a nie rozsiany po
komendach (AC5).
"""

from pathlib import Path
from typing import Annotated

import typer

from testgen import __version__
from testgen.auth import resolve_token
from testgen.client import TestGENClient
from testgen.commands import analyze as analyze_cmd
from testgen.commands import export as export_cmd
from testgen.commands import generate as generate_cmd
from testgen.commands import login as login_cmd
from testgen.commands import scan as scan_cmd
from testgen.commands import status as status_cmd
from testgen.config import load_config
from testgen.errors import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK, CliError, ThresholdExceeded
from testgen.output import OutputFormat, Printer, projects_table

app = typer.Typer(
    name="testgen",
    help="TestGEN CLI — analiza kodu, generowanie testów i raporty z terminala.",
    no_args_is_help=True,
    add_completion=False,
)


class Context:
    """Stan wspólny dla komend: konfiguracja, drukarka, leniwy klient."""

    def __init__(self, printer: Printer, overrides: dict) -> None:
        self.printer = printer
        self._overrides = overrides
        self._config = None
        self._client = None

    @property
    def config(self):
        if self._config is None:
            self._config = load_config(**self._overrides)
        return self._config

    @property
    def client(self) -> TestGENClient:
        # Klient powstaje dopiero przy pierwszym użyciu — `testgen logout`
        # i `--version` nie mogą wymagać poświadczeń.
        if self._client is None:
            config = self.config
            self._client = TestGENClient(
                config.api_url, resolve_token(config.api_key), config.timeout
            )
        return self._client


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"testgen {__version__}")
        raise typer.Exit(EXIT_OK)


@app.callback()
def main(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Wynik jako JSON")] = False,
    yaml_output: Annotated[bool, typer.Option("--yaml", help="Wynik jako YAML")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Bez wyjścia — tylko kod")] = False,
    api_url: Annotated[str | None, typer.Option("--api-url", help="Adres API TestGEN")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="Klucz API (tgn_…)")] = None,
    project_id: Annotated[str | None, typer.Option("--project-id", help="Identyfikator projektu")] = None,
    timeout: Annotated[int | None, typer.Option("--timeout", help="Limit czasu żądania [s]")] = None,
    version: Annotated[
        bool, typer.Option("--version", callback=_version_callback, is_eager=True, help="Wersja CLI")
    ] = False,
) -> None:
    """Opcje globalne — obowiązują dla każdej komendy."""
    if json_output and yaml_output:
        raise typer.BadParameter("Wybierz jeden format: --json albo --yaml")

    fmt = OutputFormat.JSON if json_output else OutputFormat.YAML if yaml_output else OutputFormat.HUMAN
    overrides = {
        "api_url": api_url,
        "api_key": api_key,
        "project_id": project_id,
        "timeout": timeout,
    }
    ctx.obj = Context(Printer(fmt=fmt, quiet=quiet), {k: v for k, v in overrides.items() if v is not None})


# ── autoryzacja ─────────────────────────────────────────────────────────────


@app.command()
def login(
    ctx: typer.Context,
    api_key: Annotated[str | None, typer.Option("--api-key", help="Klucz API tgn_…")] = None,
    email: Annotated[str | None, typer.Option("--email", help="Logowanie e-mailem")] = None,
    tenant_id: Annotated[
        str | None, typer.Option("--tenant-id", help="Organizacja przy wielu firmach")
    ] = None,
) -> None:
    """Zapisuje poświadczenia w ~/.testgen/auth."""
    context: Context = ctx.obj
    if email:
        password = typer.prompt("Hasło", hide_input=True)
        login_cmd.login_with_password(context.config, context.printer, email, password, tenant_id)
        return
    key = api_key or typer.prompt("Klucz API", hide_input=True)
    login_cmd.login_with_api_key(context.config, context.printer, key)


@app.command()
def logout(ctx: typer.Context) -> None:
    """Usuwa zapisane poświadczenia."""
    login_cmd.logout(ctx.obj.printer)


@app.command()
def whoami(ctx: typer.Context) -> None:
    """Pokazuje zalogowanego użytkownika i jego organizację."""
    context: Context = ctx.obj
    login_cmd.whoami(context.client, context.config, context.printer)


@app.command()
def projects(ctx: typer.Context) -> None:
    """Lista projektów dostępnych dla poświadczeń."""
    context: Context = ctx.obj
    payload = context.client.list_projects()
    items = payload.get("items") or []
    context.printer.result(
        payload if context.printer.is_machine else items,
        table=None if context.printer.is_machine else projects_table(items),
    )


# ── praca z projektem ───────────────────────────────────────────────────────


@app.command()
def analyze(
    ctx: typer.Context,
    path: Annotated[Path, typer.Argument(help="Katalog z kodem")] = Path("."),
    modules: Annotated[list[str] | None, typer.Option("--modules", "-m", help="Moduły analizy")] = None,
    engine_mode: Annotated[str | None, typer.Option("--engine-mode", help="native|llm|hybrid")] = None,
    framework: Annotated[str | None, typer.Option("--framework", help="Framework testów")] = None,
    wait: Annotated[bool, typer.Option("--wait", help="Czekaj na wynik i werdykt progu")] = False,
    timeout_minutes: Annotated[int, typer.Option("--timeout-minutes", help="Limit oczekiwania")] = 30,
) -> None:
    """Wysyła kod i uruchamia analizę."""
    context: Context = ctx.obj
    config = context.config
    if engine_mode:
        config.engine_mode = engine_mode
        config.validate()
    analyze_cmd.run(
        context.client,
        config,
        context.printer,
        path=path,
        modules=list(modules or []),
        wait=wait,
        framework=framework,
        timeout_minutes=timeout_minutes,
    )


@app.command()
def generate(
    ctx: typer.Context,
    framework: Annotated[str | None, typer.Option("--framework", "-f", help="Framework testów")] = None,
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o", help="Katalog docelowy")] = Path("tests"),
    language: Annotated[str | None, typer.Option("--language", help="Wymusza rozszerzenie plików")] = None,
) -> None:
    """Zapisuje wygenerowane testy na dysk."""
    context: Context = ctx.obj
    generate_cmd.run(
        context.client,
        context.config,
        context.printer,
        output_dir=output_dir,
        framework=framework,
        language=language,
    )


@app.command()
def export(
    ctx: typer.Context,
    export_format: Annotated[str, typer.Option("--format", "-f", help="pdf|html|csv|xlsx|json|yaml")] = "pdf",
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Plik docelowy")] = None,
    report_type: Annotated[str, typer.Option("--report-type", help="executive|technical|both")] = "both",
) -> None:
    """Pobiera raport projektu w wybranym formacie."""
    context: Context = ctx.obj
    export_cmd.run(
        context.client,
        context.config,
        context.printer,
        export_format=export_format,
        output=output,
        report_type=report_type,
    )


@app.command()
def scan(
    ctx: typer.Context,
    scan_type: Annotated[
        str, typer.Option("--type", "-t", help="sast|taint|dependency|config|dast")
    ] = "sast",
    severity_threshold: Annotated[
        str | None, typer.Option("--severity-threshold", help="critical|high|medium")
    ] = None,
    target_url: Annotated[str | None, typer.Option("--target-url", help="Adres celu dla DAST")] = None,
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help="Czekaj na wynik skanu")] = True,
    timeout_minutes: Annotated[int, typer.Option("--timeout-minutes", help="Limit oczekiwania")] = 30,
) -> None:
    """Uruchamia skan bezpieczeństwa i sprawdza próg."""
    context: Context = ctx.obj
    scan_cmd.run(
        context.client,
        context.config,
        context.printer,
        scan_type=scan_type,
        severity_threshold=severity_threshold,
        target_url=target_url,
        wait=wait,
        timeout_minutes=timeout_minutes,
    )


@app.command()
def status(
    ctx: typer.Context,
    task_id: Annotated[str, typer.Argument(help="Identyfikator zadania")],
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Odpytuj co 5 s aż do końca")] = False,
) -> None:
    """Sprawdza status zadania analizy lub skanu."""
    context: Context = ctx.obj
    status_cmd.run(context.client, context.printer, task_id=task_id, watch=watch)


def run() -> int:
    """Uruchamia CLI i tłumaczy wyjątki na kody wyjścia (AC5, AC6)."""
    printer = Printer()
    try:
        app()
    except ThresholdExceeded as exc:
        printer.error(exc.description)
        return EXIT_FINDINGS
    except CliError as exc:
        printer.error(exc.message, exc.hint)
        return exc.exit_code
    except SystemExit as exc:
        # Typer sam obsługuje `--help` i złe argumenty, kończąc `sys.exit`.
        # Przechwytujemy to zamiast pozwolić procesowi zniknąć, żeby kod
        # wyjścia przechodził przez jedno miejsce — także wtedy, gdy Typer
        # zmieni wersję i przestanie dzielić klasy wyjątków z `click`.
        return int(exc.code or EXIT_OK)
    except KeyboardInterrupt:
        printer.error("Przerwano")
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
