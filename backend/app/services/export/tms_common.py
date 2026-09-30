"""Wspólne narzędzia eksportu test case'ów do TMS — Story 6.8 (FR46).

Normalizacja pól TestCase do płaskiego słownika (snake_case) używanego przez
generatory TestRail CSV / Jira Xray XML / Ogólny JSON oraz mapowanie
priorytetów i typów na słowniki docelowych systemów TMS.
"""

from __future__ import annotations

import re
from typing import Any

# Mapowanie priorytetów TestGEN → TestRail/Xray (AC2)
PRIORITY_TO_TMS: dict[str, str] = {
    "CRITICAL": "Critical",
    "HIGH": "High",
    "MEDIUM": "Medium",
    "LOW": "Low",
}

# Mapowanie typów TestGEN → typy TestRail (AC2)
TYPE_TO_TESTRAIL: dict[str, str] = {
    "SECURITY": "Security",
    "PERFORMANCE": "Performance",
    "ACCESSIBILITY": "Usability",
}
TESTRAIL_TYPE_DEFAULT = "Functional"

# Mapowanie typów TestGEN → typy testów Xray (AC3)
TYPE_TO_XRAY: dict[str, str] = {
    "SECURITY": "Security",
    "PERFORMANCE": "Performance",
}
XRAY_TYPE_DEFAULT = "Generic"

_POLISH_MAP = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def slugify(name: str) -> str:
    """Slug do nazwy pliku: `Mój Projekt!` → `moj-projekt` (AC7)."""
    ascii_name = name.translate(_POLISH_MAP).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    return slug or "projekt"


def _enum_value(value: Any) -> str:
    """Zwraca wartość Enum lub string bez zmian."""
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def steps_list(steps: Any) -> list[str]:
    """Kroki z JSONB (konwencja {items: [...]}), stringa lub listy."""
    if steps is None:
        return []
    if isinstance(steps, dict):
        items = steps.get("items") or []
        return [str(item) for item in items]
    if isinstance(steps, list):
        return [str(item) for item in steps]
    text = str(steps).strip()
    return [line.strip() for line in text.splitlines() if line.strip()]


def test_case_row(tc: Any) -> dict[str, Any]:
    """Płaski słownik pól test case'a używany przez generatory TMS."""
    module = tc.source_class or tc.source_function or ""
    return {
        "id": str(tc.id),
        "title": tc.title or "",
        "description": tc.description or "",
        "preconditions": tc.preconditions or "",
        "steps": steps_list(tc.steps),
        "expected_result": tc.expected_result or "",
        "priority": _enum_value(tc.priority),
        "type": _enum_value(tc.type),
        "framework": _enum_value(tc.framework),
        "status": _enum_value(tc.status),
        "module": module,
        "tags": list(tc.tags or []),
        "source_function": tc.source_function or "",
        "source_class": tc.source_class or "",
        "source_endpoint": tc.source_endpoint or "",
    }


def mapped_value(
    row: dict[str, Any],
    tms_field: str,
    default_field: str,
    field_mapping: dict[str, str] | None,
) -> Any:
    """Wartość pola TestGEN przypisanego do pola TMS (AC5 — mapowanie pól)."""
    source_field = (field_mapping or {}).get(tms_field) or default_field
    return row.get(source_field, "")


def as_text(value: Any) -> str:
    """Renderuje wartość (string/lista) do tekstu jednej komórki."""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value or "")
