"""C# taint definitions — Epic 4, Story 4.3."""

from app.services.security_scan.taint_definitions.base import (
    CS,
    TaintSanitizer,
    TaintSink,
    TaintSource,
    rx,
)

CSHARP_SOURCES: tuple[TaintSource, ...] = (
    TaintSource(
        name="Request.Form / QueryString",
        patterns=(
            rx(r"Request\.(Form|QueryString|Params|Cookies|Headers)"),
            rx(r"Request\[\s*[\"']"),
        ),
        language=CS,
        taint_type="user_input",
    ),
    TaintSource(
        name="ModelState / model binding",
        patterns=(rx(r"\bModelState\b"),),
        language=CS,
        taint_type="user_input",
    ),
    TaintSource(
        name="environment variable",
        patterns=(rx(r"Environment\.GetEnvironmentVariable\s*\("),),
        language=CS,
        taint_type="env_input",
    ),
)

CSHARP_SINKS: tuple[TaintSink, ...] = (
    TaintSink(
        name="SqlCommand.Execute (SQL)",
        patterns=(
            rx(r"new\s+SqlCommand\s*\("),
            rx(r"\.ExecuteReader\s*\("),
            rx(r"\.ExecuteNonQuery\s*\("),
        ),
        language=CS,
        sink_type="sql",
        vulnerability_type="sql_injection",
        cwe_id="CWE-89",
        severity="high",
    ),
    TaintSink(
        name="Process.Start (exec)",
        patterns=(rx(r"Process\.Start\s*\("),),
        language=CS,
        sink_type="exec",
        vulnerability_type="command_injection",
        cwe_id="CWE-78",
        severity="critical",
    ),
    TaintSink(
        name="Response.Write (HTML)",
        patterns=(rx(r"Response\.Write\s*\("),),
        language=CS,
        sink_type="html",
        vulnerability_type="xss",
        cwe_id="CWE-79",
        severity="medium",
    ),
)

CSHARP_SANITIZERS: tuple[TaintSanitizer, ...] = (
    TaintSanitizer(
        name="SqlParameter",
        patterns=(rx(r"new\s+SqlParameter\s*\("), rx(r"\.Parameters\.Add")),
        language=CS,
        protects_against=frozenset({"sql"}),
    ),
    TaintSanitizer(
        name="HttpUtility.HtmlEncode",
        patterns=(rx(r"HtmlEncode\s*\("), rx(r"HttpUtility\.HtmlEncode\s*\(")),
        language=CS,
        protects_against=frozenset({"html"}),
    ),
    TaintSanitizer(
        name="int.Parse / Convert.ToInt32",
        patterns=(rx(r"int\.Parse\s*\("), rx(r"Convert\.ToInt32\s*\(")),
        language=CS,
        protects_against=frozenset({"sql", "exec", "html"}),
    ),
)
