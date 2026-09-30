"""Unified diff generator — Epic 4, Story 4.9.

Wraps ``difflib.unified_diff`` to produce a GitHub-style unified diff between a
vulnerable code snippet and its fixed version, used in the recommendation view.
"""

import difflib


def generate_unified_diff(
    original: str,
    fixed: str,
    file_path: str | None = None,
    line_start: int = 1,
    context: int = 3,
) -> str:
    """Return a unified diff (old vs fixed) with the given context lines.

    ``line_start`` shifts the hunk header so it reflects the finding's location
    in the original file rather than line 1.
    """
    if original == fixed:
        return ""

    label = file_path or "code"
    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if fixed_lines and not fixed_lines[-1].endswith("\n"):
        fixed_lines[-1] += "\n"

    diff = difflib.unified_diff(
        original_lines,
        fixed_lines,
        fromfile=f"a/{label}",
        tofile=f"b/{label}",
        n=context,
        lineterm="\n",
    )
    return _shift_hunk_lines("".join(diff), line_start)


def _shift_hunk_lines(diff: str, line_start: int) -> str:
    """Rewrite @@ hunk headers so line numbers start at ``line_start``."""
    if line_start <= 1 or not diff:
        return diff
    offset = line_start - 1
    out: list[str] = []
    for line in diff.splitlines(keepends=True):
        if line.startswith("@@"):
            out.append(_shift_hunk_header(line, offset))
        else:
            out.append(line)
    return "".join(out)


def _shift_hunk_header(header: str, offset: int) -> str:
    # Format: @@ -l,s +l,s @@
    try:
        body = header.strip().strip("@").strip()
        old_part, new_part = body.split(" ")[0], body.split(" ")[1]
        old_shifted = _shift_range(old_part, offset)
        new_shifted = _shift_range(new_part, offset)
        return f"@@ {old_shifted} {new_shifted} @@\n"
    except (ValueError, IndexError):
        return header


def _shift_range(part: str, offset: int) -> str:
    sign = part[0]
    rest = part[1:]
    if "," in rest:
        start, size = rest.split(",", 1)
        return f"{sign}{int(start) + offset},{size}"
    return f"{sign}{int(rest) + offset}"
