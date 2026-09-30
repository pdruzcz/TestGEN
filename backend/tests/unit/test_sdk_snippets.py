"""Testy generatorów przykładów wywołań — Story 8.5 (AC2; Task 5.2).

Snippety mają być gotowe do wklejenia, więc testy sprawdzają, że zawierają
uwierzytelnienie, poprawny JSON i obsługę błędu — a nie tylko że „coś zwrócono".
"""

import json

import pytest

from app.core.sdk_snippets import (
    PLACEHOLDER_API_KEY,
    build_code_samples,
    example_for_schema,
    fill_path,
    generate_curl_snippet,
    generate_js_snippet,
    generate_python_snippet,
)

URL = "https://api.testgen.io/api/v1/projects/abc/analyze"
BODY = {"engine_mode": "native", "modules": ["code_analysis"]}


# ── przykłady ze schematu ────────────────────────────────────────────────────


def test_example_ma_pierwszenstwo_przed_typem():
    assert example_for_schema({"type": "string", "example": "konkret"}, {}) == "konkret"


def test_default_uzywany_gdy_brak_example():
    assert example_for_schema({"type": "integer", "default": 42}, {}) == 42


def test_enum_daje_pierwsza_wartosc():
    assert example_for_schema({"enum": ["native", "llm", "hybrid"]}, {}) == "native"


def test_ref_jest_rozwijany():
    document = {"components": {"schemas": {"Mode": {"enum": ["native", "llm"]}}}}

    assert example_for_schema({"$ref": "#/components/schemas/Mode"}, document) == "native"


def test_ref_w_anyof_nie_wyczerpuje_limitu_zagniezdzenia():
    """Indirekcja to nie zejście w głąb — inaczej enum ginie pod warstwami."""
    document = {
        "components": {
            "schemas": {
                "Outer": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "anyOf": [
                                {"$ref": "#/components/schemas/Mode"},
                                {"type": "null"},
                            ]
                        }
                    },
                },
                "Mode": {"enum": ["native", "llm"]},
            }
        }
    }

    result = example_for_schema({"$ref": "#/components/schemas/Outer"}, document)

    assert result == {"mode": "native"}


def test_null_w_anyof_jest_pomijany():
    node = {"anyOf": [{"type": "null"}, {"type": "integer", "default": 7}]}

    assert example_for_schema(node, {}) == 7


def test_uuid_dostaje_realistyczny_placeholder():
    value = example_for_schema({"type": "string", "format": "uuid"}, {})

    assert value.count("-") == 4
    assert len(value) == 36


def test_data_dostaje_format_iso():
    assert example_for_schema({"type": "string", "format": "date-time"}, {}) == "2026-01-15T10:00:00Z"


def test_obiekt_zaczyna_od_pol_wymaganych():
    node = {
        "type": "object",
        "required": ["wymagane"],
        "properties": {
            "aaa_opcjonalne": {"type": "string"},
            "wymagane": {"type": "string"},
        },
    }

    assert list(example_for_schema(node, {})) == ["wymagane", "aaa_opcjonalne"]


def test_tablica_dostaje_jeden_element():
    node = {"type": "array", "items": {"type": "string", "example": "x"}}

    assert example_for_schema(node, {}) == ["x"]


def test_cykl_w_schemacie_nie_zapetla_generatora():
    """Schemat rekurencyjny (drzewo, graf) nie może zawiesić dokumentacji."""
    document = {
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {"child": {"$ref": "#/components/schemas/Node"}},
                }
            }
        }
    }

    example_for_schema({"$ref": "#/components/schemas/Node"}, document)


def test_nieznany_ref_nie_wywraca_generatora():
    assert example_for_schema({"$ref": "#/components/schemas/Brak"}, {}) is not None


# ── podstawianie parametrów ścieżki ──────────────────────────────────────────


def test_parametry_sciezki_sa_podstawiane():
    parameters = [
        {"name": "project_id", "in": "path", "schema": {"type": "string", "format": "uuid"}},
        {"name": "limit", "in": "query", "schema": {"type": "integer"}},
    ]

    filled = fill_path("/api/v1/projects/{project_id}/files", parameters, {})

    assert "{project_id}" not in filled
    assert "{" not in filled


def test_parametry_zapytania_nie_trafiaja_do_sciezki():
    parameters = [{"name": "limit", "in": "query", "schema": {"type": "integer"}}]

    assert fill_path("/api/v1/tasks", parameters, {}) == "/api/v1/tasks"


# ── curl ─────────────────────────────────────────────────────────────────────


def test_curl_zawiera_metode_url_i_klucz():
    snippet = generate_curl_snippet("POST", URL, body=BODY)

    assert snippet.startswith("curl -X POST")
    assert URL in snippet
    assert PLACEHOLDER_API_KEY in snippet
    assert "Content-Type: application/json" in snippet


def test_curl_bez_ciala_nie_ma_wiszacego_ukosnika():
    """Wiszący backslash sprawia, że wklejona komenda czeka na kolejną linię."""
    snippet = generate_curl_snippet("GET", URL, body=None)

    assert not snippet.rstrip().endswith("\\")


def test_curl_publicznego_endpointu_bez_naglowka_autoryzacji():
    snippet = generate_curl_snippet("POST", URL, body={"email": "a@b.pl"}, requires_auth=False)

    assert "Authorization" not in snippet


def test_curl_niesie_poprawny_json():
    snippet = generate_curl_snippet("POST", URL, body=BODY)
    payload = snippet.split("-d '", 1)[1].rsplit("'", 1)[0]

    assert json.loads(payload) == BODY


# ── Python ───────────────────────────────────────────────────────────────────


def test_python_uzywa_requests_i_sprawdza_status():
    snippet = generate_python_snippet("POST", URL, body=BODY)

    assert "import requests" in snippet
    assert "requests.post(" in snippet
    assert "raise_for_status()" in snippet
    assert "timeout=30" in snippet


def test_python_odporny_na_odpowiedz_bez_ciala():
    """204 No Content nie ma JSON-a — ``.json()`` bez zabezpieczenia by padł."""
    snippet = generate_python_snippet("DELETE", URL)

    assert "response.content" in snippet


def test_python_bez_autoryzacji_nie_deklaruje_klucza():
    snippet = generate_python_snippet("GET", URL, requires_auth=False)

    assert "API_KEY" not in snippet
    assert "headers=" not in snippet


# ── JavaScript ───────────────────────────────────────────────────────────────


def test_js_uzywa_fetch_i_sprawdza_ok():
    snippet = generate_js_snippet("POST", URL, body=BODY)

    assert "await fetch(" in snippet
    assert "method: 'POST'" in snippet
    assert "if (!response.ok)" in snippet
    assert "JSON.stringify(" in snippet


def test_js_bez_autoryzacji_nie_ustawia_naglowka():
    snippet = generate_js_snippet("GET", URL, requires_auth=False)

    assert "apiKey" not in snippet
    assert "Authorization" not in snippet


# ── komplet ──────────────────────────────────────────────────────────────────


def test_komplet_zawiera_trzy_jezyki():
    samples = build_code_samples("POST", URL, body=BODY)

    assert [s["lang"] for s in samples] == ["curl", "Python", "JavaScript"]
    assert all(s["source"] for s in samples)
    assert all(s["label"] for s in samples)


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_kazda_metoda_trafia_do_wszystkich_snippetow(method):
    samples = build_code_samples(method, URL)
    sources = {s["lang"]: s["source"] for s in samples}

    assert f"-X {method}" in sources["curl"]
    assert f"requests.{method.lower()}(" in sources["Python"]
    assert f"method: '{method}'" in sources["JavaScript"]


def test_klucz_w_przykladach_jest_rozpoznawalnie_fikcyjny():
    """Nikt nie może pomylić go z prawdziwym — ale ma poprawny format."""
    assert PLACEHOLDER_API_KEY.startswith("tgn_")
    assert len(PLACEHOLDER_API_KEY) == 68
    assert "0123456789abcdef" in PLACEHOLDER_API_KEY
