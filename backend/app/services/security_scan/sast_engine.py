"""SAST engine — Epic 4, Story 4.1.

Static application security testing over a project's uploaded source files.
Native detection applies the regex/line rules in :mod:`rules` (AST-aware through
language scoping); the optional LLM path (engine_mode=llm/hybrid) asks the LLM
gateway for semantic findings and merges them with native results, deduplicated
by (file_path, line_start, vulnerability_type).
"""

import json
import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_finding import (
    AnalysisSource,
    ScanType,
    SecurityFinding,
    Severity,
)
from app.services.security_scan.rules import (
    SEVERITY_ORDER,
    RawFinding,
    rules_for_language,
)

logger = logging.getLogger(__name__)

# Cap how much of a project we scan natively to keep runtime bounded (AC2).
_MAX_CONTENT_BYTES = 2_000_000
# Number of snippets handed to the LLM in dual-path mode.
_MAX_LLM_SNIPPETS = 20


class SASTEngine:
    """Pattern-matching SAST engine with an optional LLM dual-path."""

    def __init__(
        self,
        db: AsyncSession | None = None,
        llm_gateway=None,
        engine_mode: str = "native",
    ) -> None:
        self.db = db
        self.llm_gateway = llm_gateway
        self.engine_mode = engine_mode

    # ----- public API ------------------------------------------------------

    def scan_code(self, code: str, language: str | None, file_path: str | None = None) -> list[RawFinding]:
        """Apply native rules to a single source string. Pure + testable."""
        return self._apply_rules(code, language, file_path)

    async def run_sast(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> list[SecurityFinding]:
        """Scan all of a project's code files and return persisted-ready findings."""
        start = time.time()
        files = await self._load_source_files(project_id)

        raw: list[RawFinding] = []
        total_loc = 0
        for file_path, language, content in files:
            total_loc += content.count("\n") + 1
            raw.extend(self._apply_rules(content, language, file_path))

        if self.engine_mode in ("llm", "hybrid") and self.llm_gateway is not None:
            try:
                llm_raw = await self._run_llm_analysis(files, tenant_id)
                raw = self._merge_findings(raw, llm_raw)
            except Exception as exc:  # LLM path must never fail the whole scan
                logger.warning("SAST LLM analysis failed, keeping native results: %s", exc)

        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "SAST project=%s files=%d loc=%d findings=%d in %dms",
            project_id, len(files), total_loc, len(raw), elapsed_ms,
        )

        return [self._to_finding(r, project_id, tenant_id, scan_id) for r in raw]

    # ----- native rule engine ---------------------------------------------

    def _apply_rules(self, code: str, language: str | None, file_path: str | None) -> list[RawFinding]:
        if not code:
            return []
        rules = rules_for_language(language)
        lines = code.splitlines()
        findings: list[RawFinding] = []
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            comment_line = stripped.startswith(("#", "//", "*"))
            if not stripped:
                continue
            for rule in rules:
                for pattern in rule.patterns_for_language(language):
                    # Comment lines only count when the rule deliberately scans
                    # them (e.g. auth-bypass TODO markers).
                    if comment_line and "//" not in pattern.regex.pattern and "#" not in pattern.regex.pattern:
                        continue
                    if pattern.regex.search(line):
                        findings.append(
                            RawFinding(
                                vulnerability_type=rule.vulnerability_type,
                                severity=self._map_severity(rule.vulnerability_type, rule.severity),
                                description=rule.description,
                                file_path=file_path,
                                line_start=idx,
                                line_end=idx,
                                code_snippet=line.strip()[:500],
                                confidence=self._calculate_confidence(rule, line, pattern.confidence_weight),
                                cwe_id=rule.cwe_id,
                                owasp_category=rule.owasp_category,
                                recommendation=rule.recommendation,
                                source="native",
                                rule_id=rule.id,
                            )
                        )
                        break  # one finding per rule per line
        return findings

    @staticmethod
    def _calculate_confidence(rule, line: str, pattern_weight: float = 0.0) -> float:
        """Score a match: base confidence, nudged by tell-tale context."""
        confidence = rule.base_confidence + pattern_weight
        lowered = line.lower()
        # User-input markers raise confidence for injection-style rules.
        if any(token in lowered for token in ("request", "input(", "argv", "params", "req.", "$_")):
            confidence += 0.15
        # A literal-only line (likely a constant/test) lowers it slightly.
        if lowered.count('"') + lowered.count("'") >= 4 and "+" not in lowered:
            confidence -= 0.05
        return round(max(0.1, min(confidence, 0.99)), 2)

    @staticmethod
    def _map_severity(vulnerability_type: str, default: str) -> str:
        """Map a vulnerability type to a severity, falling back to the rule's own."""
        overrides = {
            "command_injection": "critical",
            "sql_injection": "critical",
            "code_injection": "high",
            "insecure_deserialization": "high",
            "hardcoded_secret": "high",
            "xss": "high",
            "weak_cryptography": "medium",
            "path_traversal": "medium",
        }
        return overrides.get(vulnerability_type, default)

    # ----- dual-path LLM ---------------------------------------------------

    async def _run_llm_analysis(
        self,
        files: list[tuple[str | None, str | None, str]],
        tenant_id: uuid.UUID,
    ) -> list[RawFinding]:
        """Ask the LLM for semantic findings on a bounded set of snippets."""
        from app.services.analysis.llm_gateway import LLMMessage

        snippets = files[:_MAX_LLM_SNIPPETS]
        out: list[RawFinding] = []
        for file_path, language, content in snippets:
            prompt = self._build_llm_prompt(content[:6000], language)
            try:
                response = await self.llm_gateway.complete(
                    provider="anthropic",
                    messages=[LLMMessage(role="user", content=prompt)],
                    max_tokens=1500,
                    temperature=0.0,
                    module="security_sast",
                    task_type="sast_semantic",
                )
            except Exception as exc:
                logger.warning("LLM SAST call failed for %s: %s", file_path, exc)
                continue
            out.extend(self._parse_llm_findings(response.content, file_path))
        return out

    @staticmethod
    def _build_llm_prompt(code: str, language: str | None) -> str:
        return (
            "Jesteś ekspertem bezpieczeństwa aplikacji. Przeanalizuj poniższy kod "
            f"({language or 'nieznany język'}) pod kątem podatności semantycznych: "
            "błędów logicznych, brakujących kontroli autoryzacji/walidacji, IDOR, "
            "niebezpiecznych przepływów danych. Zwróć WYŁĄCZNIE JSON: lista obiektów "
            '{"vulnerability_type","severity","line_start","description","cwe_id"}. '
            "severity ∈ critical|high|medium|low. Jeśli brak podatności, zwróć [].\n\n"
            f"```\n{code}\n```"
        )

    @staticmethod
    def _parse_llm_findings(content: str, file_path: str | None) -> list[RawFinding]:
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
        out: list[RawFinding] = []
        for item in items:
            if not isinstance(item, dict) or "vulnerability_type" not in item:
                continue
            severity = str(item.get("severity", "medium")).lower()
            if severity not in SEVERITY_ORDER:
                severity = "medium"
            out.append(
                RawFinding(
                    vulnerability_type=str(item["vulnerability_type"]),
                    severity=severity,
                    description=str(item.get("description", "Podatność wykryta przez LLM.")),
                    file_path=file_path,
                    line_start=item.get("line_start"),
                    line_end=item.get("line_start"),
                    confidence=0.5,
                    cwe_id=item.get("cwe_id"),
                    source="llm",
                )
            )
        return out

    def _merge_findings(self, native: list[RawFinding], llm: list[RawFinding]) -> list[RawFinding]:
        """Deduplicate by (file_path, line_start, vulnerability_type); native wins."""
        index: dict[tuple, RawFinding] = {}
        for f in native:
            index[(f.file_path, f.line_start, f.vulnerability_type)] = f
        for f in llm:
            key = (f.file_path, f.line_start, f.vulnerability_type)
            if key in index:
                index[key].source = "hybrid"
                index[key].confidence = round(min(0.99, index[key].confidence + 0.1), 2)
            else:
                index[key] = f
        return list(index.values())

    # ----- persistence helpers --------------------------------------------

    def _to_finding(
        self,
        raw: RawFinding,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> SecurityFinding:
        return SecurityFinding(
            project_id=project_id,
            tenant_id=tenant_id,
            scan_id=scan_id,
            scan_type=ScanType.SAST,
            vulnerability_type=raw.vulnerability_type,
            severity=Severity(raw.severity),
            cwe_id=raw.cwe_id,
            owasp_category=raw.owasp_category,
            file_path=raw.file_path,
            line_start=raw.line_start,
            line_end=raw.line_end,
            code_snippet=raw.code_snippet,
            description=raw.description,
            confidence=raw.confidence,
            source=AnalysisSource(raw.source),
            recommendation=raw.recommendation,
            finding_metadata={"rule_id": raw.rule_id} if raw.rule_id else None,
        )

    async def _load_source_files(self, project_id: uuid.UUID) -> list[tuple[str | None, str | None, str]]:
        """Load (file_path, language, content) for a project's code files."""
        if self.db is None:
            return []
        from app.core.config import get_settings
        from app.core.storage import download_file_bytes
        from app.models.source_file import FileCategory, SourceFile

        settings = get_settings()
        result = await self.db.execute(
            select(SourceFile).where(
                SourceFile.project_id == project_id,
                SourceFile.file_category == FileCategory.CODE,
                SourceFile.is_cleaned_up == False,  # noqa: E712
            )
        )
        rows = result.scalars().all()
        files: list[tuple[str | None, str | None, str]] = []
        for sf in rows:
            if sf.file_size and sf.file_size > _MAX_CONTENT_BYTES:
                continue
            try:
                import asyncio

                raw = await asyncio.to_thread(
                    download_file_bytes, settings.minio_bucket_name, sf.storage_key
                )
                content = raw.decode("utf-8", errors="replace")
            except Exception as exc:
                logger.warning("SAST: failed to load %s: %s", sf.storage_key, exc)
                continue
            files.append((sf.original_path or sf.filename, sf.detected_language, content))
        return files
