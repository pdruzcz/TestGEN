"""Taint definition primitives — Epic 4, Story 4.3.

Declarative source/sink/sanitizer definitions used by the taint analyzer. As with
the SAST rules (Stories 4.1-4.2) matching is regex/line based — tree-sitter is not
guaranteed present, so the "AST" contract is approximated through language scoping
and pattern targeting. Each definition carries compiled patterns (via :func:`rx`).
"""

import re
from dataclasses import dataclass

# Re-use the rule framework's language groups and pattern compiler so taint and
# SAST share one notion of "which language does this apply to".
from app.services.security_scan.rules.base import (  # noqa: F401
    ALL,
    CS,
    JAVA,
    JS,
    PY,
    C,
    rx,
)


@dataclass(frozen=True)
class TaintSource:
    """A producer of tainted (attacker-controlled) data.

    ``taint_type`` describes the provenance (user_input/file_input/env_input) and
    is surfaced in the taint path for context.
    """

    name: str
    patterns: tuple[re.Pattern, ...]
    language: frozenset[str]
    taint_type: str  # user_input / file_input / env_input

    def matches(self, line: str) -> bool:
        return any(p.search(line) for p in self.patterns)

    def applies_to(self, language: str | None) -> bool:
        if not self.language:
            return True
        if language is None:
            return True
        return language.lower() in self.language


@dataclass(frozen=True)
class TaintSink:
    """A dangerous operation where tainted data must not arrive unsanitized."""

    name: str
    patterns: tuple[re.Pattern, ...]
    language: frozenset[str]
    sink_type: str  # sql / html / exec / file / log
    vulnerability_type: str
    cwe_id: str
    severity: str  # critical / high / medium / low

    def matches(self, line: str) -> bool:
        return any(p.search(line) for p in self.patterns)

    def applies_to(self, language: str | None) -> bool:
        if not self.language:
            return True
        if language is None:
            return True
        return language.lower() in self.language


@dataclass(frozen=True)
class TaintSanitizer:
    """A cleansing operation. ``protects_against`` lists the sink types it covers.

    Adequacy is sink-type specific: ``html.escape`` protects ``html`` but not
    ``sql``, so a path source -> html.escape -> SQL sink is still vulnerable.
    """

    name: str
    patterns: tuple[re.Pattern, ...]
    language: frozenset[str]
    protects_against: frozenset[str]

    def matches(self, line: str) -> bool:
        return any(p.search(line) for p in self.patterns)

    def applies_to(self, language: str | None) -> bool:
        if not self.language:
            return True
        if language is None:
            return True
        return language.lower() in self.language

    def protects(self, sink_type: str) -> bool:
        return sink_type in self.protects_against


# Severity by sink type — exec is the most dangerous (RCE), logs the least.
SINK_SEVERITY: dict[str, str] = {
    "exec": "critical",
    "sql": "high",
    "html": "medium",
    "file": "medium",
    "log": "low",
}
