"""Infrastructure-config scanner orchestrator — Epic 4, Story 4.5.

Detects a project's Docker / Kubernetes / Terraform files, routes each to the
matching :class:`IConfigScanner`, and converts the resulting
:class:`ConfigFinding` objects into persisted-ready ``SecurityFinding`` rows.
An optional LLM dual-path (engine_mode=llm/hybrid) adds holistic, cross-file
misconfiguration findings.
"""

import logging
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_finding import (
    AnalysisSource,
    ScanType,
    SecurityFinding,
    Severity,
)
from app.services.security_scan.config_scanners import (
    ConfigFinding,
    DockerScanner,
    KubernetesScanner,
    TerraformScanner,
)

logger = logging.getLogger(__name__)

_MAX_CONTENT_BYTES = 1_000_000
_MAX_LLM_FILES = 15
_SEVERITIES = {"critical", "high", "medium", "low", "info"}


@dataclass
class ConfigFile:
    path: str
    config_type: str  # docker / kubernetes / terraform
    filename: str


class ConfigScanner:
    """Routes config files to technology scanners and emits SecurityFindings."""

    def __init__(
        self,
        db: AsyncSession | None = None,
        llm_gateway=None,
        engine_mode: str = "native",
    ) -> None:
        self.db = db
        self.llm_gateway = llm_gateway
        self.engine_mode = engine_mode
        self._scanners = {
            "docker": DockerScanner(),
            "kubernetes": KubernetesScanner(),
            "terraform": TerraformScanner(),
        }

    # ----- public API ------------------------------------------------------

    def scan_content(self, content: str, filename: str) -> list[ConfigFinding]:
        """Detect the type of ``filename`` and run the matching scanner. Pure."""
        config_type = self._classify(filename)
        if config_type is None:
            return []
        return self._route_scanner(config_type).scan(content, filename)

    async def scan_config(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> list[SecurityFinding]:
        start = time.time()
        files = await self._load_config_files(project_id)

        raw: list[ConfigFinding] = []
        for path, content in files:
            raw.extend(self.scan_content(content, path))

        if self.engine_mode in ("llm", "hybrid") and self.llm_gateway is not None:
            try:
                llm_findings = await self._run_llm_analysis(files, tenant_id)
                raw = self._merge_findings(raw, llm_findings)
            except Exception as exc:  # LLM path must never fail the whole scan
                logger.warning("Config LLM analysis failed, keeping native results: %s", exc)

        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "Config scan project=%s files=%d findings=%d in %dms",
            project_id, len(files), len(raw), elapsed_ms,
        )
        return [self._to_finding(r, project_id, tenant_id, scan_id) for r in raw]

    # ----- detection / routing --------------------------------------------

    @staticmethod
    def _classify(filename: str) -> str | None:
        base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
        if base.startswith("docker-compose") or base.endswith(
            ("compose.yml", "compose.yaml")
        ):
            return "docker"
        if base == "dockerfile" or base.startswith("dockerfile") or base.endswith(".dockerfile"):
            return "docker"
        if base.endswith((".tf", ".tf.json")):
            return "terraform"
        if base.endswith((".yaml", ".yml")):
            return "kubernetes"
        return None

    def _route_scanner(self, config_type: str):
        return self._scanners[config_type]

    def _detect_config_files(self, filenames: list[str]) -> list[ConfigFile]:
        out: list[ConfigFile] = []
        for name in filenames:
            config_type = self._classify(name)
            if config_type is not None:
                base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                out.append(ConfigFile(path=name, config_type=config_type, filename=base))
        return out

    # ----- dual-path LLM ---------------------------------------------------

    async def _run_llm_analysis(
        self, files: list[tuple[str, str]], tenant_id: uuid.UUID
    ) -> list[ConfigFinding]:
        from app.services.analysis.llm_gateway import LLMMessage

        subset = files[:_MAX_LLM_FILES]
        if not subset:
            return []
        combined = "\n\n".join(
            f"### {path}\n```\n{content[:4000]}\n```" for path, content in subset
        )
        prompt = (
            "Jesteś ekspertem bezpieczeństwa infrastruktury. Przeanalizuj poniższe "
            "pliki konfiguracyjne (Docker/Kubernetes/Terraform) HOLISTYCZNIE, "
            "uwzględniając interakcje między komponentami (np. brak TLS + eksponowany "
            "port = wyższe ryzyko). Zwróć WYŁĄCZNIE JSON: lista obiektów "
            '{"config_type","severity","file","description","recommendation"}. '
            "severity ∈ critical|high|medium|low. Jeśli brak problemów, zwróć [].\n\n"
            f"{combined}"
        )
        response = await self.llm_gateway.complete(
            provider="anthropic",
            messages=[LLMMessage(role="user", content=prompt)],
            max_tokens=1500,
            temperature=0.0,
            module="security_config",
            task_type="config_holistic",
        )
        return self._parse_llm_findings(response.content)

    @staticmethod
    def _parse_llm_findings(content: str) -> list[ConfigFinding]:
        import json

        text = content.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1] if "```" in text[3:] else text.strip("`")
            text = text.removeprefix("json").strip()
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end == -1:
            return []
        try:
            items = json.loads(text[start : end + 1])
        except (ValueError, json.JSONDecodeError):
            return []
        out: list[ConfigFinding] = []
        for item in items:
            if not isinstance(item, dict) or "description" not in item:
                continue
            severity = str(item.get("severity", "medium")).lower()
            if severity not in _SEVERITIES:
                severity = "medium"
            out.append(
                ConfigFinding(
                    rule_id="LLM_HOLISTIC",
                    config_type=str(item.get("config_type", "config")),
                    severity=severity,
                    description=str(item["description"]),
                    recommendation=str(item.get("recommendation", "")),
                    file_path=item.get("file"),
                    vulnerability_type="misconfiguration",
                    source="llm",
                )
            )
        return out

    @staticmethod
    def _merge_findings(
        native: list[ConfigFinding], llm: list[ConfigFinding]
    ) -> list[ConfigFinding]:
        index: dict[tuple, ConfigFinding] = {}
        for f in native:
            index[(f.file_path, f.line, f.rule_id)] = f
        for f in llm:
            key = (f.file_path, f.line, f.rule_id)
            if key in index:
                index[key].source = "hybrid"
            else:
                index[key] = f
        return list(index.values())

    # ----- persistence -----------------------------------------------------

    def _to_finding(
        self,
        raw: ConfigFinding,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> SecurityFinding:
        return SecurityFinding(
            project_id=project_id,
            tenant_id=tenant_id,
            scan_id=scan_id,
            scan_type=ScanType.CONFIG,
            vulnerability_type=raw.vulnerability_type,
            severity=Severity(raw.severity),
            cwe_id=raw.cwe_id,
            owasp_category="A05:2021-Security Misconfiguration",
            file_path=raw.file_path,
            line_start=raw.line,
            line_end=raw.line,
            description=raw.description,
            confidence=0.85 if raw.source == "native" else 0.6,
            source=AnalysisSource(raw.source),
            recommendation=raw.recommendation,
            finding_metadata={
                "rule_id": raw.rule_id,
                "config_type": raw.config_type,
                "fix_example": raw.fix_example,
                **({"extra": raw.extra} if raw.extra else {}),
            },
        )

    async def _load_config_files(self, project_id: uuid.UUID) -> list[tuple[str, str]]:
        if self.db is None:
            return []
        import asyncio

        from app.core.config import get_settings
        from app.core.storage import download_file_bytes
        from app.models.source_file import SourceFile

        settings = get_settings()
        result = await self.db.execute(
            select(SourceFile).where(
                SourceFile.project_id == project_id,
                SourceFile.is_cleaned_up == False,  # noqa: E712
            )
        )
        files: list[tuple[str, str]] = []
        for sf in result.scalars().all():
            name = sf.original_path or sf.filename
            if self._classify(name) is None:
                continue
            if sf.file_size and sf.file_size > _MAX_CONTENT_BYTES:
                continue
            try:
                raw = await asyncio.to_thread(
                    download_file_bytes, settings.minio_bucket_name, sf.storage_key
                )
                files.append((name, raw.decode("utf-8", errors="replace")))
            except Exception as exc:
                logger.warning("Config scan: failed to load %s: %s", sf.storage_key, exc)
        return files
