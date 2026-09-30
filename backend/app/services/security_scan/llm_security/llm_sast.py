"""LLM SAST analyzer — Story 4.13 (AC2).

Asks the LLM gateway for *semantic* security findings that pattern rules
cannot catch: logical security bugs, missing authorization, framework-specific
issues (mass assignment, etc.), race conditions and TOCTOU. Code is chunked per
file (bounded token budget) and analyzed in sequence; failures degrade to an
empty list so the dual-path scan keeps the native results.
"""

import logging
import uuid

from app.services.security_scan.llm_security import extract_json_array, normalize_severity
from app.services.security_scan.rules import RawFinding

logger = logging.getLogger(__name__)

# Keep per-call code bounded (~4000 tokens ≈ 12k chars, conservatively halved).
_MAX_CHUNK_CHARS = 6000
_MAX_FILES = 20


class LLMSASTAnalyzer:
    """Semantic SAST via the LLM gateway, returning ``RawFinding`` (source=llm)."""

    def __init__(self, llm_gateway=None) -> None:
        self.llm_gateway = llm_gateway

    async def analyze(
        self,
        files: list[tuple[str | None, str | None, str]],
        tenant_id: uuid.UUID | None = None,
    ) -> list[RawFinding]:
        """Analyze ``(file_path, language, content)`` tuples for semantic issues."""
        if self.llm_gateway is None:
            return []
        from app.services.analysis.llm_gateway import LLMMessage

        out: list[RawFinding] = []
        for file_path, language, content in files[:_MAX_FILES]:
            prompt = self._build_prompt(content[:_MAX_CHUNK_CHARS], language)
            try:
                response = await self.llm_gateway.complete(
                    provider="anthropic",
                    messages=[LLMMessage(role="user", content=prompt)],
                    max_tokens=1500,
                    temperature=0.0,
                    tenant_id=tenant_id,
                    module="security_sast",
                    task_type="sast_semantic_dualpath",
                )
            except Exception as exc:  # never fail the scan over one chunk
                logger.warning("LLM SAST call failed for %s: %s", file_path, exc)
                continue
            out.extend(self.parse_response(response.content, file_path))
        return out

    @staticmethod
    def _build_prompt(code: str, language: str | None) -> str:
        return (
            "Jesteś ekspertem bezpieczeństwa aplikacji. Przeanalizuj poniższy kod "
            f"({language or 'nieznany język'}) pod kątem podatności, których NIE wykrywają "
            "proste reguły: błędów logicznych bezpieczeństwa, brakujących kontroli "
            "dostępu (analiza kontekstu biznesowego), podatności specyficznych dla "
            "frameworka (np. mass assignment w Django/Rails), race conditions oraz "
            "TOCTOU. Zwróć WYŁĄCZNIE JSON: lista obiektów "
            '{"vulnerability_type","severity","line_start","description","cwe_id","recommendation"}. '
            "severity ∈ critical|high|medium|low. Jeśli brak podatności, zwróć [].\n\n"
            f"```\n{code}\n```"
        )

    @staticmethod
    def parse_response(content: str, file_path: str | None) -> list[RawFinding]:
        """Parse the LLM JSON response into ``RawFinding`` objects. Pure + testable."""
        out: list[RawFinding] = []
        for item in extract_json_array(content):
            if not isinstance(item, dict) or "vulnerability_type" not in item:
                continue
            line = item.get("line_start")
            out.append(
                RawFinding(
                    vulnerability_type=str(item["vulnerability_type"]),
                    severity=normalize_severity(item.get("severity")),
                    description=str(item.get("description", "Podatność wykryta przez LLM.")),
                    file_path=file_path,
                    line_start=line,
                    line_end=line,
                    confidence=0.6,
                    cwe_id=item.get("cwe_id"),
                    recommendation=item.get("recommendation"),
                    source="llm",
                )
            )
        return out
