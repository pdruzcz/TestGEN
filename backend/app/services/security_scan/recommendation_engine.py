"""Recommendation engine — Epic 4, Story 4.9.

Generates a remediation recommendation for a single ``SecurityFinding`` via two
paths: deterministic native templates (default) and a contextual LLM path that
falls back to the native template when the model is unavailable or returns no
usable code. Each recommendation carries the problem / risk / fix text, a fixed
code snippet in the project's language and a unified diff against the vulnerable
snippet.
"""

import logging
from dataclasses import dataclass

from app.models.security_finding import SecurityFinding
from app.services.security_scan import recommendation_templates  # noqa: F401 — registers templates
from app.services.security_scan.diff_generator import generate_unified_diff
from app.services.security_scan.recommendation_templates.registry import Template, TemplateRegistry

logger = logging.getLogger(__name__)

# File extension → language used for template lookup.
_EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".go": "go",
}

_NATIVE = "native"
_LLM = "llm"


@dataclass
class Recommendation:
    problem_description: str
    risk_description: str
    fix_description: str
    fixed_code_snippet: str
    diff: str
    language: str
    engine_source: str


class RecommendationEngine:
    """Builds a :class:`Recommendation` for a finding (native or LLM path)."""

    def __init__(self, llm_gateway=None) -> None:
        self.llm_gateway = llm_gateway

    async def generate_recommendation(
        self,
        finding: SecurityFinding,
        source_code: str | None = None,
        engine_mode: str = _NATIVE,
    ) -> Recommendation:
        """Produce a recommendation. ``engine_mode`` selects native vs LLM (AC1-AC3)."""
        if engine_mode == _LLM and self.llm_gateway is not None:
            recommendation = await self._get_llm_recommendation(finding, source_code or "")
            if recommendation is not None:
                return recommendation
            logger.info("LLM recommendation unavailable, falling back to native template")
        return self._get_native_recommendation(finding, source_code)

    def _get_native_recommendation(
        self,
        finding: SecurityFinding,
        source_code: str | None = None,
    ) -> Recommendation:
        """Resolve a native template for the finding and build the diff (AC1-AC2)."""
        language = self._infer_language(finding.file_path)
        framework = (finding.finding_metadata or {}).get("framework")
        template = TemplateRegistry.get_template(finding.vulnerability_type, language, framework)
        if template is None:
            template = self._generic_template(finding)

        original = source_code if source_code is not None else (finding.code_snippet or "")
        diff = self._generate_diff(original, template.fixed_code_snippet, finding.file_path or "code", finding)
        return Recommendation(
            problem_description=template.problem_description,
            risk_description=template.risk_description,
            fix_description=template.fix_description,
            fixed_code_snippet=template.fixed_code_snippet,
            diff=diff,
            language=template.language,
            engine_source=_NATIVE,
        )

    async def _get_llm_recommendation(
        self,
        finding: SecurityFinding,
        source_code: str,
    ) -> Recommendation | None:
        """Ask the LLM for a contextual fix; returns ``None`` so the caller can fall back (AC3)."""
        from app.services.analysis.llm_gateway import LLMMessage

        language = self._infer_language(finding.file_path)
        framework = (finding.finding_metadata or {}).get("framework")
        prompt = self._build_llm_prompt(finding, source_code, language, framework)
        try:
            response = await self.llm_gateway.complete(
                provider="anthropic",
                messages=[LLMMessage(role="user", content=prompt)],
                max_tokens=1500,
                temperature=0.0,
                module="security_recommendation",
                task_type="remediation",
            )
        except Exception as exc:
            logger.warning("LLM recommendation call failed for finding %s: %s", finding.id, exc)
            return None

        fixed_code = self._extract_code_block(response.content)
        if not fixed_code:
            return None

        original = source_code or (finding.code_snippet or "")
        diff = self._generate_diff(original, fixed_code, finding.file_path or "code", finding)
        # Reuse native text where available; LLM contributes the fixed snippet/diff.
        native = TemplateRegistry.get_template(
            finding.vulnerability_type, language, framework
        ) or self._generic_template(finding)
        return Recommendation(
            problem_description=native.problem_description,
            risk_description=native.risk_description,
            fix_description=native.fix_description,
            fixed_code_snippet=fixed_code,
            diff=diff,
            language=language or native.language,
            engine_source=_LLM,
        )

    @staticmethod
    def _generate_diff(original: str, fixed: str, file_path: str, finding: SecurityFinding) -> str:
        line_start = finding.line_start or 1
        return generate_unified_diff(original, fixed, file_path=file_path, line_start=line_start)

    @staticmethod
    def _infer_language(file_path: str | None) -> str:
        if not file_path:
            return "generic"
        lowered = file_path.lower()
        for ext, language in _EXTENSION_LANGUAGE.items():
            if lowered.endswith(ext):
                return language
        return "generic"

    @staticmethod
    def _build_llm_prompt(
        finding: SecurityFinding,
        source_code: str,
        language: str,
        framework: str | None,
    ) -> str:
        return (
            f"Przeanalizuj podatność {finding.vulnerability_type} w kodzie {language}. "
            "Oto podatny fragment:\n"
            f"```\n{source_code[:6000]}\n```\n\n"
            f"Wygeneruj naprawiony kod uwzględniający framework {framework or 'nieznany'} "
            "i styl projektu. Zwróć WYŁĄCZNIE naprawiony kod w bloku ``` ```."
        )

    @staticmethod
    def _extract_code_block(content: str) -> str:
        """Pull the fenced code block out of an LLM response (best-effort)."""
        text = content.strip()
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                block = parts[1]
                # Drop an optional language hint on the first line.
                if "\n" in block:
                    first, rest = block.split("\n", 1)
                    if first.strip().isalpha():
                        return rest.strip()
                return block.strip()
        return text

    @staticmethod
    def _generic_template(finding: SecurityFinding) -> Template:
        vuln = finding.vulnerability_type.replace("_", " ")
        return Template(
            problem_description=f"Wykryto podatność typu {vuln} w kodzie.",
            risk_description="Podatność może zostać wykorzystana przez atakującego do naruszenia bezpieczeństwa aplikacji.",
            fix_description="Zastosuj rekomendowane praktyki bezpieczeństwa dla tej klasy podatności (OWASP Cheat Sheet).",
            fixed_code_snippet="// zastosuj bezpieczny wzorzec zgodny z OWASP dla tej podatności",
            language="generic",
        )
