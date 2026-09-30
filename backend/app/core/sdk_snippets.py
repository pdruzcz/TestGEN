"""Generatory przykładów wywołań API — Epic 8, Story 8.5 (AC2).

Przykłady powstają z samej schemy OpenAPI, a nie z ręcznie pisanych tekstów.
Przy 239 operacjach ręczne snippety rozjechałyby się z kodem przy pierwszej
zmianie kontraktu; wyprowadzone ze schemy są z definicji aktualne.

Ciało żądania budujemy z opisu schematu: bierzemy ``example``, potem
``default``, a na końcu wartość reprezentatywną dla typu. Taki przykład jest
realistyczny (właściwe nazwy pól i typy), a jednocześnie oczywiście fikcyjny —
nikt nie wklei go w produkcji myśląc, że to prawdziwe dane.
"""

import json
from typing import Any

# Wartości zastępcze — celowo rozpoznawalne jako przykładowe.
PLACEHOLDER_API_KEY = "tgn_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
_PLACEHOLDER_UUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
_PLACEHOLDER_BY_TYPE: dict[str, Any] = {
    "string": "przykladowa-wartosc",
    "integer": 1,
    "number": 1.0,
    "boolean": True,
    "array": [],
    "object": {},
}
# Ile pól obiektu pokazujemy — dłuższe ciało przestaje być przykładem,
# a staje się zrzutem schematu.
_MAX_EXAMPLE_FIELDS = 8
_MAX_NESTING = 3


def _resolve_ref(ref: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Rozwija ``$ref`` w obrębie dokumentu OpenAPI."""
    node: Any = schema
    for part in ref.lstrip("#/").split("/"):
        if not isinstance(node, dict) or part not in node:
            return {}
        node = node[part]
    return node if isinstance(node, dict) else {}


def example_for_schema(
    node: dict[str, Any],
    document: dict[str, Any],
    depth: int = 0,
) -> Any:
    """Przykładowa wartość dla fragmentu schematu."""
    if not isinstance(node, dict) or depth > _MAX_NESTING:
        return None

    # Rozwinięcie ``$ref`` i wybór wariantu z ``anyOf`` to indirekcja, nie
    # zejście w głąb danych — nie zwiększamy tu licznika zagnieżdżenia,
    # bo wyczerpałby limit zanim dotrzemy do właściwego typu.
    if "$ref" in node:
        return example_for_schema(_resolve_ref(node["$ref"], document), document, depth)

    for key in ("example", "default"):
        if key in node:
            return node[key]

    for key in ("anyOf", "oneOf", "allOf"):
        for variant in node.get(key, []):
            if variant.get("type") != "null":
                value = example_for_schema(variant, document, depth)
                if value is not None:
                    return value

    if enum := node.get("enum"):
        return enum[0]

    node_type = node.get("type")
    if node_type == "object" or "properties" in node:
        properties = node.get("properties") or {}
        required = set(node.get("required") or [])
        # Najpierw pola wymagane — to one są istotne w przykładzie.
        ordered = sorted(properties.items(), key=lambda kv: (kv[0] not in required, kv[0]))
        return {
            name: example_for_schema(prop, document, depth + 1)
            for name, prop in ordered[:_MAX_EXAMPLE_FIELDS]
        }
    if node_type == "array":
        item = example_for_schema(node.get("items") or {}, document, depth + 1)
        return [item] if item is not None else []
    if node.get("format") == "uuid":
        return _PLACEHOLDER_UUID
    if node_type == "string" and node.get("format") in ("date-time", "date"):
        return "2026-01-15T10:00:00Z"

    return _PLACEHOLDER_BY_TYPE.get(node_type or "string", "przykladowa-wartosc")


def fill_path(path: str, parameters: list[dict[str, Any]], document: dict[str, Any]) -> str:
    """Podstawia wartości przykładowe pod parametry ścieżki."""
    filled = path
    for param in parameters:
        if param.get("in") != "path":
            continue
        value = example_for_schema(param.get("schema") or {}, document)
        filled = filled.replace("{" + param["name"] + "}", str(value))
    return filled


def _body_json(body: Any) -> str:
    return json.dumps(body, ensure_ascii=False, indent=2)


def generate_curl_snippet(
    method: str,
    url: str,
    *,
    body: Any = None,
    requires_auth: bool = True,
) -> str:
    lines = [f"curl -X {method.upper()} '{url}' \\"]
    if requires_auth:
        lines.append(f"  -H 'Authorization: Bearer {PLACEHOLDER_API_KEY}' \\")
    if body is not None:
        lines.append("  -H 'Content-Type: application/json' \\")
        compact = json.dumps(body, ensure_ascii=False)
        lines.append(f"  -d '{compact}'")
    else:
        lines[-1] = lines[-1].rstrip(" \\")
    return "\n".join(lines)


def generate_python_snippet(
    method: str,
    url: str,
    *,
    body: Any = None,
    requires_auth: bool = True,
) -> str:
    lines = ["import requests", ""]
    if requires_auth:
        lines.append(f'API_KEY = "{PLACEHOLDER_API_KEY}"  # Ustawienia → Klucze API')
        lines.append("")
    call = [f'response = requests.{method.lower()}(', f'    "{url}",']
    if requires_auth:
        call.append('    headers={"Authorization": f"Bearer {API_KEY}"},')
    if body is not None:
        call.append(f"    json={_body_json(body)},".replace("\n", "\n    "))
    call.append("    timeout=30,")
    call.append(")")
    lines.extend(call)
    lines.append("response.raise_for_status()")
    # Odpowiedzi 204 nie mają ciała — `.json()` by się wywrócił.
    lines.append("print(response.json() if response.content else response.status_code)")
    return "\n".join(lines)


def generate_js_snippet(
    method: str,
    url: str,
    *,
    body: Any = None,
    requires_auth: bool = True,
) -> str:
    lines = []
    if requires_auth:
        lines.append(f"const apiKey = '{PLACEHOLDER_API_KEY}'; // Ustawienia → Klucze API")
        lines.append("")
    options = [f"  method: '{method.upper()}',"]
    headers = []
    if requires_auth:
        headers.append("    Authorization: `Bearer ${apiKey}`,")
    if body is not None:
        headers.append("    'Content-Type': 'application/json',")
    if headers:
        options.append("  headers: {")
        options.extend(headers)
        options.append("  },")
    if body is not None:
        serialized = _body_json(body).replace("\n", "\n  ")
        options.append(f"  body: JSON.stringify({serialized}),")

    lines.append(f"const response = await fetch('{url}', {{")
    lines.extend(options)
    lines.append("});")
    lines.append("")
    lines.append("if (!response.ok) {")
    lines.append("  throw new Error(`TestGEN API: ${response.status}`);")
    lines.append("}")
    lines.append("console.log(await response.json());")
    return "\n".join(lines)


def build_code_samples(
    method: str,
    url: str,
    *,
    body: Any = None,
    requires_auth: bool = True,
) -> list[dict[str, str]]:
    """Lista ``x-code-samples`` w formacie rozumianym przez Swagger UI i ReDoc."""
    return [
        {
            "lang": "curl",
            "label": "curl",
            "source": generate_curl_snippet(method, url, body=body, requires_auth=requires_auth),
        },
        {
            "lang": "Python",
            "label": "Python (requests)",
            "source": generate_python_snippet(method, url, body=body, requires_auth=requires_auth),
        },
        {
            "lang": "JavaScript",
            "label": "JavaScript (fetch)",
            "source": generate_js_snippet(method, url, body=body, requires_auth=requires_auth),
        },
    ]
