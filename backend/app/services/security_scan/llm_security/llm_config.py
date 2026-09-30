"""LLM config analyzer — Story 4.13 (AC2).

Reviews infrastructure config (Docker / Kubernetes / Terraform) *holistically*,
flagging risks that emerge from the combination of settings rather than any
single line (e.g. an exposed port together with disabled TLS). Returns
``RawFinding`` with ``source="llm"``.
"""

import logging
import uuid

from app.services.security_scan.llm_security import extract_json_array, normalize_severity
from app.services.security_scan.rules import RawFinding

logger = logging.getLogger(__name__)

_MAX_FILE_CHARS = 4000
_MAX_FILES = 12


class LLMConfigAnalyzer:
    """Holistic infrastructure-config review via the LLM gateway (source=llm)."""

    def __init__(self, llm_gateway=None) -> None:
        self.llm_gateway = llm_gateway

    async def analyze(
        self,
        files: list[tuple[str, str]],
        tenant_id: uuid.UUID | None = None,
    ) -> list[RawFinding]:
        """Analyze ``(path, content)`` config files together for holistic risks."""
        if self.llm_gateway is None:
            return []
        from app.services.analysis.llm_gateway import LLMMessage

        subset = files[:_MAX_FILES]
        if not subset:
            return []
        prompt = self._build_prompt(subset)
        try:
            response = await self.llm_gateway.complete(
                provider="anthropic",
                messages=[LLMMessage(role="user", content=prompt)],
                max_tokens=1500,
                temperature=0.0,
                tenant_id=tenant_id,
                module="security_config",
                task_type="config_holistic_dualpath",
            )
        except Exception as exc:
            logger.warning("LLM config call failed: %s", exc)
            return []
        return self.parse_response(response.content)

    @staticmethod
    def _build_prompt(files: list[tuple[str, str]]) -> str:
        combined = "\n\n".join(
            f"### {path}\n```\n{content[:_MAX_FILE_CHARS]}\n```" for path, content in files
        )
        return (
            "Jesteś ekspertem bezpieczeństwa infrastruktury. Przeanalizuj poniższe "
            "pliki konfiguracyjne (Docker/Kubernetes/Terraform) HOLISTYCZNIE, "
            "uwzględniając interakcje między ustawieniami (np. brak TLS + eksponowany "
            "port = wyższe ryzyko). Zwróć WYŁĄCZNIE JSON: lista obiektów "
            '{"vulnerability_type","severity","file","line_start","description","recommendation"}. '
            "severity ∈ critical|high|medium|low. Jeśli brak problemów, zwróć [].\n\n"
            f"{combined}"
        )

    @staticmethod
    def parse_response(content: str) -> list[RawFinding]:
        out: list[RawFinding] = []
        for item in extract_json_array(content):
            if not isinstance(item, dict) or "description" not in item:
                continue
            line = item.get("line_start")
            out.append(
                RawFinding(
                    vulnerability_type=str(item.get("vulnerability_type", "insecure_configuration")),
                    severity=normalize_severity(item.get("severity")),
                    description=str(item["description"]),
                    file_path=item.get("file"),
                    line_start=line,
                    line_end=line,
                    confidence=0.6,
                    recommendation=item.get("recommendation"),
                    source="llm",
                )
            )
        return out
