"""Generator ogólnego JSON test case'ów — Story 6.8, AC4 (FR46).

Struktura: id, title, description, steps[], priority, type, module, tags —
snake_case, pretty-printed, UTF-8.
"""

from __future__ import annotations

import json
from typing import Any

from app.services.export.tms_common import mapped_value


def render(
    rows: list[dict[str, Any]],
    field_mapping: dict[str, str] | None = None,
) -> bytes:
    """Renderuje test case'y do ogólnego JSON (struktura zgodna z API)."""
    payload = []
    for row in rows:
        steps = mapped_value(row, "steps", "steps", field_mapping)
        payload.append(
            {
                "id": row.get("id", ""),
                "title": str(mapped_value(row, "title", "title", field_mapping)),
                "description": str(
                    mapped_value(row, "description", "description", field_mapping)
                ),
                "steps": steps if isinstance(steps, list) else [str(steps)],
                "expected_result": str(
                    mapped_value(
                        row, "expected_result", "expected_result", field_mapping
                    )
                ),
                "priority": row.get("priority", ""),
                "type": row.get("type", ""),
                "module": str(mapped_value(row, "module", "module", field_mapping)),
                "tags": row.get("tags", []),
            }
        )

    return json.dumps(
        {"test_cases": payload, "total": len(payload)},
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
