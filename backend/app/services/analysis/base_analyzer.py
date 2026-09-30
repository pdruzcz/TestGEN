"""
Dual-path analysis framework with native/LLM/hybrid modes.

All analyzers inherit from BaseAnalyzer and implement:
- analyze_native(): Deterministic analysis (AST, regex, rules)
- analyze_llm(): LLM-based semantic analysis
- merge_results(): Combine results from both paths

Engine modes:
- native: Only native path (no LLM calls)
- llm: Only LLM path
- hybrid: Both paths merged with native as base, LLM as enrichment
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TypeVar

from app.core.config import EngineMode, get_settings
from app.services.analysis.llm_gateway import LLMMessage, LLMProvider, get_llm_gateway

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T", bound="AnalysisResult")


class AnalyzerError(Exception):
    """Base exception for analyzer errors."""
    pass


class NativeAnalysisError(AnalyzerError):
    """Raised when native analysis fails."""
    pass


class LLMAnalysisError(AnalyzerError):
    """Raised when LLM analysis fails."""
    pass


@dataclass
class AnalysisMetrics:
    """Performance metrics for analysis."""
    engine_mode: EngineMode
    native_duration_ms: int = 0
    llm_duration_ms: int = 0
    llm_tokens_input: int = 0
    llm_tokens_output: int = 0
    llm_cost_usd: float = 0.0
    llm_fallback: bool = False
    total_duration_ms: int = 0

    def to_dict(self) -> dict:
        """Convert metrics to dictionary."""
        return {
            "engine_mode": self.engine_mode,
            "native_duration_ms": self.native_duration_ms,
            "llm_duration_ms": self.llm_duration_ms,
            "llm_tokens_input": self.llm_tokens_input,
            "llm_tokens_output": self.llm_tokens_output,
            "llm_cost_usd": self.llm_cost_usd,
            "llm_fallback": self.llm_fallback,
            "total_duration_ms": self.total_duration_ms,
        }


@dataclass
class AnalysisResult:
    """Base class for analysis results."""
    analyzer_name: str
    engine_mode: EngineMode
    success: bool
    data: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: AnalysisMetrics | None = None
    source_path: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "analyzer": self.analyzer_name,
            "engine_mode": self.engine_mode,
            "success": self.success,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "source_path": self.source_path,
            "timestamp": self.timestamp.isoformat(),
        }

    def merge_with(self, other: "AnalysisResult") -> "AnalysisResult":
        """Merge this result with another (for hybrid mode)."""
        if not other.success:
            return self

        merged_data = {**self.data}
        merged_data.update(other.data)

        # Combine warnings
        merged_warnings = list(set(self.warnings + other.warnings))

        return AnalysisResult(
            analyzer_name=self.analyzer_name,
            engine_mode=self.engine_mode,
            success=self.success,
            data=merged_data,
            errors=self.errors,
            warnings=merged_warnings,
            metrics=self.metrics,
            source_path=self.source_path,
            timestamp=self.timestamp,
        )


@dataclass
class NativeResult(AnalysisResult):
    """Result from native analysis path."""
    path: str = "native"


@dataclass
class LLMResult(AnalysisResult):
    """Result from LLM analysis path."""
    path: str = "llm"
    model: str = ""
    provider: str = ""


class BaseAnalyzer(ABC):
    """
    Base class for all analyzers implementing dual-path pattern.

    Subclasses must implement:
    - analyze_native(): Deterministic analysis
    - analyze_llm(): LLM-based analysis
    - merge_results(): Combine both paths
    """

    def __init__(
        self,
        name: str,
        engine_mode: EngineMode | None = None,
        default_llm_provider: LLMProvider = LLMProvider.ANTHROPIC,
        default_llm_model: str | None = None,
        tenant_id: int | None = None,
    ):
        self.name = name
        self.engine_mode = engine_mode or settings.engine_mode
        self.default_llm_provider = default_llm_provider
        self.default_llm_model = default_llm_model
        self.tenant_id = tenant_id
        self._llm_gateway = get_llm_gateway()

    @abstractmethod
    async def analyze_native(self, source_code: str, **context) -> NativeResult:
        """
        Perform native analysis using deterministic algorithms.

        Args:
            source_code: Source code to analyze
            **context: Additional context (filename, language, etc.)

        Returns:
            NativeResult with extracted data

        Raises:
            NativeAnalysisError: If native analysis fails
        """
        pass

    @abstractmethod
    async def analyze_llm(
        self,
        source_code: str,
        prompt_name: str | None = None,
        prompt_version: str | None = None,
        **context,
    ) -> LLMResult:
        """
        Perform LLM-based analysis.

        Args:
            source_code: Source code to analyze
            prompt_name: Name of prompt to use (from prompt repository)
            prompt_version: Prompt version (v1, v2, latest)
            **context: Additional context

        Returns:
            LLMResult with extracted data

        Raises:
            LLMAnalysisError: If LLM analysis fails
        """
        pass

    @abstractmethod
    def merge_results(self, native: NativeResult, llm: LLMResult) -> AnalysisResult:
        """
        Merge results from native and LLM paths.

        Default strategy: native as base, LLM as enrichment.
        Subclasses can override for custom merge logic.

        Args:
            native: Result from native analysis
            llm: Result from LLM analysis

        Returns:
            Merged AnalysisResult
        """
        merged = native.merge_with(llm)
        merged.path = "hybrid"
        return merged

    async def analyze(
        self,
        source_code: str,
        engine_mode: EngineMode | None = None,
        prompt_name: str | None = None,
        prompt_version: str | None = None,
        **context,
    ) -> AnalysisResult:
        """
        Main analysis entry point with automatic routing.

        Args:
            source_code: Source code to analyze
            engine_mode: Override engine mode for this call
            prompt_name: Prompt name for LLM path
            prompt_version: Prompt version for LLM path
            **context: Additional context

        Returns:
            AnalysisResult from appropriate path(s)
        """
        import time

        mode = engine_mode or self.engine_mode
        start_time = time.time()
        metrics = AnalysisMetrics(engine_mode=mode)

        logger.info(f"Starting {self.name} analysis in {mode} mode")

        try:
            if mode == EngineMode.NATIVE:
                return await self._analyze_native_only(source_code, metrics, **context)

            elif mode == EngineMode.LLM:
                return await self._analyze_llm_only(
                    source_code, metrics, prompt_name, prompt_version, **context
                )

            else:  # HYBRID
                return await self._analyze_hybrid(
                    source_code, metrics, prompt_name, prompt_version, **context
                )

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return AnalysisResult(
                analyzer_name=self.name,
                engine_mode=mode,
                success=False,
                errors=[str(e)],
                metrics=metrics,
            )

        finally:
            metrics.total_duration_ms = int((time.time() - start_time) * 1000)

    async def _analyze_native_only(
        self, source_code: str, metrics: AnalysisMetrics, **context
    ) -> AnalysisResult:
        """Run only native path."""
        import time

        start = time.time()
        result = await self.analyze_native(source_code, **context)
        metrics.native_duration_ms = int((time.time() - start) * 1000)
        result.metrics = metrics
        return result

    async def _analyze_llm_only(
        self,
        source_code: str,
        metrics: AnalysisMetrics,
        prompt_name: str | None,
        prompt_version: str | None,
        **context,
    ) -> AnalysisResult:
        """Run only LLM path."""
        import time

        start = time.time()
        result = await self.analyze_llm(source_code, prompt_name, prompt_version, **context)

        metrics.llm_duration_ms = int((time.time() - start) * 1000)
        if hasattr(result, "model"):
            # Extract token info from result data if available
            metrics.llm_tokens_input = result.data.get("tokens_input", 0)
            metrics.llm_tokens_output = result.data.get("tokens_output", 0)
            metrics.llm_cost_usd = result.data.get("cost_usd", 0.0)

        result.metrics = metrics
        return result

    async def _analyze_hybrid(
        self,
        source_code: str,
        metrics: AnalysisMetrics,
        prompt_name: str | None,
        prompt_version: str | None,
        **context,
    ) -> AnalysisResult:
        """Run both paths and merge results."""
        import time

        # Run native path
        native_start = time.time()
        native_result = await self.analyze_native(source_code, **context)
        metrics.native_duration_ms = int((time.time() - native_start) * 1000)

        # Run LLM path
        llm_start = time.time()
        try:
            llm_result = await self.analyze_llm(
                source_code, prompt_name, prompt_version, **context
            )
            metrics.llm_duration_ms = int((time.time() - llm_start) * 1000)
            metrics.llm_tokens_input = llm_result.data.get("tokens_input", 0)
            metrics.llm_tokens_output = llm_result.data.get("tokens_output", 0)
            metrics.llm_cost_usd = llm_result.data.get("cost_usd", 0.0)

            # Merge results
            merged = self.merge_results(native_result, llm_result)
            merged.metrics = metrics
            return merged

        except LLMAnalysisError as e:
            logger.warning(f"LLM analysis failed, falling back to native: {e}")
            metrics.llm_fallback = True
            native_result.metrics = metrics
            native_result.warnings.append(f"LLM analysis failed: {e}")
            return native_result

    def set_tenant(self, tenant_id: int):
        """Set tenant ID for cost tracking."""
        self.tenant_id = tenant_id


def get_analyzer(analyzer_class: type, **kwargs) -> BaseAnalyzer:
    """Factory function to create analyzer instances."""
    return analyzer_class(**kwargs)
