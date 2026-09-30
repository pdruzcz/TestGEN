"""CSRF rules (CWE-352, OWASP A01:2021) — Epic 4, Story 4.2.

Line-based detection cannot prove the *absence* of a CSRF token across a whole
form/handler, so these rules target high-confidence signals that CSRF protection
is explicitly disabled or bypassed.
"""

from app.services.security_scan.rules.base import (
    JAVA,
    JS,
    PY,
    RulePattern,
    VulnerabilityRule,
    rx,
)

CSRF_RULES: list[VulnerabilityRule] = [
    VulnerabilityRule(
        id="PY-CSRF-DISABLED",
        name="Ochrona CSRF wyłączona (Python)",
        vulnerability_type="csrf",
        cwe_id="CWE-352",
        owasp_category="A01:2021-Broken Access Control",
        severity="high",
        description="Jawne wyłączenie ochrony CSRF (csrf_exempt / WTF_CSRF_ENABLED=False).",
        recommendation="Nie wyłączaj CSRF dla endpointów zmieniających stan.",
        base_confidence=0.7,
        patterns=(
            RulePattern(
                regex=rx(r"@csrf_exempt|csrf_exempt\s*\(|WTF_CSRF_ENABLED\s*=\s*False|CSRF_ENABLED\s*=\s*False"),
                languages=PY,
                node_hint="CSRF exemption marker",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JAVA-CSRF-DISABLED",
        name="CSRF wyłączone w Spring Security",
        vulnerability_type="csrf",
        cwe_id="CWE-352",
        owasp_category="A01:2021-Broken Access Control",
        severity="high",
        description="Spring Security z .csrf().disable().",
        recommendation="Pozostaw ochronę CSRF włączoną lub użyj tokenów synchronizujących.",
        base_confidence=0.75,
        patterns=(
            RulePattern(
                regex=rx(r"\.csrf\s*\(\s*\)\s*\.\s*disable\s*\(|csrf\(\)\.ignoringAntMatchers"),
                languages=JAVA,
                node_hint="Spring Security config",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JS-CSRF-DISABLED",
        name="CSRF wyłączone (Express/JS)",
        vulnerability_type="csrf",
        cwe_id="CWE-352",
        owasp_category="A01:2021-Broken Access Control",
        severity="medium",
        description="Wyłączona ochrona CSRF lub stan-zmieniający fetch bez nagłówka CSRF.",
        recommendation="Włącz middleware CSRF i dołączaj token do żądań POST/PUT/DELETE.",
        base_confidence=0.55,
        patterns=(
            RulePattern(
                regex=rx(r"csrf\s*:\s*false|ignoreMethods\s*:\s*\[[^\]]*POST"),
                languages=JS,
                node_hint="CSRF middleware config",
            ),
        ),
    ),
]
