"""Generator referencji endpointów do ``docs/api/endpoints/`` — Story 8.13.

Referencja powstaje z żywej schemy OpenAPI, a nie z ręcznie pisanych opisów.
Przy 237 operacjach ręczna dokumentacja rozjechałaby się z kodem przy
pierwszej zmianie kontraktu — wygenerowana jest z definicji aktualna, a jej
odświeżenie to jedno polecenie.

Uruchomienie::

    cd backend
    python -m scripts.generate_api_docs

Nie wymaga bazy danych — ``app.openapi()`` introspekcjonuje trasy.
Pliki koncepcyjne (uwierzytelnianie, webhooki, przewodniki) pisane są ręcznie
i ten skrypt ich nie dotyka.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.core.sdk_snippets import PLACEHOLDER_API_KEY
from app.main import app

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "api" / "endpoints"

# Dziesięć grup z AC1. Aplikacja ma 31 tagów (efekt Epikow 1-8), więc
# mapujemy je na grupy tematyczne — inaczej czytelnik musiałby przeszukać
# 31 plików, żeby znaleźć jeden endpoint.
TAG_GROUPS: dict[str, dict[str, Any]] = {
    "auth": {
        "title": "Uwierzytelnianie i użytkownicy",
        "tags": ["auth", "users", "tenants", "api-keys"],
        "intro": (
            "Logowanie, rejestracja, MFA, zarządzanie kontami w firmie oraz klucze API "
            "do automatyzacji. Szczegóły obu sposobów uwierzytelniania opisuje "
            "[Uwierzytelnianie](../authentication.md)."
        ),
    },
    "projects": {
        "title": "Projekty i pliki",
        "tags": ["projects", "uploads"],
        "intro": (
            "Zarządzanie projektami oraz wysyłanie kodu źródłowego — pojedynczych plików, "
            "archiwów ZIP albo przez podłączenie repozytorium Git."
        ),
    },
    "analysis": {
        "title": "Analiza",
        "tags": ["analysis", "tasks", "documents", "uml", "gui", "dashboard"],
        "intro": (
            "Uruchamianie analiz, śledzenie zadań w tle oraz odczyt wyników analizy "
            "dokumentacji, diagramów UML i zrzutów GUI."
        ),
    },
    "test-cases": {
        "title": "Przypadki testowe",
        "tags": ["test-cases", "codegen", "gherkin", "healing"],
        "intro": (
            "Zarządzanie przypadkami testowymi, generowanie kodu testowego dla wybranych "
            "frameworków, scenariusze Gherkin oraz naprawa lokatorów."
        ),
    },
    "reports": {
        "title": "Raporty i eksport",
        "tags": ["report-exports"],
        "intro": (
            "Generowanie i pobieranie raportów w formatach PDF, HTML, CSV, Excel, JSON i YAML. "
            "Eksport przypadków do systemów TMS opisuje "
            "[Integracja z TMS](../tms-integration.md)."
        ),
    },
    "security-scan": {
        "title": "Bezpieczeństwo",
        "tags": ["security", "admin-cve"],
        "intro": (
            "Skany bezpieczeństwa (SAST, taint analysis, zależności, konfiguracja, DAST), "
            "znaleziska i rekomendacje naprawcze."
        ),
    },
    "gap-analysis": {
        "title": "Luki funkcjonalne i zgodność",
        "tags": ["gap-analysis", "traceability"],
        "intro": (
            "Porównanie dokumentacji z kodem, luki funkcjonalne, rekomendacje oraz macierz "
            "śledzenia wymaganie → kod → test."
        ),
    },
    "integrations": {
        "title": "Integracje",
        "tags": [
            "integrations",
            "integrations-scm",
            "integrations-tms",
            "integrations-sync",
            "integrations-jira-import",
        ],
        "intro": (
            "GitHub i GitLab (OAuth, webhooki, status checki), trackery Jira i Azure DevOps, "
            "systemy zarządzania testami oraz generator konfiguracji CI/CD. Przewodniki: "
            "[CI/CD](../cicd-integration.md), [TMS](../tms-integration.md)."
        ),
    },
    "webhooks": {
        "title": "Webhooki",
        "tags": ["webhooks-outbound", "webhooks"],
        "intro": (
            "Konfiguracja webhooków wychodzących TestGEN, testy połączenia i historia dostaw. "
            "Formaty zdarzeń i weryfikację podpisu opisuje [Webhooki](../webhooks.md)."
        ),
    },
    "billing": {
        "title": "Subskrypcje i limity",
        "tags": ["billing", "notifications", "admin"],
        "intro": (
            "Plany, płatności, faktury, liczniki zużycia i powiadomienia o zbliżaniu się "
            "do limitów. Progi żądań opisuje [Limity żądań](../rate-limiting.md)."
        ),
    },
}

_METHODS = ("get", "post", "put", "patch", "delete")


def _schema_name(node: dict[str, Any]) -> str | None:
    ref = node.get("$ref")
    if ref:
        return ref.rsplit("/", 1)[-1]
    for key in ("anyOf", "oneOf", "allOf"):
        for variant in node.get(key, []):
            name = _schema_name(variant)
            if name:
                return name
    if node.get("type") == "array":
        inner = _schema_name(node.get("items") or {})
        return f"lista {inner}" if inner else "lista"
    return None


# Nagłówek ``authorization`` i ciasteczko ``access_token`` pojawiają się
# w schemie, bo są argumentami zależności uwierzytelniającej — nie są częścią
# kontraktu konkretnego endpointu. Sposób uwierzytelniania opisuje osobna
# strona, więc powtarzanie ich przy 244 operacjach to szum.
_AUTH_PARAMS = frozenset({"authorization", "access_token"})


def _params_table(parameters: list[dict[str, Any]]) -> list[str]:
    parameters = [p for p in parameters if p.get("name") not in _AUTH_PARAMS]
    if not parameters:
        return []
    lines = ["| Parametr | W | Wymagany | Opis |", "| --- | --- | :-: | --- |"]
    for param in parameters:
        required = "tak" if param.get("required") else "nie"
        description = (param.get("description") or "").replace("\n", " ").strip()
        lines.append(
            f"| `{param.get('name')}` | {param.get('in')} | {required} | {description} |"
        )
    lines.append("")
    return lines


def _responses_table(responses: dict[str, Any]) -> list[str]:
    if not responses:
        return []
    lines = ["| Kod | Znaczenie |", "| :-: | --- |"]
    for code in sorted(responses):
        description = (responses[code].get("description") or "").replace("\n", " ").strip()
        lines.append(f"| `{code}` | {description} |")
    lines.append("")
    return lines


def _operation_section(path: str, method: str, operation: dict[str, Any]) -> list[str]:
    summary = operation.get("summary") or operation.get("operationId") or path
    lines = [f"### `{method.upper()} {path}`", "", f"{summary}.", ""]

    description = (operation.get("description") or "").strip()
    if description and description != summary:
        lines.extend([description, ""])

    lines.append(
        "**Uwierzytelnianie:** "
        + ("wymagane" if operation.get("security") else "niewymagane")
    )
    lines.append("")

    lines.extend(_params_table(operation.get("parameters") or []))

    body = (operation.get("requestBody") or {}).get("content", {}).get("application/json", {})
    if body.get("schema"):
        name = _schema_name(body["schema"])
        lines.append(f"**Ciało żądania:** `{name}`" if name else "**Ciało żądania:** JSON")
        lines.append("")

    lines.extend(_responses_table(operation.get("responses") or {}))

    for sample in operation.get("x-code-samples") or []:
        lang = {"curl": "bash", "Python": "python", "JavaScript": "javascript"}.get(
            sample["lang"], "text"
        )
        lines.append(f"<details><summary>Przykład — {sample['label']}</summary>")
        lines.append("")
        lines.append(f"```{lang}")
        lines.append(sample["source"])
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return lines


def _group_document(group_key: str, meta: dict[str, Any], operations: list[tuple]) -> str:
    lines = [
        f"# {meta['title']}",
        "",
        "> Plik generowany ze schemy OpenAPI przez `python -m scripts.generate_api_docs`.",
        "> Nie edytuj ręcznie — zmiany nadpisze kolejne uruchomienie.",
        "",
        meta["intro"],
        "",
        f"Liczba endpointów: **{len(operations)}**.",
        "",
        "[↩ Powrót do spisu treści](../index.md)",
        "",
        "---",
        "",
    ]
    for path, method, operation in operations:
        lines.extend(_operation_section(path, method, operation))
        lines.append("---")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate() -> dict[str, int]:
    schema = app.openapi()
    by_tag: dict[str, list[tuple]] = defaultdict(list)
    for path, operations in schema.get("paths", {}).items():
        for method, operation in operations.items():
            if method not in _METHODS:
                continue
            for tag in operation.get("tags") or ["inne"]:
                by_tag[tag].append((path, method, operation))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}
    covered_tags: set[str] = set()

    for group_key, meta in TAG_GROUPS.items():
        operations: list[tuple] = []
        for tag in meta["tags"]:
            covered_tags.add(tag)
            operations.extend(by_tag.get(tag, []))
        operations.sort(key=lambda item: (item[0], item[1]))

        (OUTPUT_DIR / f"{group_key}.md").write_text(
            _group_document(group_key, meta, operations), encoding="utf-8"
        )
        written[group_key] = len(operations)

    # Tag spoza mapowania oznacza endpoint, którego nikt nie udokumentował.
    missing = sorted(set(by_tag) - covered_tags - {"health", "chat"})
    if missing:
        raise SystemExit(
            "Tagi bez przypisanej grupy dokumentacji: " + ", ".join(missing) +
            "\nDopisz je do TAG_GROUPS w scripts/generate_api_docs.py."
        )

    return written


if __name__ == "__main__":
    counts = generate()
    total = sum(counts.values())
    for group, count in counts.items():
        print(f"{group:16s} {count:4d} endpointów")
    print(f"{'RAZEM':16s} {total:4d}")
    print(f"Klucz w przykładach: {PLACEHOLDER_API_KEY[:12]}… (fikcyjny)")
    print(json.dumps({"output": str(OUTPUT_DIR)}, ensure_ascii=False))
