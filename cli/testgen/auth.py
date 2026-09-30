"""Przechowywanie poświadczeń — Story 8.10 (AC1).

Token trafia do `~/.testgen/auth` z prawami `600`. To nie jest magazyn
sekretów, tylko plik w katalogu domowym — dlatego CLI mówi wprost, gdzie go
zapisało, a w CI zaleca zmienną `TESTGEN_API_KEY` zamiast logowania.
"""

import json
import os
import stat
from pathlib import Path
from typing import Any

from testgen.errors import AuthError, CliError

AUTH_PATH = Path.home() / ".testgen" / "auth"
_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 600


def _write_secure(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Plik tworzymy z docelowymi prawami od razu — zapis, a potem chmod,
    # zostawiałby okno, w którym token jest czytelny dla innych kont.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    os.chmod(path, _FILE_MODE)


def save_credentials(token: str, *, api_url: str, kind: str = "api_key") -> Path:
    """Zapisuje poświadczenia i zwraca ścieżkę pliku."""
    _write_secure(AUTH_PATH, {"token": token, "api_url": api_url, "kind": kind})
    return AUTH_PATH


def load_credentials() -> dict[str, Any] | None:
    if not AUTH_PATH.is_file():
        return None
    try:
        data = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(
            f"Plik poświadczeń {AUTH_PATH} jest uszkodzony",
            hint="Usuń go i zaloguj się ponownie: testgen logout && testgen login",
        ) from exc
    return data if isinstance(data, dict) and data.get("token") else None


def clear_credentials() -> bool:
    """Usuwa zapisane poświadczenia. Zwraca ``False``, gdy nic nie było zapisane."""
    if not AUTH_PATH.is_file():
        return False
    AUTH_PATH.unlink()
    return True


def resolve_token(config_api_key: str | None = None) -> str:
    """Token do użycia: z konfiguracji/środowiska albo z zapisanych poświadczeń.

    Pierwszeństwo ma konfiguracja, bo zmienna `TESTGEN_API_KEY` w CI musi
    wygrać z tym, co przypadkiem zostało w katalogu domowym runnera.
    """
    if config_api_key:
        return config_api_key

    stored = load_credentials()
    if stored:
        return str(stored["token"])

    raise AuthError(
        "Brak poświadczeń",
        hint=(
            "Zaloguj się poleceniem `testgen login` albo ustaw zmienną "
            "środowiskową TESTGEN_API_KEY."
        ),
    )
