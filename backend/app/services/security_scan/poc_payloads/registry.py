"""PoC payload registry — Epic 4, Story 4.10.

Holds safe, canonical proof-of-concept payloads keyed by vulnerability type. Each
``PayloadTemplate`` is a non-destructive demonstration (read/reveal only); the
``safe`` flag lets a module record a well-known *destructive* example purely for
documentation while keeping it out of the served set.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PayloadTemplate:
    payload: str
    reproduction_steps: tuple[str, ...]
    expected_effect: str
    safe: bool = True
    label: str = ""


_PAYLOADS: dict[str, list[PayloadTemplate]] = {}


def register(vulnerability_type: str, template: PayloadTemplate) -> None:
    _PAYLOADS.setdefault(vulnerability_type, []).append(template)


class PayloadRegistry:
    """Resolves safe payload templates for a vulnerability type."""

    @staticmethod
    def get_payloads(vulnerability_type: str, include_unsafe: bool = False) -> list[PayloadTemplate]:
        templates = _PAYLOADS.get(vulnerability_type, [])
        if include_unsafe:
            return list(templates)
        return [t for t in templates if t.safe]

    @staticmethod
    def first_safe(vulnerability_type: str) -> PayloadTemplate | None:
        safe = PayloadRegistry.get_payloads(vulnerability_type)
        return safe[0] if safe else None

    @staticmethod
    def has(vulnerability_type: str) -> bool:
        return vulnerability_type in _PAYLOADS
