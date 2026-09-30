"""Hardcoded secret rules (CWE-798, OWASP A07:2021) — Epic 4, Story 4.2."""

from app.services.security_scan.rules.base import (
    ALL,
    RulePattern,
    VulnerabilityRule,
    rx,
)

SECRETS_RULES: list[VulnerabilityRule] = [
    VulnerabilityRule(
        id="SECRET-HARDCODED",
        name="Zakodowany sekret (hasło/klucz/token)",
        vulnerability_type="hardcoded_secret",
        cwe_id="CWE-798",
        owasp_category="A07:2021-Identification and Authentication Failures",
        severity="high",
        description="Zakodowany na stałe sekret (hasło/klucz API/token) w kodzie źródłowym.",
        recommendation="Przenieś sekrety do zmiennych środowiskowych / menedżera sekretów.",
        base_confidence=0.55,
        patterns=(
            RulePattern(
                regex=rx(
                    r"(password|passwd|pwd|secret|api[_-]?key|apikey|token|access[_-]?key)"
                    r"\s*[:=]\s*[\"'][^\"'\s]{6,}[\"']"
                ),
                languages=ALL,
                node_hint="secret assignment",
            ),
        ),
    ),
    VulnerabilityRule(
        id="SECRET-PRIVATE-KEY",
        name="Klucz prywatny w repozytorium",
        vulnerability_type="hardcoded_secret",
        cwe_id="CWE-798",
        owasp_category="A02:2021-Cryptographic Failures",
        severity="critical",
        description="Klucz prywatny osadzony w repozytorium.",
        recommendation="Usuń klucz prywatny z repozytorium i zrotuj go.",
        base_confidence=0.9,
        patterns=(
            RulePattern(
                regex=rx(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
                languages=ALL,
                node_hint="PEM private key block",
            ),
        ),
    ),
    VulnerabilityRule(
        id="SECRET-AWS-KEY",
        name="Identyfikator klucza dostępu AWS",
        vulnerability_type="hardcoded_secret",
        cwe_id="CWE-798",
        owasp_category="A07:2021-Identification and Authentication Failures",
        severity="critical",
        description="Identyfikator klucza dostępu AWS (AKIA…) w kodzie.",
        recommendation="Usuń klucz, zrotuj go i używaj ról IAM / menedżera sekretów.",
        base_confidence=0.85,
        patterns=(
            RulePattern(
                regex=rx(r"\bAKIA[0-9A-Z]{16}\b"),
                languages=ALL,
                node_hint="AWS access key id",
            ),
        ),
    ),
    VulnerabilityRule(
        id="SECRET-JWT",
        name="Osadzony token JWT",
        vulnerability_type="hardcoded_secret",
        cwe_id="CWE-798",
        owasp_category="A07:2021-Identification and Authentication Failures",
        severity="high",
        description="Token JWT (eyJ…) zakodowany na stałe w kodzie.",
        recommendation="Nie przechowuj tokenów w kodzie; używaj bezpiecznego magazynu.",
        base_confidence=0.7,
        patterns=(
            RulePattern(
                regex=rx(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+"),
                languages=ALL,
                node_hint="JWT literal",
            ),
        ),
    ),
]
