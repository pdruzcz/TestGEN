"""LLM taint analyzer — Story 4.13 (AC2).

Tracks data flows the line-based native taint engine cannot follow: flows that
cross functions/files or pass through framework abstractions. The LLM is asked
for source→sink paths lacking sanitization and returns ``RawFinding`` with a
``taint_path`` description in metadata.
"""

import logging
import uuid

from app.services.security_scan.llm_security import extract_json_array, normalize_severity
from app.services.security_scan.rules import RawFinding

logger = logging.getLogger(__name__)

_MAX_CHUNK_CHARS = 6000
_MAX_FILES = 15


class LLMTaintAnalyzer:
    """Semantic taint analysis via the LLM gateway (source=llm)."""

    def __init__(self, llm_gateway=None) -> None:
        self.llm_gateway = llm_gateway

    async def analyze(
        self,
        files: list[tuple[str | None, str | None, str]],
        tenant_id: uuid.UUID | None = None,
    ) -> list[RawFinding]:
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
                    module="security_taint",
                    task_type="taint_semantic_dualpath",
                )
            except Exception as exc:
                logger.warning("LLM taint call failed for %s: %s", file_path, exc)
                continue
            out.extend(self.parse_response(response.content, file_path))
        return out

    @staticmethod
    def _build_prompt(code: str, language: str | None) -> str:
        return (
            "Jesteś ekspertem analizy przepływu danych. Przeanalizuj poniższy kod "
            f"({language or 'nieznany język'}) i znajdź ścieżki od danych "
            "użytkownika (sources: request, params, argv, body) do niebezpiecznych "
            "operacji (sinks: SQL, exec, eval, system, render) BEZ odpowiedniej "
            "sanityzacji — także przepływy przechodzące między funkcjami. Zwróć "
            "WYŁĄCZNIE JSON: lista obiektów "
            '{"vulnerability_type","severity","line_start","description","source","sink","cwe_id"}. '
            "severity ∈ critical|high|medium|low. Jeśli brak ścieżek, zwróć [].\n\n"
            f"```\n{code}\n```"
        )

    @staticmethod
    def parse_response(content: str, file_path: str | None) -> list[RawFinding]:
        out: list[RawFinding] = []
        for item in extract_json_array(content):
            if not isinstance(item, dict) or "vulnerability_type" not in item:
                continue
            line = item.get("line_start")
            metadata = {}
            if item.get("source"):
                metadata["source"] = str(item["source"])
            if item.get("sink"):
                metadata["sink"] = str(item["sink"])
            out.append(
                RawFinding(
                    vulnerability_type=str(item["vulnerability_type"]),
                    severity=normalize_severity(item.get("severity")),
                    description=str(item.get("description", "Niebezpieczny przepływ danych (LLM).")),
                    file_path=file_path,
                    line_start=line,
                    line_end=line,
                    confidence=0.6,
                    cwe_id=item.get("cwe_id"),
                    source="llm",
                    metadata=metadata,
                )
            )
        return out
