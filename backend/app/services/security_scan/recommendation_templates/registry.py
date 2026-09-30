"""Recommendation template registry — Epic 4, Story 4.9.

Maps a (vulnerability_type, language, framework) triple to a native remediation
template. Each template carries the human-facing problem / risk / fix text plus a
fixed-code snippet in the project's language. Lookups degrade gracefully: an
unknown framework falls back to the language default, and an unknown language to
a generic template for the vulnerability class.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    problem_description: str
    risk_description: str
    fix_description: str
    fixed_code_snippet: str
    language: str = "generic"
    framework: str | None = None


# Per-vulnerability template tables, keyed by language → framework. ``None`` is
# the language's default framework.
_TEMPLATES: dict[str, dict[str, dict[str | None, Template]]] = {}


def register(vulnerability_type: str, language: str, framework: str | None, template: Template) -> None:
    _TEMPLATES.setdefault(vulnerability_type, {}).setdefault(language, {})[framework] = template


class TemplateRegistry:
    """Resolves the best-matching native remediation template."""

    @staticmethod
    def get_template(
        vulnerability_type: str,
        language: str | None,
        framework: str | None = None,
    ) -> Template | None:
        by_lang = _TEMPLATES.get(vulnerability_type)
        if not by_lang:
            return None

        lang = (language or "").lower()
        candidates = by_lang.get(lang)
        if candidates is None:
            # Fall back to a generic, language-agnostic entry if present.
            candidates = by_lang.get("generic")
        if candidates is None:
            # Otherwise pick any language so the caller still gets guidance.
            candidates = next(iter(by_lang.values()))

        if framework and framework.lower() in candidates:
            return candidates[framework.lower()]
        return candidates.get(None) or next(iter(candidates.values()))

    @staticmethod
    def has(vulnerability_type: str) -> bool:
        return vulnerability_type in _TEMPLATES
