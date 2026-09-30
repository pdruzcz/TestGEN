"""Broken authorization / IDOR rules (CWE-862/639, OWASP A01:2021) — Story 4.2.

Authorization is contextual, so line-based rules target two high-signal shapes:
explicit auth bypass markers and direct object lookups keyed straight off request
input (a strong IDOR tell).
"""

from app.services.security_scan.rules.base import (
    JAVA,
    JS,
    PY,
    RulePattern,
    VulnerabilityRule,
    rx,
)

AUTHZ_RULES: list[VulnerabilityRule] = [
    VulnerabilityRule(
        id="PY-IDOR-LOOKUP",
        name="Odwołanie do obiektu po ID z requestu (IDOR)",
        vulnerability_type="idor",
        cwe_id="CWE-639",
        owasp_category="A01:2021-Broken Access Control",
        severity="high",
        description="Pobranie obiektu po identyfikatorze z requestu bez sprawdzenia właściciela.",
        recommendation="Weryfikuj własność/uprawnienia (np. filter(owner=current_user)).",
        base_confidence=0.5,
        patterns=(
            RulePattern(
                regex=rx(
                    r"objects\.(get|filter)\s*\([^)]*=\s*request\.|"
                    r"get_object_or_404\s*\([^)]*request\.|"
                    r"\.query\.get\s*\(\s*request\."
                ),
                languages=PY,
                node_hint="ORM lookup keyed by request input",
            ),
        ),
    ),
    VulnerabilityRule(
        id="PY-AUTH-BYPASS",
        name="Jawny bypass autoryzacji (Python)",
        vulnerability_type="broken_authz",
        cwe_id="CWE-862",
        owasp_category="A01:2021-Broken Access Control",
        severity="high",
        description="Wyłączone uwierzytelnianie/uprawnienia (AllowAny / login_required usunięty).",
        recommendation="Stosuj zasadę domyślnego odrzucania; wymagaj uwierzytelnienia.",
        base_confidence=0.55,
        patterns=(
            RulePattern(
                regex=rx(r"permission_classes\s*=\s*\[\s*AllowAny|authentication_classes\s*=\s*\[\s*\]"),
                languages=PY,
                node_hint="DRF permission override",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JAVA-IDOR-LOOKUP",
        name="findById z parametrem requestu (IDOR)",
        vulnerability_type="idor",
        cwe_id="CWE-639",
        owasp_category="A01:2021-Broken Access Control",
        severity="high",
        description="repository.findById z identyfikatorem z requestu bez kontroli właściciela.",
        recommendation="Sprawdź uprawnienia/własność przed zwróceniem obiektu.",
        base_confidence=0.45,
        patterns=(
            RulePattern(
                regex=rx(r"\.findById\s*\(\s*(request|@PathVariable|id\s*\))"),
                languages=JAVA,
                node_hint="repository findById",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JS-AUTH-BYPASS",
        name="Jawny bypass autoryzacji (JS/TS)",
        vulnerability_type="broken_authz",
        cwe_id="CWE-862",
        owasp_category="A01:2021-Broken Access Control",
        severity="high",
        description="Pominięcie middleware autoryzacji (next() bez sprawdzenia roli/uprawnień).",
        recommendation="Egzekwuj autoryzację w middleware przed dostępem do zasobu.",
        base_confidence=0.4,
        patterns=(
            RulePattern(
                regex=rx(r"//\s*(TODO|FIXME)[^\n]*\bauth|requireAuth\s*:\s*false"),
                languages=JS,
                node_hint="auth bypass marker",
            ),
        ),
    ),
]
