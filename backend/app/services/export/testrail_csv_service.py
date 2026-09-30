"""Generator CSV zgodnego z importem TestRail — Story 6.8, AC2 (FR46).

Format: UTF-8 z BOM, separator średnikowy (polski standard), kolumny zgodne
z formatem importu TestRail: Title, Section, Priority, Type, Steps,
Expected Result + pola dodatkowe (Preconditions, References).
"""

from __future__ import annotations

import csv
import io
from typing import Any

from app.services.export.tms_common import (
    PRIORITY_TO_TMS,
    TESTRAIL_TYPE_DEFAULT,
    TYPE_TO_TESTRAIL,
    as_text,
    mapped_value,
)

# (nagłówek TestRail, klucz mapowania, domyślne pole TestGEN)
TESTRAIL_COLUMNS: list[tuple[str, str, str]] = [
    ("Title", "title", "title"),
    ("Section", "section", "module"),
    ("Priority", "priority", "priority"),
    ("Type", "type", "type"),
    ("Preconds", "preconditions", "preconditions"),
    ("Steps", "steps", "steps"),
    ("Expected Result", "expected_result", "expected_result"),
    ("References", "references", "tags"),
]


def _steps_text(value: Any) -> str:
    """Kroki jako lista numerowana (format kroków TestRail)."""
    if isinstance(value, list):
        return "\n".join(f"{i}. {step}" for i, step in enumerate(value, start=1))
    return as_text(value)


def render(
    rows: list[dict[str, Any]],
    field_mapping: dict[str, str] | None = None,
) -> bytes:
    """Renderuje test case'y do CSV importu TestRail."""
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\r\n",
    )
    writer.writerow([header for header, _, _ in TESTRAIL_COLUMNS])

    for row in rows:
        record: list[str] = []
        for _, tms_field, default_field in TESTRAIL_COLUMNS:
            value = mapped_value(row, tms_field, default_field, field_mapping)
            if tms_field == "priority":
                text = PRIORITY_TO_TMS.get(str(value), as_text(value))
            elif tms_field == "type":
                text = TYPE_TO_TESTRAIL.get(str(value), TESTRAIL_TYPE_DEFAULT)
            elif tms_field == "steps":
                text = _steps_text(value)
            elif tms_field == "references":
                text = ", ".join(value) if isinstance(value, list) else as_text(value)
            else:
                text = as_text(value)
            record.append(text)
        writer.writerow(record)

    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
