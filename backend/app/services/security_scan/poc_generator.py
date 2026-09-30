"""Proof-of-concept generator — Epic 4, Story 4.10.

Produces a *safe*, non-destructive proof-of-concept for an injection finding so an
authorised auditor can confirm exploitability. Two paths: deterministic native
payload templates (default) and a contextual LLM path that proposes a payload
tailored to the code's validators/sanitisers. Every PoC — native or LLM — passes
through :mod:`poc_safety` before it is returned, and the LLM path falls back to a
native template when its output is unavailable or fails the safety check. A
mandatory disclaimer is attached to every PoC.
"""

import logging
from dataclasses import dataclass, field

from app.models.security_finding import SecurityFinding
from app.services.security_scan import poc_payloads  # noqa: F401 — registers payloads
from app.services.security_scan.poc_payloads.registry import PayloadRegistry, PayloadTemplate
from app.services.security_scan.poc_safety import validate_text_safety

logger = logging.getLogger(__name__)

_NATIVE = "native"
_LLM = "llm"

DISCLAIMER = (
    "PoC służy wyłącznie do weryfikacji podatności. "
    "Użycie na systemach bez autoryzacji jest zabronione."
)

_EXTENSION_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".go": "go",
}


@dataclass
class ProofOfConcept:
    payload: str
    reproduction_steps: list[str]
    expected_effect: str
    severity: str
    is_safe: bool
    disclaimer: str = DISCLAIMER
    engine_source: str = _NATIVE
    blocked_reasons: list[str] = field(default_factory=list)


class PoCGenerator:
    """Builds a safe :class:`ProofOfConcept` for an injection finding."""

    def __init__(self, llm_gateway=None) -> None:
        self.llm_gateway = llm_gateway

    async def generate_poc(
        self,
        finding: SecurityFinding,
        engine_mode: str = _NATIVE,
        source_code: str | None = None,
    ) -> ProofOfConcept | None:
        """Generate a PoC for the finding (AC1-AC4). Returns ``None`` if unsupported."""
        if engine_mode == _LLM and self.llm_gateway is not None:
            poc = await self._get_llm_poc(finding, source_code or "")
            if poc is not None and poc.is_safe:
                return poc
            logger.info("LLM PoC unavailable or unsafe, falling back to native template")
        return self._get_native_poc(finding)

    def _get_native_poc(self, finding: SecurityFinding) -> ProofOfConcept | None:
        template = PayloadRegistry.first_safe(finding.vulnerability_type)
        if template is None:
            return None
        return self._build(finding, template, _NATIVE)

    async def _get_llm_poc(self, finding: SecurityFinding, source_code: str) -> ProofOfConcept | None:
        from app.services.analysis.llm_gateway import LLMMessage

        language = self._infer_language(finding.file_path)
        prompt = self._build_llm_prompt(finding, source_code, language)
        try:
            response = await self.llm_gateway.complete(
                provider="anthropic",
                messages=[LLMMessage(role="user", content=prompt)],
                max_tokens=800,
                temperature=0.0,
                module="security_poc",
                task_type="poc_generation",
            )
        except Exception as exc:
            logger.warning("LLM PoC call failed for finding %s: %s", finding.id, exc)
            return None

        payload = self._extract_payload(response.content)
        if not payload:
            return None

        severity = finding.severity.value if finding.severity else "medium"
        steps = [
            "1. Zlokalizuj punkt wejścia podatności wskazany w zgłoszeniu.",
            "2. Wprowadź wygenerowany payload w podatnym parametrze.",
            "3. Obserwuj efekt potwierdzający wykonanie / odczyt.",
        ]
        effect = "Payload demonstruje podatność z uwzględnieniem walidacji obecnych w kodzie."
        safety = self._validate(payload, steps, effect)
        return ProofOfConcept(
            payload=payload,
            reproduction_steps=steps,
            expected_effect=effect,
            severity=severity,
            is_safe=safety.is_safe,
            engine_source=_LLM,
            blocked_reasons=safety.blocked_reasons,
        )

    def _build(self, finding: SecurityFinding, template: PayloadTemplate, source: str) -> ProofOfConcept:
        severity = finding.severity.value if finding.severity else "medium"
        steps = list(template.reproduction_steps)
        safety = self._validate(template.payload, steps, template.expected_effect)
        return ProofOfConcept(
            payload=template.payload,
            reproduction_steps=steps,
            expected_effect=template.expected_effect,
            severity=severity,
            is_safe=safety.is_safe,
            engine_source=source,
            blocked_reasons=safety.blocked_reasons,
        )

    @staticmethod
    def _validate(payload: str, steps: list[str], effect: str):
        return validate_text_safety(payload, "\n".join(steps), effect)

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
    def _build_llm_prompt(finding: SecurityFinding, source_code: str, language: str) -> str:
        return (
            f"Wygeneruj BEZPIECZNY, nie-destruktywny PoC dla podatności "
            f"{finding.vulnerability_type} w kodzie {language}. Podatny fragment:\n"
            f"```\n{source_code[:4000]}\n```\n\n"
            "Uwzględnij istniejące walidacje i sanityzatory. PoC NIE MOŻE modyfikować "
            "ani usuwać danych, plików, ani sterować systemem (zakaz DROP/DELETE/rm/shutdown). "
            "Zwróć WYŁĄCZNIE sam payload w jednej linii, bez wyjaśnień."
        )

    @staticmethod
    def _extract_payload(content: str) -> str:
        text = content.strip()
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                block = parts[1]
                if "\n" in block:
                    first, rest = block.split("\n", 1)
                    if first.strip().isalpha():
                        block = rest
                text = block.strip()
        # Use the first non-empty line as the payload.
        for line in text.splitlines():
            if line.strip():
                return line.strip()
        return ""
