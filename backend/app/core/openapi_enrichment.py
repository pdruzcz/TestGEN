"""Wzbogacanie schemy OpenAPI — Epic 8, Story 8.5 (AC1, AC3, AC4).

FastAPI generuje poprawną schemę z typów, ale nie wie o rzeczach, które
wynikają z konfiguracji aplikacji: że uwierzytelniamy się Bearerem (JWT albo
kluczem API z 8.6), że każdy endpoint może zwrócić 429 z nagłówkami limitu
(rate limiting z 7.8) i że warto pokazać gotowe wywołanie w trzech językach.

Wszystko to dokładamy raz, przy pierwszym żądaniu o schemę, i cache'ujemy
w ``app.openapi_schema`` — wzorzec zalecany przez FastAPI. Przy 239 operacjach
generowanie przykładów przy każdym otwarciu ``/docs`` byłoby marnotrawstwem.
"""

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.sdk_snippets import build_code_samples, example_for_schema, fill_path

logger = logging.getLogger(__name__)

# Endpointy dostępne bez poświadczeń: logowanie/rejestracja, sondy zdrowia
# oraz dostawy i powroty od zewnętrznych dostawców.
#
# Lista jest **jawna i dokładna**, nie oparta na podciągach. Wcześniejsza
# reguła „ścieżka zawiera /webhook" oznaczała jako publiczne także zarządzanie
# webhookami wychodzącymi (Story 8.7 — wymaga roli właściciela i sesji) oraz
# endpointy administracyjne. Dokumentacja mówiła wtedy integratorowi, że token
# jest zbędny, a API odpowiadało 401.
PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/password-reset",
    "/api/v1/auth/set-password",
    "/api/v1/health",
    "/health",
)

# Dostawy od dostawców: uwierzytelnia je podpis w ciele albo jednorazowy
# parametr ``state``, nie nagłówek ``Authorization`` — GitHub go nie wyśle.
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/integrations/github/webhook",
        "/api/v1/integrations/gitlab/webhook",
        "/api/v1/integrations/github/callback",
        "/api/v1/integrations/gitlab/callback",
        "/api/v1/billing/webhooks/tpay",
    }
)

# Ścieżki wyłączone z rate limitingu — lustro ``EXEMPT_SUBSTRINGS``
# z ``middleware/rate_limit``. Nie dokładamy im odpowiedzi 429, bo nigdy
# jej nie zwrócą.
RATE_LIMIT_EXEMPT_SUBSTRINGS: tuple[str, ...] = (
    "/webhooks/",
    "/integrations/github/webhook",
    "/integrations/gitlab/webhook",
    "/health",
)

SECURITY_SCHEME_NAME = "BearerAuth"

_TAG_DESCRIPTIONS: dict[str, str] = {
    "auth": "Rejestracja, logowanie, MFA, odświeżanie tokenów i reset hasła",
    "users": "Konta użytkowników w firmie: zaproszenia, role, profil",
    "tenants": "Firmy (tenanty) i przełączanie kontekstu",
    "api-keys": "Klucze API do automatyzacji CI/CD (Story 8.6)",
    "projects": "Projekty: CRUD, preprocessing, statystyki",
    "uploads": "Wysyłanie kodu źródłowego i podłączanie repozytoriów Git",
    "documents": "Analiza dokumentacji: sekcje, klasyfikacja, wymagania, glosariusz, niespójności",
    "uml": "Diagramy UML: parsowanie, przepływy, analiza między diagramami",
    "gui": "Zrzuty ekranu GUI: komponenty, przepływy, regresja wizualna",
    "gherkin": "Scenariusze Gherkin/BDD generowane z UML i GUI",
    "analysis": "Uruchamianie i konfiguracja analiz projektu",
    "tasks": "Status i anulowanie zadań w tle",
    "test-cases": "Zarządzanie przypadkami testowymi: CRUD, wykonanie, przegląd",
    "codegen": "Generowanie kodu testowego dla wybranych frameworków",
    "healing": "Self-healing testów: naprawa lokatorów",
    "security": "Skany bezpieczeństwa: SAST, taint, zależności, konfiguracja, DAST",
    "gap-analysis": "Luki funkcjonalne, zgodność i rekomendacje",
    "traceability": "Macierz śledzenia: wymaganie → kod → test",
    "report-exports": "Eksport raportów do PDF, HTML, CSV, Excel, JSON i YAML",
    "dashboard": "Pulpit: statystyki i ostatnia aktywność",
    "notifications": "Powiadomienia in-app",
    "chat": "Asystent AI",
    "billing": "Subskrypcje, płatności, faktury i limity",
    "integrations": "Integracje z trackerami (Jira, Azure DevOps) i generator konfiguracji CI/CD",
    "integrations-scm": "Integracje z hostingiem kodu: GitHub i GitLab (OAuth, webhooki, status checki)",
    "integrations-tms": "Integracje z systemami zarządzania testami: TestRail (eksport przypadków)",
    "integrations-sync": "Dwukierunkowa synchronizacja przypadków testowych z TMS (kierunek, odstęp, konflikty)",
    "integrations-jira-import": "Import wymagań i załączników z Jiry jako dokumentacji projektu",
    "webhooks-outbound": "Webhooki wychodzące TestGEN: konfiguracja, testy, historia dostaw",
    "webhooks": "Notyfikacje przychodzące od operatora płatności",
    "admin": "Panel administracyjny platformy",
    "admin-cve": "Aktualizacje bazy CVE",
    "health": "Sondy zdrowia usługi",
}

_RATE_LIMIT_HEADERS: dict[str, Any] = {
    "X-RateLimit-Limit": {
        "description": "Limit żądań na minutę dla planu firmy",
        "schema": {"type": "integer", "example": 100},
    },
    "X-RateLimit-Remaining": {
        "description": "Ile żądań pozostało w bieżącym oknie",
        "schema": {"type": "integer", "example": 87},
    },
    "X-RateLimit-Reset": {
        "description": "Znacznik czasu (epoch) początku następnego okna",
        "schema": {"type": "integer", "example": 1767225600},
    },
}

_PROBLEM_SCHEMA_REF = {"$ref": "#/components/schemas/ProblemDetail"}

_PROBLEM_DETAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "title": "ProblemDetail",
    "description": "Błąd w formacie RFC 7807 (`application/problem+json`).",
    "properties": {
        "type": {"type": "string", "example": "https://testgen.io/errors/validation-error"},
        "title": {"type": "string", "example": "Validation Error"},
        "status": {"type": "integer", "example": 422},
        "detail": {"type": "string", "example": "Nie znaleziono projektu"},
        "instance": {"type": "string", "example": "/api/v1/projects/3fa85f64-5717-4562-b3fc-2c963f66afa6"},
    },
}

_AUTH_RESPONSES: dict[str, Any] = {
    "401": {
        "description": "Brak lub nieprawidłowe poświadczenia (wygasły token, odwołany klucz API)",
        "content": {"application/problem+json": {"schema": _PROBLEM_SCHEMA_REF}},
    },
    "403": {
        "description": "Poświadczenia poprawne, ale bez uprawnień do tej operacji",
        "content": {"application/problem+json": {"schema": _PROBLEM_SCHEMA_REF}},
    },
}

_RATE_LIMIT_RESPONSE: dict[str, Any] = {
    "description": (
        "Przekroczono limit żądań. Nagłówek `Retry-After` podaje, po ilu sekundach ponowić."
    ),
    "headers": {**_RATE_LIMIT_HEADERS, "Retry-After": {
        "description": "Liczba sekund do końca bieżącego okna",
        "schema": {"type": "integer", "example": 42},
    }},
    "content": {"application/problem+json": {"schema": _PROBLEM_SCHEMA_REF}},
}

_DESCRIPTION = """
Platforma TestGEN — automatyczne generowanie przypadków testowych, analiza
dokumentacji, UML, GUI i bezpieczeństwa.

## Uwierzytelnianie

Wszystkie chronione endpointy przyjmują nagłówek `Authorization: Bearer <token>`,
gdzie tokenem może być:

* **klucz API** (prefiks `tgn_`) — do automatyzacji i CI/CD; zakładasz go
  w *Ustawienia → Klucze API*. Klucz o zakresie „tylko odczyt" przepuszcza
  wyłącznie `GET`, `HEAD` i `OPTIONS`;
* **token JWT** z logowania — używany przez interfejs webowy.

Zakładanie kolejnych kluczy API i webhooków wymaga zalogowanej sesji — kluczem
API tych operacji wykonać się nie da.

## Limity żądań

Limit jest naliczany **per firma**, nie per klucz, w oknie jednominutowym.
Każda odpowiedź niesie nagłówki `X-RateLimit-Limit`, `X-RateLimit-Remaining`
i `X-RateLimit-Reset` (epoch początku następnego okna). Po przekroczeniu limitu
API zwraca `429` z nagłówkiem `Retry-After`.

Progi wynikają z planu firmy (stan na wydanie): Freemium i Basic — 100 żądań
na minutę, Premium — 1000. Wartości pochodzą z konfiguracji planów, więc
źródłem prawdy pozostaje cennik; bieżące zużycie widać w *Panelu zużycia
zasobów*.

Webhooki (przychodzące i wychodzące) oraz sondy zdrowia są z limitu wyłączone —
to dostawy od zewnętrznych systemów, nie ruch generowany przez firmę.

## Błędy

Błędy mają format RFC 7807 (`application/problem+json`) z polami `type`,
`title`, `status`, `detail` i `instance`.
""".strip()


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PATH_PREFIXES)


def _is_rate_limited(path: str) -> bool:
    return not any(fragment in path for fragment in RATE_LIMIT_EXEMPT_SUBSTRINGS)


def _request_body_example(operation: dict[str, Any], document: dict[str, Any]) -> Any:
    content = (operation.get("requestBody") or {}).get("content") or {}
    json_schema = (content.get("application/json") or {}).get("schema")
    if json_schema is None:
        return None
    return example_for_schema(json_schema, document)


def _enrich_operation(
    path: str,
    method: str,
    operation: dict[str, Any],
    document: dict[str, Any],
    server_url: str,
) -> None:
    requires_auth = not _is_public(path)

    if requires_auth:
        operation.setdefault("security", [{SECURITY_SCHEME_NAME: []}])
        for code, response in _AUTH_RESPONSES.items():
            operation.setdefault("responses", {}).setdefault(code, response)

    responses = operation.setdefault("responses", {})
    if _is_rate_limited(path):
        responses.setdefault("429", _RATE_LIMIT_RESPONSE)
        # Nagłówki limitu wracają przy każdej odpowiedzi, nie tylko przy 429.
        for code, response in responses.items():
            if code.startswith("2") and isinstance(response, dict):
                response.setdefault("headers", {}).update(_RATE_LIMIT_HEADERS)

    parameters = operation.get("parameters") or []
    url = server_url.rstrip("/") + fill_path(path, parameters, document)
    body = _request_body_example(operation, document)

    # ``x-code-samples`` czyta Swagger UI; ``x-codeSamples`` — ReDoc.
    samples = build_code_samples(method, url, body=body, requires_auth=requires_auth)
    operation["x-code-samples"] = samples
    operation["x-codeSamples"] = samples


def build_openapi_schema(app: FastAPI, server_url: str) -> dict[str, Any]:
    """Schema OpenAPI wzbogacona o bezpieczeństwo, limity i przykłady."""
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=_DESCRIPTION,
        routes=app.routes,
        tags=app.openapi_tags,
    )

    components = schema.setdefault("components", {})
    components.setdefault("securitySchemes", {})[SECURITY_SCHEME_NAME] = {
        "type": "http",
        "scheme": "bearer",
        "description": (
            "Klucz API (prefiks `tgn_`, Ustawienia → Klucze API) albo token JWT z logowania."
        ),
    }
    components.setdefault("schemas", {}).setdefault("ProblemDetail", _PROBLEM_DETAIL_SCHEMA)

    for path, operations in schema.get("paths", {}).items():
        for method, operation in operations.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete", "head", "options"):
                continue
            try:
                _enrich_operation(path, method, operation, schema, server_url)
            except Exception:  # dokumentacja nie może wywrócić aplikacji
                logger.warning("Nie udało się wzbogacić %s %s", method.upper(), path, exc_info=True)

    schema["tags"] = _build_tags(schema)
    return schema


def _build_tags(schema: dict[str, Any]) -> list[dict[str, str]]:
    """Opisy tagów dla tagów faktycznie występujących w schemie.

    Lista powstaje z użytych tagów, a nie ze stałej: tag dodany w nowym
    routerze pojawi się w dokumentacji od razu, choćby bez opisu.
    """
    used: set[str] = set()
    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            if isinstance(operation, dict):
                used.update(operation.get("tags") or [])

    return [
        {"name": tag, "description": _TAG_DESCRIPTIONS.get(tag, "")}
        for tag in sorted(used, key=lambda t: (t not in _TAG_DESCRIPTIONS, t))
    ]


def setup_openapi(app: FastAPI, server_url: str) -> None:
    """Podmienia generator schemy na wzbogacony, z cache'owaniem (AC4)."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        app.openapi_schema = build_openapi_schema(app, server_url)
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
