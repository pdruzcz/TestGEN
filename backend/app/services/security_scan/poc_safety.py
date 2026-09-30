"""PoC safety validator — Epic 4, Story 4.10.

Every proof-of-concept is checked here before it is shown to a user. The platform
only ever produces *non-destructive* demonstrations: payloads that read or reveal
data are allowed, but anything that could modify/delete data, touch the
filesystem destructively, control the host, or fetch a remote payload is blocked.
This keeps generated PoCs safe to paste into an authorised test of one's own app.
"""

import re
from dataclasses import dataclass, field

# Patterns that make a payload destructive / out of scope for a safe PoC.
# Matched case-insensitively against the payload, steps and expected effect.
_UNSAFE_PATTERNS: dict[str, str] = {
    r"\bDROP\s+(TABLE|DATABASE)\b": "Usuwanie obiektów bazy danych (DROP)",
    r"\bDELETE\s+FROM\b": "Modyfikacja/usuwanie danych (DELETE FROM)",
    r"\bTRUNCATE\b": "Czyszczenie tabeli (TRUNCATE)",
    r"\bUPDATE\s+\w+\s+SET\b": "Modyfikacja danych (UPDATE ... SET)",
    r"\bINSERT\s+INTO\b": "Wstawianie danych (INSERT INTO)",
    r"rm\s+-rf": "Usuwanie plików (rm -rf)",
    r"\bdel\s+/[sq]": "Usuwanie plików (del /s)",
    r"\bformat\b\s+[a-z]:": "Formatowanie dysku (format)",
    r"\bmkfs\b": "Formatowanie systemu plików (mkfs)",
    r"\b(shutdown|reboot|halt|poweroff)\b": "Operacje systemowe (shutdown/reboot)",
    r":\(\)\s*\{.*\};:": "Fork bomb",
    r"\bwget\b\s+https?://": "Pobieranie zdalnego ładunku (wget)",
    r"curl\s+.*-O\b": "Pobieranie zdalnego ładunku (curl -O)",
    r"\bcurl\b\s+https?://\S+\s*\|\s*(sh|bash)": "Wykonanie zdalnego skryptu (curl | sh)",
}

_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE), reason) for pattern, reason in _UNSAFE_PATTERNS.items()
]


@dataclass
class SafetyCheck:
    is_safe: bool
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _scan(text: str) -> list[str]:
    return [reason for pattern, reason in _COMPILED if pattern.search(text)]


def validate_text_safety(*parts: str | None) -> SafetyCheck:
    """Validate arbitrary PoC text fragments against the unsafe-pattern list."""
    haystack = "\n".join(p for p in parts if p)
    blocked = _scan(haystack)
    # Deduplicate while preserving order.
    seen: dict[str, None] = {}
    for reason in blocked:
        seen.setdefault(reason, None)
    reasons = list(seen)
    return SafetyCheck(is_safe=not reasons, blocked_reasons=reasons)
