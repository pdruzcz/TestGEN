"""Testy generatora referencji API — Story 8.13.

Dokumentacja endpointów powstaje ze schemy OpenAPI, więc jej aktualność zależy
od jednego: czy każdy tag ma przypisaną grupę. Tag bez grupy oznacza endpointy,
których referencja w ogóle nie opisuje — i nikt by się o tym nie dowiedział
poza czytelnikiem, który ich nie znalazł.
"""

import pytest

from app.main import create_app
from scripts.generate_api_docs import TAG_GROUPS, _operation_section, _params_table

# Tagi świadomie pominięte: sondy zdrowia i asystent AI nie są częścią
# publicznego kontraktu integracyjnego.
_SKIPPED_TAGS = {"health", "chat"}


@pytest.fixture(scope="module")
def schema() -> dict:
    return create_app().openapi()


def _used_tags(schema: dict) -> set[str]:
    tags: set[str] = set()
    for operations in schema["paths"].values():
        for method, operation in operations.items():
            if method in ("get", "post", "put", "patch", "delete"):
                tags.update(operation.get("tags") or [])
    return tags


def test_kazdy_tag_ma_przypisana_grupe_dokumentacji(schema):
    """Nowy router bez wpisu w TAG_GROUPS zostawiłby endpointy nieudokumentowane."""
    mapped = {tag for meta in TAG_GROUPS.values() for tag in meta["tags"]}
    missing = _used_tags(schema) - mapped - _SKIPPED_TAGS

    assert missing == set(), (
        f"Tagi bez grupy: {sorted(missing)}. "
        "Dopisz je do TAG_GROUPS w scripts/generate_api_docs.py."
    )


def test_grupy_nie_dubluja_tagow():
    """Tag w dwóch grupach dałby te same endpointy w dwóch plikach."""
    seen: dict[str, str] = {}
    duplicates = []
    for group, meta in TAG_GROUPS.items():
        for tag in meta["tags"]:
            if tag in seen:
                duplicates.append(f"{tag}: {seen[tag]} i {group}")
            seen[tag] = group

    assert duplicates == []


def test_jest_dziesiec_grup_zgodnie_z_kontraktem_story():
    assert len(TAG_GROUPS) == 10


def test_kazda_grupa_ma_tytul_i_wstep():
    for group, meta in TAG_GROUPS.items():
        assert meta["title"], group
        assert meta["intro"], group
        assert meta["tags"], group


def test_parametry_uwierzytelniania_nie_zasmiecaja_tabeli():
    """``authorization`` i ``access_token`` to artefakt zależności, nie kontrakt."""
    parameters = [
        {"name": "authorization", "in": "header"},
        {"name": "access_token", "in": "cookie"},
        {"name": "project_id", "in": "path", "required": True, "description": "Projekt"},
    ]

    table = "\n".join(_params_table(parameters))

    assert "project_id" in table
    assert "authorization" not in table
    assert "access_token" not in table


def test_tabela_znika_gdy_zostaly_same_parametry_uwierzytelniania():
    assert _params_table([{"name": "authorization", "in": "header"}]) == []


def test_sekcja_operacji_oznacza_wymog_uwierzytelnienia(schema):
    analyze = schema["paths"]["/api/v1/projects/{project_id}/analyze"]["post"]

    section = "\n".join(
        _operation_section("/api/v1/projects/{project_id}/analyze", "post", analyze)
    )

    assert "POST /api/v1/projects/{project_id}/analyze" in section
    assert "**Uwierzytelnianie:** wymagane" in section
    # Przykłady w trzech językach, każdy w zwijanej sekcji
    assert section.count("<details>") == 3


def test_sekcja_operacji_publicznej_nie_klamie_o_uwierzytelnieniu(schema):
    login = schema["paths"]["/api/v1/auth/login"]["post"]

    section = "\n".join(_operation_section("/api/v1/auth/login", "post", login))

    assert "**Uwierzytelnianie:** niewymagane" in section
