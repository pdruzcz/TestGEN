"""Java taint definitions — Epic 4, Story 4.3."""

from app.services.security_scan.taint_definitions.base import (
    JAVA,
    TaintSanitizer,
    TaintSink,
    TaintSource,
    rx,
)

JAVA_SOURCES: tuple[TaintSource, ...] = (
    TaintSource(
        name="HttpServletRequest",
        patterns=(
            rx(r"request\.getParameter\s*\("),
            rx(r"request\.getHeader\s*\("),
            rx(r"request\.getQueryString\s*\("),
        ),
        language=JAVA,
        taint_type="user_input",
    ),
    TaintSource(
        name="@RequestParam / @PathVariable",
        patterns=(rx(r"@RequestParam"), rx(r"@PathVariable")),
        language=JAVA,
        taint_type="user_input",
    ),
    TaintSource(
        name="environment variable",
        patterns=(rx(r"System\.getenv\s*\("),),
        language=JAVA,
        taint_type="env_input",
    ),
)

JAVA_SINKS: tuple[TaintSink, ...] = (
    TaintSink(
        name="Statement.execute (SQL)",
        patterns=(
            rx(r"\.execute(Query|Update)?\s*\("),
            rx(r"createStatement\s*\("),
        ),
        language=JAVA,
        sink_type="sql",
        vulnerability_type="sql_injection",
        cwe_id="CWE-89",
        severity="high",
    ),
    TaintSink(
        name="Runtime.exec / ProcessBuilder",
        patterns=(rx(r"Runtime\.getRuntime\(\)\.exec\s*\("), rx(r"new\s+ProcessBuilder\s*\(")),
        language=JAVA,
        sink_type="exec",
        vulnerability_type="command_injection",
        cwe_id="CWE-78",
        severity="critical",
    ),
    TaintSink(
        name="response.getWriter (HTML)",
        patterns=(rx(r"\.getWriter\s*\(\s*\)\.(print|write)"), rx(r"\.println\s*\(")),
        language=JAVA,
        sink_type="html",
        vulnerability_type="xss",
        cwe_id="CWE-79",
        severity="medium",
    ),
)

JAVA_SANITIZERS: tuple[TaintSanitizer, ...] = (
    TaintSanitizer(
        name="PreparedStatement",
        patterns=(rx(r"prepareStatement\s*\("), rx(r"setString\s*\(")),
        language=JAVA,
        protects_against=frozenset({"sql"}),
    ),
    TaintSanitizer(
        name="ESAPI / OWASP encoder",
        patterns=(rx(r"ESAPI\.encoder\(\)"), rx(r"Encode\.forHtml\s*\(")),
        language=JAVA,
        protects_against=frozenset({"html"}),
    ),
    TaintSanitizer(
        name="Integer.parseInt",
        patterns=(rx(r"Integer\.parseInt\s*\("), rx(r"Long\.parseLong\s*\(")),
        language=JAVA,
        protects_against=frozenset({"sql", "exec", "html"}),
    ),
)
