"""Taint analyzer — Epic 4, Story 4.3.

Forward taint analysis tracking attacker-controlled data from sources to dangerous
sinks. As elsewhere in the security module (Stories 4.1-4.2) tree-sitter is not
guaranteed present, so the control-flow graph is approximated by a line-ordered
forward pass over raw source: variable assignments propagate taint, sanitizer
calls clear it (per sink type), and tainted data arriving at a sink yields a
finding carrying the full ``taint_path``. Cross-function tracking is limited to a
single file (cross-file is a later phase).
"""

import logging
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.security_finding import (
    AnalysisSource,
    ScanType,
    SecurityFinding,
    Severity,
)
from app.services.security_scan.rules import owasp_for
from app.services.security_scan.taint_definitions import (
    sanitizers_for_language,
    sinks_for_language,
    sources_for_language,
)

logger = logging.getLogger(__name__)

_MAX_CONTENT_BYTES = 2_000_000
# Single `=` assignment (not ==, !=, <=, >=, +=, etc.).
_ASSIGN_RE = re.compile(r"^\s*(?:let|const|var|final|public|private|static|[\w<>\[\]]+\s+)?"
                        r"([A-Za-z_$][\w$.]*)\s*=\s*(?!=)(.+)$")
_IDENT_RE = re.compile(r"[A-Za-z_$][\w$]*")


@dataclass
class TaintPathStep:
    """One hop on a taint path, surfaced to the UI viewer."""

    file_path: str | None
    line: int
    variable: str | None
    operation: str
    node_type: str  # source / transform / sanitizer / sink

    def to_dict(self) -> dict:
        return {
            "file": self.file_path,
            "line": self.line,
            "variable": self.variable,
            "operation": self.operation,
            "node_type": self.node_type,
        }


@dataclass
class TaintPath:
    """A complete source -> ... -> sink flow."""

    source_name: str
    sink_name: str
    sink_type: str
    taint_type: str
    vulnerability_type: str
    cwe_id: str
    severity: str
    variable: str | None
    steps: list[TaintPathStep] = field(default_factory=list)
    sanitizer_name: str | None = None
    sanitizer_adequate: bool = True
    file_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None


@dataclass
class _TaintState:
    """Tracked taint for a single variable during the forward pass."""

    source_name: str
    taint_type: str
    steps: list[TaintPathStep]
    protected_against: frozenset[str] = frozenset()
    sanitizer_name: str | None = None


class TaintAnalyzer:
    """Line-based forward taint analysis over a project's source files.

    With ``engine_mode`` in ``llm``/``hybrid`` (Story 4.13) an LLM taint pass
    augments the deterministic flows with cross-function/cross-abstraction paths,
    merged by (file_path, line_start, vulnerability_type) with native as base.
    """

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

    def analyze_code(
        self,
        code: str,
        language: str | None,
        file_path: str | None = None,
    ) -> list[TaintPath]:
        """Analyze a single source string. Pure + testable."""
        if not code:
            return []
        sources = sources_for_language(language)
        sinks = sinks_for_language(language)
        sanitizers = sanitizers_for_language(language)

        tainted: dict[str, _TaintState] = {}
        paths: list[TaintPath] = []

        for idx, line in enumerate(code.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "*")):
                continue

            # 1) Sink check first, against the taint state built so far.
            self._check_sinks(line, idx, file_path, tainted, sinks, sources, paths)

            # 2) Then update taint state from this line's assignment.
            self._apply_assignment(line, idx, file_path, tainted, sources, sanitizers)

        return paths

    async def run_taint_analysis(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> list[SecurityFinding]:
        """Analyze every code file of a project and return persisted-ready findings."""
        files = await self._load_source_files(project_id)
        findings: list[SecurityFinding] = []
        for file_path, language, content in files:
            for path in self.analyze_code(content, language, file_path):
                findings.append(self._to_finding(path, project_id, tenant_id, scan_id))

        if self.engine_mode in ("llm", "hybrid") and self.llm_gateway is not None:
            try:
                findings = await self._merge_llm_path(findings, files, project_id, tenant_id, scan_id)
            except Exception as exc:  # LLM path must never fail the whole scan
                logger.warning("Taint LLM analysis failed, keeping native results: %s", exc)

        logger.info(
            "Taint project=%s files=%d findings=%d", project_id, len(files), len(findings)
        )
        return findings

    async def _merge_llm_path(
        self,
        native: list[SecurityFinding],
        files: list[tuple[str | None, str | None, str]],
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> list[SecurityFinding]:
        """Run the LLM taint analyzer and merge with native findings (Story 4.13)."""
        from app.services.security_scan.llm_security.llm_taint import LLMTaintAnalyzer

        llm_raw = await LLMTaintAnalyzer(self.llm_gateway).analyze(files, tenant_id)
        index: dict[tuple, SecurityFinding] = {
            (f.file_path, f.line_start, f.vulnerability_type): f for f in native
        }
        for raw in llm_raw:
            key = (raw.file_path, raw.line_start, raw.vulnerability_type)
            base = index.get(key)
            if base is not None:
                base.source = AnalysisSource.HYBRID
                base.confidence = round(min(0.99, base.confidence + 0.1), 2)
            else:
                index[key] = SecurityFinding(
                    project_id=project_id,
                    tenant_id=tenant_id,
                    scan_id=scan_id,
                    scan_type=ScanType.TAINT,
                    vulnerability_type=raw.vulnerability_type,
                    severity=Severity(raw.severity),
                    cwe_id=raw.cwe_id,
                    owasp_category=owasp_for(raw.vulnerability_type),
                    file_path=raw.file_path,
                    line_start=raw.line_start,
                    line_end=raw.line_end,
                    description=raw.description,
                    confidence=raw.confidence,
                    source=AnalysisSource.LLM,
                    taint_path=raw.metadata or None,
                )
        return list(index.values())

    # ----- forward pass internals -----------------------------------------

    def _apply_assignment(
        self,
        line: str,
        idx: int,
        file_path: str | None,
        tainted: dict[str, _TaintState],
        sources,
        sanitizers,
    ) -> None:
        match = _ASSIGN_RE.match(line)
        if not match:
            return
        lhs, rhs = match.group(1), match.group(2)
        # Strip trailing member access: a.b = ... taints `a` conservatively.
        lhs_name = lhs.split(".")[0]

        # a) Direct source assignment.
        src = next((s for s in sources if s.matches(rhs)), None)
        if src is not None:
            step = TaintPathStep(file_path, idx, lhs_name, line.strip()[:200], "source")
            tainted[lhs_name] = _TaintState(src.name, src.taint_type, [step])
            return

        # b) Propagation from an already-tainted variable referenced on the RHS.
        rhs_idents = set(_IDENT_RE.findall(rhs))
        upstream = next(
            (tainted[name] for name in rhs_idents if name in tainted),
            None,
        )
        if upstream is None:
            return

        protected = set(upstream.protected_against)
        sanitizer_name = upstream.sanitizer_name
        node_type = "transform"
        san = next((s for s in sanitizers if s.matches(rhs)), None)
        if san is not None:
            protected |= set(san.protects_against)
            sanitizer_name = san.name
            node_type = "sanitizer"

        new_steps = [*upstream.steps, TaintPathStep(file_path, idx, lhs_name, line.strip()[:200], node_type)]
        tainted[lhs_name] = _TaintState(
            upstream.source_name,
            upstream.taint_type,
            new_steps,
            frozenset(protected),
            sanitizer_name,
        )

    def _check_sinks(
        self,
        line: str,
        idx: int,
        file_path: str | None,
        tainted: dict[str, _TaintState],
        sinks,
        sources,
        paths: list[TaintPath],
    ) -> None:
        sink = next((s for s in sinks if s.matches(line)), None)
        if sink is None:
            return
        idents = set(_IDENT_RE.findall(line))

        # A tainted variable flowing into the sink.
        var = next((name for name in idents if name in tainted), None)
        if var is not None:
            state = tainted[var]
            adequate = sink.sink_type in state.protected_against
            if adequate:
                return  # properly sanitized for this sink — not a finding
            sink_step = TaintPathStep(file_path, idx, var, line.strip()[:200], "sink")
            paths.append(
                self._build_path(
                    sink, state.source_name, state.taint_type, var,
                    [*state.steps, sink_step], file_path,
                    sanitizer_name=state.sanitizer_name,
                    sanitizer_adequate=not state.sanitizer_name,
                )
            )
            return

        # A source used directly inside the sink on the same line.
        src = next((s for s in sources if s.matches(line)), None)
        if src is not None:
            sink_step = TaintPathStep(file_path, idx, None, line.strip()[:200], "sink")
            source_step = TaintPathStep(file_path, idx, None, line.strip()[:200], "source")
            paths.append(
                self._build_path(
                    sink, src.name, src.taint_type, None,
                    [source_step, sink_step], file_path,
                )
            )

    @staticmethod
    def _build_path(
        sink,
        source_name: str,
        taint_type: str,
        variable: str | None,
        steps: list[TaintPathStep],
        file_path: str | None,
        sanitizer_name: str | None = None,
        sanitizer_adequate: bool = True,
    ) -> TaintPath:
        lines = [s.line for s in steps]
        return TaintPath(
            source_name=source_name,
            sink_name=sink.name,
            sink_type=sink.sink_type,
            taint_type=taint_type,
            vulnerability_type=sink.vulnerability_type,
            cwe_id=sink.cwe_id,
            severity=sink.severity,
            variable=variable,
            steps=steps,
            sanitizer_name=sanitizer_name,
            sanitizer_adequate=sanitizer_adequate,
            file_path=file_path,
            line_start=min(lines) if lines else None,
            line_end=max(lines) if lines else None,
        )

    # ----- persistence -----------------------------------------------------

    def _to_finding(
        self,
        path: TaintPath,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
    ) -> SecurityFinding:
        if path.sanitizer_name and not path.sanitizer_adequate:
            description = (
                f"Niebezpieczny przepływ danych: {path.source_name} → {path.sink_name}. "
                f"Zastosowany sanitizer '{path.sanitizer_name}' nie chroni przed "
                f"ujściem typu '{path.sink_type}'."
            )
            confidence = 0.55
        else:
            description = (
                f"Niebezpieczny przepływ danych ({path.taint_type}): "
                f"{path.source_name} → {path.sink_name} bez sanityzacji."
            )
            confidence = 0.7
        return SecurityFinding(
            project_id=project_id,
            tenant_id=tenant_id,
            scan_id=scan_id,
            scan_type=ScanType.TAINT,
            vulnerability_type=path.vulnerability_type,
            severity=Severity(path.severity),
            cwe_id=path.cwe_id,
            owasp_category=owasp_for(path.vulnerability_type),
            file_path=path.file_path,
            line_start=path.line_start,
            line_end=path.line_end,
            code_snippet=path.steps[-1].operation if path.steps else None,
            description=description,
            confidence=confidence,
            source=AnalysisSource.NATIVE,
            taint_path={
                "source": path.source_name,
                "sink": path.sink_name,
                "sink_type": path.sink_type,
                "taint_type": path.taint_type,
                "variable": path.variable,
                "sanitizer": path.sanitizer_name,
                "sanitizer_adequate": path.sanitizer_adequate,
                "path": [s.to_dict() for s in path.steps],
            },
        )

    async def _load_source_files(
        self, project_id: uuid.UUID
    ) -> list[tuple[str | None, str | None, str]]:
        if self.db is None:
            return []
        import asyncio

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
        files: list[tuple[str | None, str | None, str]] = []
        for sf in result.scalars().all():
            if sf.file_size and sf.file_size > _MAX_CONTENT_BYTES:
                continue
            try:
                raw = await asyncio.to_thread(
                    download_file_bytes, settings.minio_bucket_name, sf.storage_key
                )
                content = raw.decode("utf-8", errors="replace")
            except Exception as exc:
                logger.warning("Taint: failed to load %s: %s", sf.storage_key, exc)
                continue
            files.append((sf.original_path or sf.filename, sf.detected_language, content))
        return files
