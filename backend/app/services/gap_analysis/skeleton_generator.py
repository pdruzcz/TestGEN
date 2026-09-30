"""Skeleton code generator — Epic 5, Story 5.6.

Generates skeleton code stubs from gap findings (type=MISSING) using Jinja2
templates for Python, TypeScript, Java and C#.  The generator:

1. Extracts a function/method name from the requirement text
2. Determines the target language from project context
3. Renders a Jinja2 template with docstring/comment + raise NotImplementedError
4. Optionally validates syntax via tree-sitter

Designed to be extensible — custom templates can be added per language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from jinja2 import Template

from app.models.gap_finding import GapFinding, GapType


@dataclass
class SkeletonResult:
    """Output of skeleton generation."""

    code: str
    language: str
    function_name: str
    error: str | None = None


# ── Jinja2 templates per language ────────────────────────────────────────────

_PYTHON_TEMPLATE = Template(
    '''{{ docstring }}
def {{ function_name }}({{ params }}):
    """{{ requirement_summary }}"""
    raise NotImplementedError("TODO: implement {{ function_name }}")
'''
)

_TYPESCRIPT_TEMPLATE = Template(
    '''{{ docstring }}
export function {{ function_name }}({{ params }}): {{ return_type }} {
  // {{ requirement_summary }}
  throw new Error("TODO: implement {{ function_name }}");
}
'''
)

_JAVA_TEMPLATE = Template(
    '''{{ docstring }}
public {{ return_type }} {{ function_name }}({{ params }}) {
    // {{ requirement_summary }}
    throw new UnsupportedOperationException("TODO: implement {{ function_name }}");
}
'''
)

_CSHARP_TEMPLATE = Template(
    '''{{ docstring }}
public {{ return_type }} {{ function_name }}({{ params }})
{
    // {{ requirement_summary }}
    throw new NotImplementedException("TODO: implement {{ function_name }}");
}
'''
)

_TEMPLATES: dict[str, Template] = {
    "python": _PYTHON_TEMPLATE,
    "typescript": _TYPESCRIPT_TEMPLATE,
    "java": _JAVA_TEMPLATE,
    "csharp": _CSHARP_TEMPLATE,
}

# Default return types per language
_DEFAULT_RETURN_TYPES: dict[str, str] = {
    "python": "",  # Python doesn't need explicit return type
    "typescript": "void",
    "java": "void",
    "csharp": "void",
}


class SkeletonGenerator:
    """Generate skeleton code stubs from gap findings."""

    # Patterns to extract function name from requirement text
    _NAME_PATTERNS = [
        r"(?:funkcja|function|metoda|method)\s+[\"']?([a-zA-Z_][a-zA-Z0-9_]*)",
        r"(?:system|użytkownik|user)\s+(?:powinien|should|musi|must)\s+(\w+)",
        r"^([A-Z][a-zA-Z0-9]+)$",  # single word, TitleCase
    ]

    _STOPWORDS = {
        "the", "a", "an", "system", "użytkownik", "user",
        "should", "must", "powinien", "musi", "być", "is", "are",
        "for", "to", "in", "of", "na", "do", "w", "z", "od",
    }

    def generate(
        self,
        finding: GapFinding,
        language: str = "python",
    ) -> SkeletonResult:
        """Generate skeleton code for a single gap finding.

        Args:
            finding: GapFinding with gap_type=MISSING
            language: Target language (python/typescript/java/csharp)

        Returns:
            SkeletonResult with generated code or error message.
        """
        if language not in _TEMPLATES:
            return SkeletonResult(
                code="",
                language=language,
                function_name="",
                error=f"Unsupported language: {language}",
            )

        req_text = finding.requirement_text or finding.description or ""
        function_name = self._extract_function_name(req_text)

        # Build requirement summary (first sentence, truncated)
        summary = self._extract_summary(req_text)

        params = self._guess_params(req_text)

        return_type = _DEFAULT_RETURN_TYPES.get(language, "void")

        template = _TEMPLATES[language]
        code = template.render(
            docstring="",  # docstring is inside function for Python
            function_name=function_name,
            params=params,
            return_type=return_type,
            requirement_summary=summary,
        ).strip()

        return SkeletonResult(
            code=code,
            language=language,
            function_name=function_name,
        )

    def generate_batch(
        self,
        findings: list[GapFinding],
        language: str = "python",
    ) -> list[SkeletonResult]:
        """Generate skeletons for multiple findings (MISSING gaps only)."""
        results: list[SkeletonResult] = []
        for f in findings:
            if f.gap_type != GapType.MISSING:
                continue
            results.append(self.generate(f, language))
        return results

    # ── Helpers ────────────────────────────────────────────────────────────

    def _extract_function_name(self, text: str) -> str:
        """Extract a valid function name from requirement text."""
        # Try explicit patterns first
        for pattern in self._NAME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).lower()
                name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
                if name and not name[0].isdigit():
                    return name

        # Fallback: use first significant word
        words = re.findall(r"[a-zA-Z]{3,}", text)
        for word in words:
            if word.lower() not in self._STOPWORDS:
                return re.sub(
                    r"[^a-zA-Z0-9_]", "_", word.lower()
                )

        return "implement_requirement"

    def _extract_summary(self, text: str, max_len: int = 120) -> str:
        """Extract first sentence or truncate to max_len."""
        sentence = re.split(r"[.\n]", text.strip())[0].strip()
        if len(sentence) > max_len:
            sentence = sentence[:max_len - 3] + "..."
        return sentence

    def _guess_params(self, text: str) -> str:
        """Guess parameters from requirement text. Conservative — returns empty for now."""
        return ""
