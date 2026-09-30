"""Dead code detector — Epic 5, Story 5.10.

Reports functions and methods that nothing in the project calls:
  - private/internal definitions (``_``-prefixed, non-dunder),
  - module-level public functions with no calls and no project import.

Excluded from the report (AC2 — generous on purpose, dynamic dispatch,
DI and reflection make call evidence unreliable): entry points (route /
endpoint / command / ``@internal`` decorators), ``main``/dunders,
``test_*``/``spec`` definitions, anything inside test files, public
methods, and names imported anywhere in the project.

Unlike the per-file detectors, dead code is inherently project-wide, so
``detect_project`` takes all parsed files at once. Call evidence is
collected in a single linear pass over each file's source (identifier
followed by ``(``), minus the definition sites themselves.

Reporting only — automatic cleanup stays out of scope (see
``services/code_cleanup.py``).
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.models.code_error import ErrorCategory
from app.services.gap_analysis.error_detectors.base import (
    BaseDetector,
    DetectedError,
)

if TYPE_CHECKING:
    from app.services.analysis.ast.ast_tree import ASTTree

# identifier immediately followed by an opening paren = call candidate
_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")

# decorator (Python/JS/TS/Java) or attribute (C#) line directly above a def
_DECORATOR_RE = re.compile(r"^\s*[@\[]")

_SUGGESTION = "Sprawdź i usuń albo oznacz `@internal`"

# path segments marking test/spec files
_TEST_SEGMENTS = {"test", "tests", "__tests__", "spec", "specs", "e2e"}


@dataclass
class ParsedFile:
    """One parsed project file: tree + the source it was parsed from."""

    tree: ASTTree
    file_path: str
    content: str


def build_fingerprint(file_path: str, name: str, source: str) -> str:
    """Stable finding key ``{file}:{name}:{sha8}``.

    ``sha8`` hashes the definition's source slice, so the key survives
    re-scans of the same code state and changes when the body changes.
    Edge whitespace is stripped so the key does not depend on it.
    """
    normalized = source.strip()
    sha8 = hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"{file_path}:{name}:{sha8}"


def _is_test_path(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/").lower()
    segments = [seg for seg in normalized.split("/") if seg]
    stem = segments[-1].rsplit(".", 1)[0] if segments else ""
    return (
        any(seg in _TEST_SEGMENTS for seg in segments[:-1])
        or stem.startswith(("test_", "test-"))
        or stem.endswith(("_test", "_spec", ".spec"))
        or stem in _TEST_SEGMENTS
    )


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_test_name(name: str) -> bool:
    lower = name.lower()
    return lower.startswith("test_") or lower.endswith(("_test", "_spec")) or lower == "test"


def _is_private(name: str) -> bool:
    return name.startswith("_") and not _is_dunder(name)


def _has_decorator(content_lines: list[str], def_line_start: int) -> bool:
    """True when a decorator/attribute line sits directly above the def."""
    idx = def_line_start - 2  # def_line_start is 1-based; line above it
    if idx < 0:
        return False
    line = content_lines[idx]
    if not line.strip():
        return False
    return bool(_DECORATOR_RE.match(line))


class DeadCodeDetector(BaseDetector):
    """Detect project-wide uncalled private/internal definitions."""

    category = ErrorCategory.DEAD_CODE

    def detect(
        self,
        tree: ASTTree,
        file_path: str | None = None,
    ) -> list[DetectedError]:
        """Per-file contract is a no-op — dead code needs project scope.

        Kept for BaseDetector compatibility; use :meth:`detect_project`.
        """
        return []

    def detect_project(self, files: list[ParsedFile]) -> list[DetectedError]:
        # --- 1. Collect definitions and call evidence (linear pass) -------
        defs: list[dict] = []
        call_counter: Counter[str] = Counter()
        def_counter: Counter[str] = Counter()
        imported_names: set[str] = set()

        for pf in files:
            content_lines = pf.content.splitlines()

            for imp in pf.tree.all_imports():
                if imp.module:
                    imported_names.add(imp.module)
                    imported_names.add(imp.module.split(".")[-1])
                imported_names.update(imp.aliases or [])

            for fn in pf.tree.functions:
                def_counter[fn.name] += 1
                defs.append(
                    {
                        "name": fn.name,
                        "file_path": pf.file_path,
                        "line_start": fn.line_start,
                        "line_end": fn.line_end,
                        "class_name": None,
                        "is_method": False,
                        "content_lines": content_lines,
                    }
                )
            for cls in pf.tree.classes:
                for m in cls.methods:
                    def_counter[m.name] += 1
                    defs.append(
                        {
                            "name": m.name,
                            "file_path": pf.file_path,
                            "line_start": m.line_start,
                            "line_end": m.line_end,
                            "class_name": cls.name,
                            "is_method": True,
                            "content_lines": content_lines,
                        }
                    )

            # one pass per file counts every call candidate; definition
            # sites are subtracted afterwards via def_counter
            for match in _CALL_RE.finditer(pf.content):
                call_counter[match.group(1)] += 1

        # --- 2. Filter to dead candidates ---------------------------------
        errors: list[DetectedError] = []
        for d in defs:
            name = d["name"]

            # AC2 exclusions
            if _is_test_path(d["file_path"]):
                continue
            if _is_dunder(name) or name == "main":
                continue
            if _is_test_name(name):
                continue
            if _has_decorator(d["content_lines"], d["line_start"]):
                continue
            if d["is_method"] and not _is_private(name):
                continue  # public methods excluded in v1

            calls = call_counter[name] - def_counter[name]
            if calls > 0:
                continue

            if not d["is_method"] and not _is_private(name) and name in imported_names:
                continue  # imported somewhere → reachable

            source_slice = "\n".join(d["content_lines"][d["line_start"] - 1 : d["line_end"]])
            fingerprint = build_fingerprint(d["file_path"], name, source_slice)

            if d["is_method"]:
                message = f"Metoda '{d['class_name']}.{name}' nie jest wywoływana nigdzie w projekcie (0 wywołań)"
            else:
                message = f"Funkcja '{name}' nie jest wywoływana nigdzie w projekcie (0 wywołań)"

            errors.append(
                DetectedError(
                    category=self.category,
                    message=message,
                    file_path=d["file_path"],
                    line_start=d["line_start"],
                    line_end=d["line_end"],
                    severity="warning",
                    rule_id="DEAD_CODE",
                    suggestion=_SUGGESTION,
                    context={
                        "function": name,
                        "class": d["class_name"],
                        "calls": 0,
                        "kind": "method" if d["is_method"] else "function",
                        "fingerprint": fingerprint,
                    },
                )
            )

        return errors
