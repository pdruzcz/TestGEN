"""LLM-based security analyzers — Story 4.13 (dual-path: LLM engine).

Each analyzer wraps the LLM gateway to find vulnerabilities that the
deterministic native engines miss: logical security bugs, missing access
controls, framework-specific issues, race conditions / TOCTOU and holistic
configuration problems. Responses are parsed into the engine-internal
``RawFinding`` type (``source="llm"``) so they merge cleanly with native
findings in :mod:`app.services.security_scan.dual_path_orchestrator`.
"""

import json

from app.services.security_scan.rules import SEVERITY_ORDER


def extract_json_array(content: str) -> list:
    """Best-effort extraction of a JSON array from an LLM response.

    Tolerates markdown code fences and surrounding prose; returns ``[]`` when
    no valid array can be parsed (the LLM path must never raise).
    """
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text[3:] else text.strip("`")
        text = text.removeprefix("json").strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        items = json.loads(text[start : end + 1])
    except (ValueError, json.JSONDecodeError):
        return []
    return items if isinstance(items, list) else []


def normalize_severity(value: object, default: str = "medium") -> str:
    """Clamp an LLM-provided severity label to a known level."""
    severity = str(value).lower() if value is not None else default
    return severity if severity in SEVERITY_ORDER else default


__all__ = ["extract_json_array", "normalize_severity"]
