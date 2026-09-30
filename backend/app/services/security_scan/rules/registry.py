"""Central rule registry — Epic 4, Story 4.2.

Aggregates every category rule module and exposes language-filtered lookups used
by the SAST engine, plus a CWE index for reporting/aggregation (Epic 4 later
stories).
"""

from typing import Protocol

from app.services.security_scan.rules.authz_rules import AUTHZ_RULES
from app.services.security_scan.rules.base import VulnerabilityRule
from app.services.security_scan.rules.csrf_rules import CSRF_RULES
from app.services.security_scan.rules.input_validation_rules import (
    INPUT_VALIDATION_RULES,
)
from app.services.security_scan.rules.secrets_rules import SECRETS_RULES
from app.services.security_scan.rules.sqli_rules import SQLI_RULES
from app.services.security_scan.rules.xss_rules import XSS_RULES

# Order is stable so findings come out deterministically per line.
ALL_RULES: list[VulnerabilityRule] = [
    *SQLI_RULES,
    *XSS_RULES,
    *CSRF_RULES,
    *AUTHZ_RULES,
    *INPUT_VALIDATION_RULES,
    *SECRETS_RULES,
]


class IRuleRegistry(Protocol):
    def get_rules(self, language: str | None) -> list[VulnerabilityRule]: ...


class RuleRegistry:
    """Registry of all vulnerability rules with per-language filtering."""

    def __init__(self, rules: list[VulnerabilityRule] | None = None) -> None:
        self._rules = rules if rules is not None else ALL_RULES

    @property
    def rules(self) -> list[VulnerabilityRule]:
        return self._rules

    def get_rules(self, language: str | None) -> list[VulnerabilityRule]:
        """Return rules with at least one pattern applicable to ``language``."""
        return [r for r in self._rules if r.applies_to(language)]

    def get_rule_by_id(self, rule_id: str) -> VulnerabilityRule | None:
        return next((r for r in self._rules if r.id == rule_id), None)

    def get_rules_by_cwe(self, cwe_id: str) -> list[VulnerabilityRule]:
        return [r for r in self._rules if r.cwe_id == cwe_id]


_REGISTRY = RuleRegistry()


def get_registry() -> RuleRegistry:
    """Return the process-wide rule registry."""
    return _REGISTRY


def rules_for_language(language: str | None) -> list[VulnerabilityRule]:
    """Backwards-compatible helper (Story 4.1 API) delegating to the registry."""
    return _REGISTRY.get_rules(language)
