"""Eksport JSON — Story 6.7, AC5.

Struktura zgodna z API (snake_case), pretty-printed, UTF-8 bez escapowania
polskich znaków.
"""

import json


def render(report: dict, report_type: str = "both") -> bytes:
    payload = {"report_type": report_type, **report}
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
