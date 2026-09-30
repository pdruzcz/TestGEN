"""Konfiguracja CLI — Story 8.10 (AC4).

Wartości pochodzą z czterech źródeł o malejącym pierwszeństwie:

1. argumenty wiersza poleceń,
2. zmienne środowiskowe (`TESTGEN_API_KEY`, `TESTGEN_API_URL`, …),
3. `.testgen.yaml` w katalogu projektu,
4. `~/.testgen/config.yaml` — ustawienia użytkownika.

Taka kolejność wynika z tego, jak narzędzie bywa używane: plik projektowy
trafia do repozytorium i opisuje domyślne zachowanie dla zespołu, a argument
w wywołaniu to świadoma jednorazowa decyzja, która musi wygrać.
"""

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from testgen.errors import CliError

PROJECT_CONFIG_NAME = ".testgen.yaml"
USER_CONFIG_PATH = Path.home() / ".testgen" / "config.yaml"

DEFAULT_API_URL = "https://api.testgen.io"
DEFAULT_ENGINE_MODE = "native"
DEFAULT_THRESHOLD = "critical"
DEFAULT_TIMEOUT_SECONDS = 30

ENGINE_MODES = ("native", "llm", "hybrid")
THRESHOLDS = ("critical", "high", "medium")

# Zmienne środowiskowe czytane zamiast pliku — wygodne w CI, gdzie sekret
# wstrzykuje się właśnie tą drogą.
_ENV_MAP = {
    "api_key": "TESTGEN_API_KEY",
    "api_url": "TESTGEN_API_URL",
    "project_id": "TESTGEN_PROJECT_ID",
}


@dataclass
class Config:
    api_url: str = DEFAULT_API_URL
    api_key: str | None = None
    project_id: str | None = None
    engine_mode: str = DEFAULT_ENGINE_MODE
    default_framework: str | None = None
    severity_threshold: str = DEFAULT_THRESHOLD
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    # Wzorce pomijane przy pakowaniu katalogu (AC2).
    exclude: list[str] = field(default_factory=list)

    def validate(self) -> "Config":
        if self.engine_mode not in ENGINE_MODES:
            raise CliError(
                f"Nieprawidłowy tryb silnika: {self.engine_mode}",
                hint="Dozwolone: " + ", ".join(ENGINE_MODES),
            )
        if self.severity_threshold not in THRESHOLDS:
            raise CliError(
                f"Nieprawidłowy próg: {self.severity_threshold}",
                hint="Dozwolone: " + ", ".join(THRESHOLDS),
            )
        if self.timeout < 1:
            raise CliError("Limit czasu musi być dodatni")
        self.api_url = self.api_url.rstrip("/")
        return self

    def require_project_id(self) -> str:
        if not self.project_id:
            raise CliError(
                "Nie wskazano projektu",
                hint=(
                    "Podaj --project-id albo dodaj `project_id` do .testgen.yaml "
                    "w katalogu projektu."
                ),
            )
        return self.project_id


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise CliError(f"Nie udało się odczytać {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CliError(f"Plik {path} musi zawierać mapowanie klucz-wartość")
    return data


def find_project_config(start: Path | None = None) -> Path | None:
    """Szuka `.testgen.yaml` w katalogu i wyżej, aż do korzenia.

    Przeszukiwanie w górę pozwala uruchomić CLI z podkatalogu repozytorium —
    tak jak działa `git`.
    """
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / PROJECT_CONFIG_NAME
        if candidate.is_file():
            return candidate
    return None


def load_config(start: Path | None = None, **overrides: Any) -> Config:
    """Scala konfigurację ze wszystkich źródeł i waliduje wynik."""
    known = {f.name for f in fields(Config)}
    merged: dict[str, Any] = {}

    merged.update({k: v for k, v in _read_yaml(USER_CONFIG_PATH).items() if k in known})

    project_config = find_project_config(start)
    if project_config is not None:
        merged.update({k: v for k, v in _read_yaml(project_config).items() if k in known})

    for key, env_name in _ENV_MAP.items():
        value = os.environ.get(env_name)
        if value:
            merged[key] = value

    merged.update({k: v for k, v in overrides.items() if v is not None and k in known})

    return Config(**merged).validate()
