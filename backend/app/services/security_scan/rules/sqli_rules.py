"""SQL injection rules (CWE-89, OWASP A03:2021) — Epic 4, Story 4.2."""

from app.services.security_scan.rules.base import (
    CS,
    JAVA,
    JS,
    PY,
    RulePattern,
    VulnerabilityRule,
    rx,
)

SQLI_RULES: list[VulnerabilityRule] = [
    VulnerabilityRule(
        id="SQLI-STRING-CONCAT",
        name="SQL budowane przez konkatenację/interpolację",
        vulnerability_type="sql_injection",
        cwe_id="CWE-89",
        owasp_category="A03:2021-Injection",
        severity="critical",
        description="Budowanie zapytania SQL przez konkatenację/format z danymi wejściowymi.",
        recommendation="Używaj zapytań parametryzowanych / ORM zamiast sklejania łańcuchów.",
        base_confidence=0.65,
        patterns=(
            # Order-independent: a quoted SQL DML keyword *and* an interpolation
            # / concatenation marker on the same line.
            RulePattern(
                # The format-operator marker is ["']\s*% (i.e. "...%s" % args), not a
                # bare %s placeholder inside the string — the latter is parametrized
                # and safe, so it must not match.
                regex=rx(
                    r"(?=.*[\"'])"
                    r"(?=.*\b(SELECT|INSERT|UPDATE|DELETE)\b)"
                    r"(?=.*(\+|\.format\s*\(|[\"']\s*%|f[\"']|\$\{|\{[A-Za-z_]))"
                ),
                node_hint="string-built SQL query",
            ),
        ),
    ),
    VulnerabilityRule(
        id="PY-CURSOR-FSTRING",
        name="cursor.execute z f-stringiem/format",
        vulnerability_type="sql_injection",
        cwe_id="CWE-89",
        owasp_category="A03:2021-Injection",
        severity="critical",
        description="cursor.execute z f-stringiem/format zamiast parametrów.",
        recommendation="Przekaż parametry jako drugi argument execute(query, params).",
        base_confidence=0.7,
        patterns=(
            RulePattern(
                # f-string or explicit concatenation in execute(); a bare %s
                # placeholder with a params tuple is parametrized and safe.
                regex=rx(r"\.execute\s*\(\s*(f[\"']|[\"'][^)]*\+|[\"'][^)]*%[^,)]*$)"),
                languages=PY,
                node_hint="DB-API execute call",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JAVA-STATEMENT-CONCAT",
        name="Statement.execute z konkatenacją",
        vulnerability_type="sql_injection",
        cwe_id="CWE-89",
        owasp_category="A03:2021-Injection",
        severity="critical",
        description="Statement.execute*/JdbcTemplate z konkatenowanym zapytaniem zamiast PreparedStatement.",
        recommendation="Użyj PreparedStatement z parametrami (?), nie konkatenacji.",
        base_confidence=0.7,
        patterns=(
            RulePattern(
                regex=rx(r"\.execute(Query|Update)?\s*\(\s*[\"'].*\+|createStatement\s*\("),
                languages=JAVA,
                node_hint="JDBC Statement",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JS-QUERY-CONCAT",
        name="Zapytanie SQL z interpolacją w JS/TS",
        vulnerability_type="sql_injection",
        cwe_id="CWE-89",
        owasp_category="A03:2021-Injection",
        severity="critical",
        description="db.query/connection.query z template literal lub konkatenacją.",
        recommendation="Używaj zapytań parametryzowanych (placeholdery ?), nie interpolacji.",
        base_confidence=0.65,
        patterns=(
            RulePattern(
                regex=rx(r"\.query\s*\(\s*([`\"'].*\$\{|[\"'].*\+)"),
                languages=JS,
                node_hint="db driver query call",
            ),
        ),
    ),
    VulnerabilityRule(
        id="CS-SQLCOMMAND-CONCAT",
        name="SqlCommand z konkatenacją",
        vulnerability_type="sql_injection",
        cwe_id="CWE-89",
        owasp_category="A03:2021-Injection",
        severity="critical",
        description="SqlCommand budowany z konkatenacji zamiast parametrów.",
        recommendation="Użyj SqlParameter / parametrów @ zamiast konkatenacji.",
        base_confidence=0.7,
        patterns=(
            RulePattern(
                regex=rx(r"new\s+SqlCommand\s*\(\s*[\"'].*\+|ExecuteReader\s*\(\s*[\"'].*\+"),
                languages=CS,
                node_hint="ADO.NET SqlCommand",
            ),
        ),
    ),
]
