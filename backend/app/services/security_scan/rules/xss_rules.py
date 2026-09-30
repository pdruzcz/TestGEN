"""XSS rules (CWE-79, OWASP A03:2021) — Epic 4, Story 4.2."""

from app.services.security_scan.rules.base import (
    CS,
    JAVA,
    JS,
    PY,
    RulePattern,
    VulnerabilityRule,
    rx,
)

XSS_RULES: list[VulnerabilityRule] = [
    VulnerabilityRule(
        id="JS-DOM-SINK",
        name="Niebezpieczny sink DOM (innerHTML/document.write)",
        vulnerability_type="xss",
        cwe_id="CWE-79",
        owasp_category="A03:2021-Injection",
        severity="high",
        description="Przypisanie do innerHTML/document.write/$.html danymi użytkownika (XSS).",
        recommendation="Używaj textContent lub sanitizacji (DOMPurify).",
        base_confidence=0.55,
        patterns=(
            RulePattern(
                regex=rx(
                    r"\.innerHTML\s*=|\.outerHTML\s*=|document\.write\s*\(|"
                    r"\$\([^)]*\)\.html\s*\(|insertAdjacentHTML\s*\("
                ),
                languages=JS,
                node_hint="DOM HTML sink",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JS-FRAMEWORK-RAW-HTML",
        name="Renderowanie surowego HTML w frameworku (React/Vue/Angular)",
        vulnerability_type="xss",
        cwe_id="CWE-79",
        owasp_category="A03:2021-Injection",
        severity="high",
        description="dangerouslySetInnerHTML / v-html / bypassSecurityTrustHtml z danymi użytkownika.",
        recommendation="Unikaj surowego HTML; sanityzuj przed renderowaniem.",
        base_confidence=0.6,
        patterns=(
            RulePattern(
                regex=rx(r"dangerouslySetInnerHTML|v-html\s*=|bypassSecurityTrust(Html|Script)"),
                languages=JS,
                node_hint="framework raw-html binding",
            ),
        ),
    ),
    VulnerabilityRule(
        id="PY-TEMPLATE-RAW",
        name="Niesanityzowane wyjście w szablonie Python",
        vulnerability_type="xss",
        cwe_id="CWE-79",
        owasp_category="A03:2021-Injection",
        severity="high",
        description="render_template_string/Markup z danymi użytkownika lub wyłączone auto-escaping.",
        recommendation="Włącz auto-escaping; nie używaj Markup() na danych użytkownika.",
        base_confidence=0.55,
        patterns=(
            RulePattern(
                regex=rx(r"render_template_string\s*\(|\bMarkup\s*\(|\|\s*safe\b|autoescape\s*=\s*False"),
                languages=PY,
                node_hint="server-side template sink",
            ),
        ),
    ),
    VulnerabilityRule(
        id="JAVA-RESPONSE-WRITE",
        name="Bezpośredni zapis do response (Java)",
        vulnerability_type="xss",
        cwe_id="CWE-79",
        owasp_category="A03:2021-Injection",
        severity="high",
        description="response.getWriter().write/print z danymi użytkownika bez escapowania.",
        recommendation="Escapuj dane (OWASP Encoder) przed zapisem do odpowiedzi.",
        base_confidence=0.5,
        patterns=(
            RulePattern(
                regex=rx(r"getWriter\s*\(\s*\)\s*\.\s*(write|print)|out\.print(ln)?\s*\("),
                languages=JAVA,
                node_hint="servlet response writer",
            ),
        ),
    ),
    VulnerabilityRule(
        id="CS-RESPONSE-RAW",
        name="Response.Write / Html.Raw (C#)",
        vulnerability_type="xss",
        cwe_id="CWE-79",
        owasp_category="A03:2021-Injection",
        severity="high",
        description="Response.Write/Html.Raw z danymi użytkownika bez HtmlEncode.",
        recommendation="Użyj HttpUtility.HtmlEncode / @Html.Encode.",
        base_confidence=0.55,
        patterns=(
            RulePattern(
                regex=rx(r"Response\.Write\s*\(|Html\.Raw\s*\("),
                languages=CS,
                node_hint="ASP.NET raw output",
            ),
        ),
    ),
]
