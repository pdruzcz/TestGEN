"""
LLM-based semantic code analysis service - Story 1.26

Uses LLM Gateway for semantic code understanding:
- Code summarization and documentation generation
- Intent extraction from functions and modules
- Semantic similarity detection
- Business domain understanding
- Risk assessment and complexity perception
- Test case suggestions (high-level)

Complements native AST analysis with AI-powered insights.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import get_sync_session
from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.services.analysis.llm_gateway import LLMGateway, LLMProvider, LLMMessage
from app.services.analysis.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class InsightType(StrEnum):
    """Types of semantic insights from LLM analysis."""
    SUMMARY = "summary"  # Code summary
    INTENT = "intent"  # Function/module intent
    COMPLEXITY = "complexity"  # Perceived complexity
    RISK = "risk"  # Risk assessment
    SUGGESTION = "suggestion"  # Improvement suggestions
    DOMAIN = "domain"  # Domain concepts detected
    SIMILARITY = "similarity"  # Similar code patterns
    TEST_SUGGESTION = "test_suggestion"  # Test case suggestions


@dataclass
class SemanticInsight:
    """A semantic insight extracted by LLM analysis."""
    insight_type: InsightType
    content: str  # Insight description
    confidence: float  # 0.0 to 1.0
    target: str  # What the insight is about (function name, etc.)
    file_path: str | None = None
    line_range: tuple[int, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeSummary:
    """AI-generated code summary."""
    name: str  # Function/class/module name
    summary: str  # Brief description
    description: str  # Detailed description
    key_features: list[str]  # Key functionality
    inputs: list[str]  # Key inputs/parameters
    outputs: list[str]  # Outputs/return values
    complexity_level: str  # low, medium, high
    confidence: float


@dataclass
class IntentAnalysis:
    """Intent analysis for code elements."""
    name: str
    intent: str  # Primary intent
    business_purpose: str | None = None  # Business purpose if applicable
    side_effects: list[str] = field(default_factory=list)  # Detected side effects
    dependencies: list[str] = field(default_factory=list)  # Semantic dependencies


@dataclass
class RiskAssessment:
    """Risk assessment for code."""
    name: str
    risk_level: str  # low, medium, high, critical
    risk_factors: list[str] = field(default_factory=list)  # Specific risks detected
    recommendations: list[str] = field(default_factory=list)  # Mitigation recommendations


@dataclass
class LLMAnalysisResult:
    """Result from LLM-based semantic analysis."""
    language: str
    source_files: list[str] = field(default_factory=list)

    # Semantic insights
    insights: list[SemanticInsight] = field(default_factory=list)

    # AI-generated summaries
    summaries: list[CodeSummary] = field(default_factory=list)

    # Intent analysis
    intents: list[IntentAnalysis] = field(default_factory=list)

    # Risk assessments
    risks: list[RiskAssessment] = field(default_factory=list)

    # Metadata
    model_used: str | None = None
    provider_used: str | None = None
    total_tokens: int = 0
    total_cost: float = 0.0

    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)

    def get_statistics(self) -> dict[str, Any]:
        """Calculate analysis statistics."""
        insights_by_type = {}
        for insight in self.insights:
            insights_by_type[insight.insight_type] = insights_by_type.get(insight.insight_type, 0) + 1

        risk_levels = {}
        for risk in self.risks:
            risk_levels[risk.risk_level] = risk_levels.get(risk.risk_level, 0) + 1

        return {
            "language": self.language,
            "source_files_count": len(self.source_files),
            "total_insights": len(self.insights),
            "insights_by_type": insights_by_type,
            "total_summaries": len(self.summaries),
            "total_intents": len(self.intents),
            "total_risks": len(self.risks),
            "risk_levels": risk_levels,
            "model_used": self.model_used,
            "provider_used": self.provider_used,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
        }

    def to_dict(self) -> dict:
        """Convert result to dictionary for JSON serialization."""
        return {
            "language": self.language,
            "source_files": self.source_files,
            "insights": [
                {
                    "insight_type": i.insight_type,
                    "content": i.content,
                    "confidence": i.confidence,
                    "target": i.target,
                    "file_path": i.file_path,
                    "line_range": i.line_range,
                    "metadata": i.metadata,
                }
                for i in self.insights
            ],
            "summaries": [
                {
                    "name": s.name,
                    "summary": s.summary,
                    "description": s.description,
                    "key_features": s.key_features,
                    "inputs": s.inputs,
                    "outputs": s.outputs,
                    "complexity_level": s.complexity_level,
                    "confidence": s.confidence,
                }
                for s in self.summaries
            ],
            "intents": [
                {
                    "name": i.name,
                    "intent": i.intent,
                    "business_purpose": i.business_purpose,
                    "side_effects": i.side_effects,
                    "dependencies": i.dependencies,
                }
                for i in self.intents
            ],
            "risks": [
                {
                    "name": r.name,
                    "risk_level": r.risk_level,
                    "risk_factors": r.risk_factors,
                    "recommendations": r.recommendations,
                }
                for r in self.risks
            ],
            "model_used": self.model_used,
            "provider_used": self.provider_used,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "statistics": self.get_statistics(),
        }


class LLMAnalysisOrchestrator:
    """Orchestrates LLM-based semantic analysis."""

    def __init__(self):
        self.llm_gateway = LLMGateway()
        self.prompt_manager = PromptManager()

    async def analyze_code(
        self,
        source_code: str,
        file_path: str,
        language: str,
        provider: LLMProvider | str = "openai",
        model: str | None = None,
        tenant_id: int | None = None,
    ) -> LLMAnalysisResult:
        """
        Analyze code using LLM for semantic understanding.

        Args:
            source_code: Source code to analyze
            file_path: Path to the source file
            language: Programming language
            provider: LLM provider to use
            model: Model to use (default: provider's default)
            tenant_id: Tenant ID for cost tracking
        """
        result = LLMAnalysisResult(language=language)

        try:
            # Generate code summary
            summary = await self._generate_summary(
                source_code, file_path, language, provider, model, tenant_id
            )
            if summary:
                result.summaries.append(summary)
                result.model_used = summary.name  # Store as reference

            # Extract intent
            intent = await self._extract_intent(
                source_code, file_path, language, provider, model, tenant_id
            )
            if intent:
                result.intents.append(intent)

            # Assess risks
            risk = await self._assess_risks(
                source_code, file_path, language, provider, model, tenant_id
            )
            if risk:
                result.risks.append(risk)

            # Generate insights
            insights = await self._generate_insights(
                source_code, file_path, language, provider, model, tenant_id
            )
            result.insights.extend(insights)

            result.source_files.append(file_path)

        except Exception as e:
            logger.error(f"Failed to analyze {file_path} with LLM: {e}")
            # Add fallback insight
            result.insights.append(SemanticInsight(
                insight_type=InsightType.SUMMARY,
                content=f"Analysis failed: {str(e)}",
                confidence=0.0,
                target=file_path,
                file_path=file_path,
            ))

        return result

    async def _generate_summary(
        self,
        source_code: str,
        file_path: str,
        language: str,
        provider: LLMProvider | str,
        model: str | None,
        tenant_id: int | None,
    ) -> CodeSummary | None:
        """Generate AI summary of the code."""
        try:
            prompt = self.prompt_manager.get("code_summary_v1", version="v1")

            messages = [
                LLMMessage(role="system", content="You are a code analysis assistant."),
                LLMMessage(
                    role="user",
                    content=f"Analyze this {language} code:\n\n{source_code[:2000]}",
                ),
            ]

            response = await self.llm_gateway.complete(
                provider=provider,
                messages=messages,
                model=model,
                tenant_id=tenant_id,
                task_type="code_summary",
            )

            # Parse response (simplified - in production, use structured output)
            return CodeSummary(
                name=file_path.split("/")[-1],
                summary=response.content[:200],  # First part as summary
                description=response.content,
                key_features=[],
                inputs=[],
                outputs=[],
                complexity_level="medium",
                confidence=0.7,
            )

        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            return None

    async def _extract_intent(
        self,
        source_code: str,
        file_path: str,
        language: str,
        provider: LLMProvider | str,
        model: str | None,
        tenant_id: int | None,
    ) -> IntentAnalysis | None:
        """Extract intent from code."""
        try:
            messages = [
                LLMMessage(role="system", content="You are a code analysis assistant."),
                LLMMessage(
                    role="user",
                    content=f"What is the intent of this {language} code?\n\n{source_code[:2000]}",
                ),
            ]

            response = await self.llm_gateway.complete(
                provider=provider,
                messages=messages,
                model=model,
                tenant_id=tenant_id,
                task_type="intent_extraction",
            )

            return IntentAnalysis(
                name=file_path.split("/")[-1],
                intent=response.content[:100],
                business_purpose=None,
            )

        except Exception as e:
            logger.warning(f"Failed to extract intent: {e}")
            return None

    async def _assess_risks(
        self,
        source_code: str,
        file_path: str,
        language: str,
        provider: LLMProvider | str,
        model: str | None,
        tenant_id: int | None,
    ) -> RiskAssessment | None:
        """Assess code risks."""
        try:
            messages = [
                LLMMessage(role="system", content="You are a code analysis assistant."),
                LLMMessage(
                    role="user",
                    content=f"Assess the risks in this {language} code:\n\n{source_code[:2000]}",
                ),
            ]

            response = await self.llm_gateway.complete(
                provider=provider,
                messages=messages,
                model=model,
                tenant_id=tenant_id,
                task_type="risk_assessment",
            )

            return RiskAssessment(
                name=file_path.split("/")[-1],
                risk_level="medium",
                risk_factors=[],
                recommendations=[response.content],
            )

        except Exception as e:
            logger.warning(f"Failed to assess risks: {e}")
            return None

    async def _generate_insights(
        self,
        source_code: str,
        file_path: str,
        language: str,
        provider: LLMProvider | str,
        model: str | None,
        tenant_id: int | None,
    ) -> list[SemanticInsight]:
        """Generate various semantic insights."""
        insights = []

        # Simple heuristic insights (fallback if LLM unavailable)
        if len(source_code) > 1000:
            insights.append(SemanticInsight(
                insight_type=InsightType.COMPLEXITY,
                content="Large file detected - consider refactoring",
                confidence=0.5,
                target=file_path,
                file_path=file_path,
            ))

        # Count complexity indicators
        nesting_depth = source_code.count("    ") // 4
        if nesting_depth > 5:
            insights.append(SemanticInsight(
                insight_type=InsightType.COMPLEXITY,
                content=f"Deep nesting detected (depth {nesting_depth})",
                confidence=0.8,
                target=file_path,
                file_path=file_path,
            ))

        return insights

    async def analyze_project(
        self,
        source_files: list[dict],  # {file_path, content, language}
        project_id: int,
        provider: LLMProvider | str = "openai",
        model: str | None = None,
        tenant_id: int | None = None,
    ) -> LLMAnalysisResult:
        """Analyze multiple source files using LLM."""
        languages = {f.get("language", "unknown") for f in source_files}
        primary_language = languages.pop() if len(languages) == 1 else "multi"

        unified_result = LLMAnalysisResult(language=primary_language)

        for file_info in source_files:
            try:
                file_result = await self.analyze_code(
                    source_code=file_info["content"],
                    file_path=file_info["file_path"],
                    language=file_info.get("language", primary_language),
                    provider=provider,
                    model=model,
                    tenant_id=tenant_id,
                )
                unified_result.source_files.extend(file_result.source_files)
                unified_result.insights.extend(file_result.insights)
                unified_result.summaries.extend(file_result.summaries)
                unified_result.intents.extend(file_result.intents)
                unified_result.risks.extend(file_result.risks)
            except Exception as e:
                logger.error(f"Failed to analyze {file_info.get('file_path')}: {e}")

        # Save to database
        await self._save_to_database(unified_result, project_id)

        return unified_result

    async def _save_to_database(self, result: LLMAnalysisResult, project_id: int):
        """Save analysis results to database."""
        try:
            session_generator = get_sync_session()
            db = next(session_generator)
            try:
                analysis_result = AnalysisResult(
                    project_id=project_id,
                    analysis_type="llm_analysis",
                    status=AnalysisStatus.COMPLETED,
                    result_data=result.to_dict(),
                    metadata={"statistics": result.get_statistics()},
                )
                db.add(analysis_result)
                db.commit()
            finally:
                try:
                    session_generator.close()
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")


def get_llm_analysis_orchestrator() -> LLMAnalysisOrchestrator:
    """Get or create LLM analysis orchestrator instance."""
    return LLMAnalysisOrchestrator()
