"""Testy wzbogaconej schemy OpenAPI — Story 8.5 (AC1, AC3, AC4, AC5; Task 5.1/5.4).

Schema jest kontraktem, po którym integratorzy piszą kod, więc testy jadą po
realnej schemie aplikacji, a nie po wycinku. Dzięki temu wyłapią też endpoint
dodany później bez opisu albo bez wymogu uwierzytelnienia.
"""

import pytest

from app.core.openapi_enrichment import (
    SECURITY_SCHEME_NAME,
    build_openapi_schema,
    setup_openapi,
)
from app.main import create_app

SERVER = "https://api.testgen.io"


@pytest.fixture(scope="module")
def schema() -> dict:
    app = create_app()
    return build_openapi_schema(app, SERVER)


def _operations(schema: dict):
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                yield path, method, operation


# ── bezpieczeństwo (AC5) ─────────────────────────────────────────────────────


def test_schema_deklaruje_uwierzytelnianie_bearerem(schema):
    scheme = schema["components"]["securitySchemes"][SECURITY_SCHEME_NAME]

    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert "tgn_" in scheme["description"]


def test_chronione_endpointy_wymagaja_poswiadczen(schema):
    analyze = schema["paths"]["/api/v1/projects/{project_id}/analyze"]["post"]

    assert analyze["security"] == [{SECURITY_SCHEME_NAME: []}]


def test_logowanie_i_zdrowie_nie_wymagaja_poswiadczen(schema):
    """Wymóg tokenu na logowaniu byłby błędem kołowym."""
    for path, method in (("/api/v1/auth/login", "post"), ("/api/v1/health", "get")):
        assert "security" not in schema["paths"][path][method]


def test_lista_publicznych_endpointow_jest_zamknieta(schema):
    """Bezpiecznik na realny błąd: reguła po podciągu „/webhook" oznaczała jako
    publiczne także zarządzanie webhookami wychodzącymi (8.7 — rola właściciela
    i sesja) oraz endpointy administracyjne. Dokumentacja mówiła wtedy, że token
    jest zbędny, a API odpowiadało 401.

    Ta lista ma rosnąć wyłącznie świadomie — nowy wpis znaczy nowy endpoint
    dostępny bez poświadczeń."""
    public = {
        f"{method.upper()} {path}"
        for path, method, op in _operations(schema)
        if "security" not in op
    }

    assert public == {
        "POST /api/v1/auth/login",
        "POST /api/v1/auth/register",
        "POST /api/v1/auth/refresh",
        "POST /api/v1/auth/verify-email",
        "POST /api/v1/billing/webhooks/tpay",
        "GET /api/v1/health",
        "GET /api/v1/integrations/github/callback",
        "POST /api/v1/integrations/github/webhook",
        "GET /api/v1/integrations/gitlab/callback",
        "POST /api/v1/integrations/gitlab/webhook",
    }


def test_zarzadzanie_webhookami_wymaga_poswiadczen(schema):
    """Endpointy z 8.7 wymagają roli właściciela — dokumentacja musi to oddać."""
    for path, method in (("/api/v1/webhooks", "post"), ("/api/v1/webhooks", "get")):
        assert "security" in schema["paths"][path][method]


def test_webhooki_dostawcow_nie_wymagaja_naglowka_authorization(schema):
    """Uwierzytelnia je podpis w ciele, nie nagłówek — GitHub go nie wyśle."""
    webhook = schema["paths"]["/api/v1/integrations/github/webhook"]["post"]

    assert "security" not in webhook


def test_kazdy_chroniony_endpoint_opisuje_401_i_403(schema):
    braki = [
        f"{method.upper()} {path}"
        for path, method, op in _operations(schema)
        if "security" in op and not {"401", "403"} <= set(op.get("responses", {}))
    ]

    assert braki == []


# ── limity żądań (AC3) ───────────────────────────────────────────────────────


def test_endpointy_objete_limitem_opisuja_429(schema):
    analyze = schema["paths"]["/api/v1/projects/{project_id}/analyze"]["post"]
    response = analyze["responses"]["429"]

    assert "Retry-After" in response["headers"]
    assert "limit" in response["description"].lower()


def test_odpowiedzi_udane_niosa_naglowki_limitu(schema):
    analyze = schema["paths"]["/api/v1/projects/{project_id}/analyze"]["post"]
    headers = analyze["responses"]["202"]["headers"]

    assert set(headers) >= {"X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"}


def test_endpointy_wylaczone_z_limitu_nie_obiecuja_429(schema):
    """Middleware ich nie limituje — obiecywanie 429 wprowadzałoby w błąd."""
    webhook = schema["paths"]["/api/v1/integrations/github/webhook"]["post"]

    assert "429" not in webhook["responses"]


def test_opis_api_tlumaczy_limity_i_uwierzytelnianie(schema):
    description = schema["info"]["description"]

    assert "X-RateLimit-Limit" in description
    assert "Retry-After" in description
    assert "tgn_" in description
    assert "RFC 7807" in description


# ── format błędów (AC4) ──────────────────────────────────────────────────────


def test_schema_bledu_rfc7807_jest_zadeklarowana(schema):
    problem = schema["components"]["schemas"]["ProblemDetail"]

    assert set(problem["properties"]) == {"type", "title", "status", "detail", "instance"}


def test_odpowiedzi_bledow_wskazuja_na_schemat_problemu(schema):
    analyze = schema["paths"]["/api/v1/projects/{project_id}/analyze"]["post"]
    content = analyze["responses"]["401"]["content"]["application/problem+json"]

    assert content["schema"]["$ref"].endswith("ProblemDetail")


# ── przykłady wywołań (AC2/AC4) ──────────────────────────────────────────────


def test_kazda_operacja_ma_przyklady_w_trzech_jezykach(schema):
    braki = [
        f"{method.upper()} {path}"
        for path, method, op in _operations(schema)
        if [s["lang"] for s in op.get("x-code-samples", [])] != ["curl", "Python", "JavaScript"]
    ]

    assert braki == []


def test_przyklady_sa_takze_pod_kluczem_czytanym_przez_redoc(schema):
    """Swagger UI czyta ``x-code-samples``, ReDoc ``x-codeSamples``."""
    analyze = schema["paths"]["/api/v1/projects/{project_id}/analyze"]["post"]

    assert analyze["x-code-samples"] == analyze["x-codeSamples"]


def test_przyklady_uzywaja_adresu_z_konfiguracji(schema):
    """Wklejone wywołanie ma działać bez podmieniania hosta."""
    analyze = schema["paths"]["/api/v1/projects/{project_id}/analyze"]["post"]
    curl = analyze["x-code-samples"][0]["source"]

    assert f"{SERVER}/api/v1/projects/" in curl


def test_przyklady_nie_zostawiaja_niepodstawionych_parametrow(schema):
    """``{project_id}`` w gotowym wywołaniu to wklejka, która nie zadziała."""
    braki = []
    for path, method, op in _operations(schema):
        for sample in op.get("x-code-samples", []):
            if sample["lang"] != "curl":
                continue
            url = sample["source"].split("'", 2)[1]
            if "{" in url:
                braki.append(f"{method.upper()} {path}")

    assert braki == []


def test_przyklad_analizy_niesie_realistyczne_dane(schema):
    curl = schema["paths"]["/api/v1/projects/{project_id}/analyze"]["post"]["x-code-samples"][0][
        "source"
    ]

    assert '"engine_mode": "native"' in curl
    assert "code_analysis" in curl


def test_przyklady_publicznego_endpointu_bez_klucza(schema):
    login = schema["paths"]["/api/v1/auth/login"]["post"]
    curl = login["x-code-samples"][0]["source"]

    assert "Authorization" not in curl


# ── tagi (AC1) ───────────────────────────────────────────────────────────────


def test_tagi_pokrywaja_wszystkie_uzyte_grupy(schema):
    used = {t for _, _, op in _operations(schema) for t in op.get("tags", [])}
    documented = {t["name"] for t in schema["tags"]}

    assert used <= documented


def test_kazdy_tag_ma_opis_po_polsku(schema):
    bez_opisu = [t["name"] for t in schema["tags"] if not t["description"]]

    assert bez_opisu == []


def test_kluczowe_grupy_sa_opisane(schema):
    descriptions = {t["name"]: t["description"] for t in schema["tags"]}

    assert "Klucze API" in descriptions["api-keys"]
    assert "GitHub" in descriptions["integrations-scm"]
    assert "Webhooki wychodzące" in descriptions["webhooks-outbound"]


# ── cache i konfiguracja aplikacji ───────────────────────────────────────────


def test_schema_jest_cachowana_miedzy_wywolaniami():
    """Budowanie przykładów dla 239 operacji przy każdym otwarciu /docs to marnotrawstwo."""
    app = create_app()
    setup_openapi(app, SERVER)

    assert app.openapi() is app.openapi()


def test_dokumentacja_wylaczona_poza_trybem_debug(monkeypatch):
    """Swagger UI w produkcji ujawniałby całą powierzchnię API."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "debug", False, raising=False)
    app = create_app()

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None


def test_dokumentacja_dostepna_w_trybie_debug(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "debug", True, raising=False)
    app = create_app()

    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"


@pytest.mark.asyncio
async def test_openapi_json_zwraca_wzbogacona_schemme(monkeypatch):
    """Kontrakt widziany przez integratora, nie tylko obiekt w pamięci.

    Bez ``lifespan`` — ten łączy się z bazą, MinIO i Redisem, a tu sprawdzamy
    wyłącznie serializację schemy.
    """
    from httpx import ASGITransport, AsyncClient

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "debug", True, raising=False)
    app = create_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    body = response.json()
    assert SECURITY_SCHEME_NAME in body["components"]["securitySchemes"]
    assert body["paths"]["/api/v1/projects/{project_id}/analyze"]["post"]["x-code-samples"]
