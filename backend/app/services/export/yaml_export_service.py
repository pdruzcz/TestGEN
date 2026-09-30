"""Eksport YAML — Story 6.7, AC6.

Struktura zgodna z JSON (snake_case), czytelne formatowanie blokowe,
polskie znaki bez escapowania (allow_unicode).
"""

import yaml


def render(report: dict, report_type: str = "both") -> bytes:
    payload = {"report_type": report_type, **report}
    return yaml.safe_dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    ).encode("utf-8")
