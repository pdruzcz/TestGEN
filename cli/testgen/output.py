"""Formatowanie wyjścia — Story 8.10 (AC5).

Trzy tryby: czytelny dla człowieka (domyślny), JSON i YAML. Wybór formatu jest
globalny, bo wyjście CLI bywa i czytane, i parsowane — a mieszanie tabel z
JSON-em w jednym wywołaniu uniemożliwiłoby to drugie.

Kolory włączamy tylko wtedy, gdy wyjście idzie na terminal. Przekierowane do
pliku albo do `jq` zostaje czystym tekstem — sekwencje sterujące psułyby
parsowanie i zaśmiecały logi CI.
"""

import json
import sys
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table


class OutputFormat(StrEnum):
    HUMAN = "human"
    JSON = "json"
    YAML = "yaml"


@dataclass
class Printer:
    """Jedno wyjście na całe wywołanie CLI."""

    fmt: OutputFormat = OutputFormat.HUMAN
    quiet: bool = False

    def __post_init__(self) -> None:
        # Komunikaty diagnostyczne idą na stderr, żeby nie zanieczyszczać
        # strumienia, który ktoś może przepuszczać przez `jq`.
        self._out = Console(file=sys.stdout, no_color=not sys.stdout.isatty())
        self._err = Console(file=sys.stderr, no_color=not sys.stderr.isatty())

    @property
    def is_machine(self) -> bool:
        return self.fmt in (OutputFormat.JSON, OutputFormat.YAML)

    def result(self, data: Any, *, table: Table | None = None) -> None:
        """Główny wynik komendy."""
        if self.quiet:
            return
        if self.fmt is OutputFormat.JSON:
            self._out.print_json(json.dumps(data, ensure_ascii=False, default=str))
        elif self.fmt is OutputFormat.YAML:
            self._out.print(
                yaml.safe_dump(_plain(data), allow_unicode=True, sort_keys=False).rstrip()
            )
        elif table is not None:
            self._out.print(table)
        else:
            self._out.print(_human(data))

    def info(self, message: str) -> None:
        """Komunikat postępu — pomijany w trybach maszynowych i w `--quiet`."""
        if self.quiet or self.is_machine:
            return
        self._err.print(message)

    def success(self, message: str) -> None:
        if self.quiet or self.is_machine:
            return
        self._err.print(f"[green]✓[/green] {message}")

    def warning(self, message: str) -> None:
        if self.quiet:
            return
        self._err.print(f"[yellow]![/yellow] {message}")

    def error(self, message: str, hint: str | None = None) -> None:
        """Błędy pokazujemy nawet w `--quiet` — inaczej nie dałoby się ich zdiagnozować."""
        self._err.print(f"[red]✗[/red] {message}")
        if hint:
            self._err.print(f"  [dim]{hint}[/dim]")


def _plain(data: Any) -> Any:
    """Sprowadza strukturę do typów, które YAML zserializuje bez znaczników."""
    if isinstance(data, dict):
        return {str(k): _plain(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_plain(item) for item in data]
    if isinstance(data, (str, int, float, bool)) or data is None:
        return data
    return str(data)


def _human(data: Any) -> str:
    if isinstance(data, dict):
        width = max((len(str(k)) for k in data), default=0)
        return "\n".join(f"{str(k).ljust(width)}  {v}" for k, v in data.items())
    if isinstance(data, list):
        return "\n".join(str(item) for item in data)
    return str(data)


def findings_table(counts: dict[str, int]) -> Table:
    """Tabela znalezisk wg wagi — od najpoważniejszych."""
    table = Table(title="Znaleziska", show_edge=False)
    table.add_column("Waga")
    table.add_column("Liczba", justify="right")

    labels = {
        "critical": ("Krytyczne", "red"),
        "high": ("Wysokie", "dark_orange"),
        "medium": ("Średnie", "yellow"),
        "low": ("Niskie", "cyan"),
        "info": ("Informacyjne", "dim"),
    }
    for severity, (label, color) in labels.items():
        count = counts.get(severity, 0)
        if count:
            table.add_row(f"[{color}]{label}[/{color}]", str(count))
    if not table.rows:
        table.add_row("[green]Brak[/green]", "0")
    return table


def projects_table(projects: list[dict[str, Any]]) -> Table:
    table = Table(title="Projekty", show_edge=False)
    table.add_column("Identyfikator", style="dim")
    table.add_column("Nazwa")
    table.add_column("Status")
    for project in projects:
        table.add_row(str(project.get("id", "")), project.get("name", ""), project.get("status", ""))
    return table
