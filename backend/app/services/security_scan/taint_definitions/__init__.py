"""Taint definitions package — Epic 4, Story 4.3.

Aggregates the per-language source/sink/sanitizer definitions and exposes a
language-scoped lookup so the taint analyzer can fetch exactly the definitions
that apply to a file's language.
"""

from app.services.security_scan.taint_definitions.base import (
    SINK_SEVERITY,
    TaintSanitizer,
    TaintSink,
    TaintSource,
)
from app.services.security_scan.taint_definitions.cpp_definitions import (
    CPP_SANITIZERS,
    CPP_SINKS,
    CPP_SOURCES,
)
from app.services.security_scan.taint_definitions.csharp_definitions import (
    CSHARP_SANITIZERS,
    CSHARP_SINKS,
    CSHARP_SOURCES,
)
from app.services.security_scan.taint_definitions.java_definitions import (
    JAVA_SANITIZERS,
    JAVA_SINKS,
    JAVA_SOURCES,
)
from app.services.security_scan.taint_definitions.javascript_definitions import (
    JS_SANITIZERS,
    JS_SINKS,
    JS_SOURCES,
)
from app.services.security_scan.taint_definitions.python_definitions import (
    PY_SANITIZERS,
    PY_SINKS,
    PY_SOURCES,
)

ALL_SOURCES: tuple[TaintSource, ...] = (
    *PY_SOURCES,
    *JS_SOURCES,
    *JAVA_SOURCES,
    *CSHARP_SOURCES,
    *CPP_SOURCES,
)

ALL_SINKS: tuple[TaintSink, ...] = (
    *PY_SINKS,
    *JS_SINKS,
    *JAVA_SINKS,
    *CSHARP_SINKS,
    *CPP_SINKS,
)

ALL_SANITIZERS: tuple[TaintSanitizer, ...] = (
    *PY_SANITIZERS,
    *JS_SANITIZERS,
    *JAVA_SANITIZERS,
    *CSHARP_SANITIZERS,
    *CPP_SANITIZERS,
)


def sources_for_language(language: str | None) -> list[TaintSource]:
    return [s for s in ALL_SOURCES if s.applies_to(language)]


def sinks_for_language(language: str | None) -> list[TaintSink]:
    return [s for s in ALL_SINKS if s.applies_to(language)]


def sanitizers_for_language(language: str | None) -> list[TaintSanitizer]:
    return [s for s in ALL_SANITIZERS if s.applies_to(language)]


__all__ = [
    "ALL_SANITIZERS",
    "ALL_SINKS",
    "ALL_SOURCES",
    "SINK_SEVERITY",
    "TaintSanitizer",
    "TaintSink",
    "TaintSource",
    "sanitizers_for_language",
    "sinks_for_language",
    "sources_for_language",
]
