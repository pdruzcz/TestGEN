"""Rule framework primitives — Epic 4, Story 4.2.

Vulnerability rules are declarative data: a :class:`VulnerabilityRule` carries the
metadata (CWE, OWASP, severity) plus one or more :class:`RulePattern` matchers.
Native matching runs regex over raw source lines (tree-sitter is optional and not
guaranteed present), scoped per language to keep the "AST-aware" contract through
language targeting. Story 4.1 shipped a flat baseline list; Story 4.2 promotes it
to a registry of per-category rule modules.
"""

import re
from dataclasses import dataclass, field

# Language groups shared by the rule modules.
PY = frozenset({"python"})
JS = frozenset({"javascript", "typescript"})
JAVA = frozenset({"java"})
C = frozenset({"c", "cpp", "c++"})
CS = frozenset({"csharp", "c#"})
ALL: frozenset[str] = frozenset()


def rx(pattern: str) -> re.Pattern:
    """Compile a case-insensitive pattern (the default for SAST matchers)."""
    return re.compile(pattern, re.IGNORECASE)


@dataclass(frozen=True)
class RulePattern:
    """A single matcher within a rule.

    ``languages`` empty means the pattern applies to every language. The optional
    ``node_hint`` documents the AST construct the regex approximates (descriptive
    only — matching is line/regex based).
    """

    regex: re.Pattern
    languages: frozenset[str] = ALL
    confidence_weight: float = 0.0
    node_hint: str | None = None

    def applies_to(self, language: str | None) -> bool:
        if not self.languages:
            return True
        if language is None:
            return True
        return language.lower() in self.languages


@dataclass(frozen=True)
class VulnerabilityRule:
    """A declarative vulnerability detection rule."""

    id: str
    name: str
    vulnerability_type: str
    cwe_id: str
    owasp_category: str
    severity: str  # critical/high/medium/low/info
    description: str
    patterns: tuple[RulePattern, ...]
    recommendation: str | None = None
    base_confidence: float = 0.6

    @property
    def languages(self) -> frozenset[str]:
        """Union of every pattern's language scope ('' if any pattern is global)."""
        scopes = [p.languages for p in self.patterns]
        if any(not s for s in scopes):
            return ALL
        return frozenset().union(*scopes) if scopes else ALL

    def applies_to(self, language: str | None) -> bool:
        return any(p.applies_to(language) for p in self.patterns)

    def patterns_for_language(self, language: str | None) -> list[RulePattern]:
        return [p for p in self.patterns if p.applies_to(language)]


# Severity ranking used by the engine for ordering/merging.
SEVERITY_ORDER: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
}


@dataclass
class RawFinding:
    """An engine-internal finding before persistence."""

    vulnerability_type: str
    severity: str
    description: str
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    code_snippet: str | None = None
    confidence: float = 0.6
    cwe_id: str | None = None
    owasp_category: str | None = None
    recommendation: str | None = None
    source: str = "native"
    rule_id: str | None = None
    metadata: dict = field(default_factory=dict)
