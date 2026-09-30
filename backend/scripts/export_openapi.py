"""Eksport specyfikacji OpenAPI do docs/p1/modul-dokumentacji/openapi.yaml.

Snapshot auto-generowany z FastAPI (``app.openapi()``). Uruchamiany ręcznie po
zmianach API; commitowany jako artefakt dokumentacji (wzorzec modul-uml-gui).

Uruchomienie::

    cd backend
    python -m scripts.export_openapi

Wymaga ``pyyaml`` (dep główny). Nie wymaga bazy danych — ``app.openapi()``
introspekcja tras.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.main import app

# Repo root = backend/.. ; output w docs/p1/modul-dokumentacji/
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT = REPO_ROOT / "docs" / "p1" / "modul-dokumentacji" / "openapi.yaml"


def main() -> None:
    schema = app.openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        yaml.dump(schema, f, allow_unicode=True, sort_keys=False)
    n_paths = len(schema.get("paths", {}))
    print(f"OpenAPI -> {OUTPUT.relative_to(REPO_ROOT)}  ({n_paths} sciezek)")


if __name__ == "__main__":
    main()
