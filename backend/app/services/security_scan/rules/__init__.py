"""SAST rule package — Epic 4, Stories 4.1-4.2.

Re-exports the rule framework primitives and registry so callers can keep using
``app.services.security_scan.rules`` as a stable import surface.
"""

from app.services.security_scan.rules.base import (
    ALL,
    SEVERITY_ORDER,
    RawFinding,
    RulePattern,
    VulnerabilityRule,
)
from app.services.security_scan.rules.cwe_owasp_mapping import (
    CWE_OWASP_MAPPING,
    cwe_for,
    owasp_for,
    severity_for,
)
from app.services.security_scan.rules.registry import (
    ALL_RULES,
    IRuleRegistry,
    RuleRegistry,
    get_registry,
    rules_for_language,
)

__all__ = [
    "ALL",
    "ALL_RULES",
    "CWE_OWASP_MAPPING",
    "SEVERITY_ORDER",
    "IRuleRegistry",
    "RawFinding",
    "RulePattern",
    "RuleRegistry",
    "VulnerabilityRule",
    "cwe_for",
    "get_registry",
    "owasp_for",
    "rules_for_language",
    "severity_for",
]
