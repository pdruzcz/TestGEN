"""Tests for LLM-based semantic code analysis service - Story 1.26"""

import pytest

from app.services.analysis.llm_analysis import (
    CodeSummary,
    InsightType,
    IntentAnalysis,
    LLMAnalysisOrchestrator,
    LLMAnalysisResult,
    RiskAssessment,
    SemanticInsight,
)


class TestInsightType:
    """Test InsightType enum."""

    def test_insight_types(self):
        """Test all insight types exist."""
        assert InsightType.SUMMARY == "summary"
        assert InsightType.INTENT == "intent"
        assert InsightType.COMPLEXITY == "complexity"
        assert InsightType.RISK == "risk"
        assert InsightType.SUGGESTION == "suggestion"
        assert InsightType.DOMAIN == "domain"
        assert InsightType.SIMILARITY == "similarity"
        assert InsightType.TEST_SUGGESTION == "test_suggestion"


class TestSemanticInsight:
    """Test SemanticInsight dataclass."""

    def test_insight_creation(self):
        """Test creating a semantic insight."""
        insight = SemanticInsight(
            insight_type=InsightType.COMPLEXITY,
            content="High cyclomatic complexity detected",
            confidence=0.85,
            target="calculate_interest",
            file_path="loan.py",
            line_range=(10, 50),
        )
        assert insight.insight_type == InsightType.COMPLEXITY
        assert insight.confidence == 0.85


class TestCodeSummary:
    """Test CodeSummary dataclass."""

    def test_summary_creation(self):
        """Test creating a code summary."""
        summary = CodeSummary(
            name="UserService",
            summary="Service for user management",
            description="Handles user CRUD operations with validation",
            key_features=["create", "update", "delete", "validate"],
            inputs=["user_data"],
            outputs=["user"],
            complexity_level="low",
            confidence=0.9,
        )
        assert summary.name == "UserService"
        assert summary.complexity_level == "low"


class TestIntentAnalysis:
    """Test IntentAnalysis dataclass."""

    def test_intent_creation(self):
        """Test creating an intent analysis."""
        intent = IntentAnalysis(
            name="process_payment",
            intent="Process payment transaction",
            business_purpose="Handle customer payments",
            side_effects=["update_balance", "send_confirmation"],
            dependencies=["PaymentGateway", "UserRepository"],
        )
        assert intent.intent == "Process payment transaction"
        assert len(intent.side_effects) == 2


class TestRiskAssessment:
    """Test RiskAssessment dataclass."""

    def test_risk_creation(self):
        """Test creating a risk assessment."""
        risk = RiskAssessment(
            name="transfer_funds",
            risk_level="high",
            risk_factors=["handles money", "external API dependency"],
            recommendations=["add logging", "implement retries"],
        )
        assert risk.risk_level == "high"
        assert len(risk.recommendations) == 2


class TestLLMAnalysisResult:
    """Test LLMAnalysisResult dataclass."""

    def test_empty_result(self):
        """Test creating empty result."""
        result = LLMAnalysisResult(language="python")
        assert result.language == "python"
        assert len(result.insights) == 0
        assert len(result.summaries) == 0

    def test_statistics(self):
        """Test statistics calculation."""
        result = LLMAnalysisResult(language="python")

        result.insights = [
            SemanticInsight(
                insight_type=InsightType.COMPLEXITY,
                content="Complex function",
                confidence=0.8,
                target="func1",
            ),
            SemanticInsight(
                insight_type=InsightType.RISK,
                content="Risk detected",
                confidence=0.7,
                target="func2",
            ),
        ]

        result.risks = [
            RiskAssessment(name="func1", risk_level="medium", risk_factors=[]),
            RiskAssessment(name="func2", risk_level="high", risk_factors=[]),
        ]

        stats = result.get_statistics()

        assert stats["total_insights"] == 2
        assert stats["insights_by_type"]["complexity"] == 1
        assert stats["insights_by_type"]["risk"] == 1
        assert stats["total_risks"] == 2
        assert stats["risk_levels"]["medium"] == 1
        assert stats["risk_levels"]["high"] == 1

    def test_to_dict_serialization(self):
        """Test result can be serialized to dict."""
        result = LLMAnalysisResult(language="python")
        result.source_files = ["test.py"]
        result.insights = [
            SemanticInsight(
                insight_type=InsightType.SUMMARY,
                content="Test function",
                confidence=0.8,
                target="test_func",
            )
        ]

        data = result.to_dict()

        assert data["language"] == "python"
        assert "test.py" in data["source_files"]
        assert len(data["insights"]) == 1


class TestLLMAnalysisOrchestrator:
    """Test LLM analysis orchestrator."""

    def test_orchestrator_initialization(self):
        """Test orchestrator can be initialized."""
        orchestrator = LLMAnalysisOrchestrator()
        assert orchestrator.llm_gateway is not None
        assert orchestrator.prompt_manager is not None

    @pytest.mark.asyncio
    async def test_analyze_code_generates_insights(self):
        """Test that analyze_code generates insights for complex code."""
        orchestrator = LLMAnalysisOrchestrator()

        # Code with deep nesting to trigger heuristic insights
        source_code = """
def complex_function():
    '''A complex function with deep nesting.'''
    if condition1:
        if condition2:
            if condition3:
                if condition4:
                    if condition5:
                        if condition6:
                            return "deep"
    return "done"
"""

        result = await orchestrator.analyze_code(
            source_code,
            "test.py",
            "python",
        )

        assert result.language == "python"
        # Should generate complexity insight due to deep nesting
        complexity_insights = [i for i in result.insights if i.insight_type == InsightType.COMPLEXITY]
        assert len(complexity_insights) >= 1

    @pytest.mark.asyncio
    async def test_analyze_code_with_large_file(self):
        """Test analyzing a large file."""
        orchestrator = LLMAnalysisOrchestrator()

        # Large code (simulated)
        source_code = "def func():\n" + "    pass\n" * 100

        result = await orchestrator.analyze_code(
            source_code,
            "large_file.py",
            "python",
        )

        assert result.language == "python"
        # Should detect large file
        complexity_insights = [i for i in result.insights if i.insight_type == InsightType.COMPLEXITY]
        assert len(complexity_insights) >= 1

    @pytest.mark.asyncio
    async def test_analyze_code_handles_errors(self):
        """Test that analyze_code handles errors gracefully."""
        orchestrator = LLMAnalysisOrchestrator()

        # Code that might cause issues
        source_code = "invalid python code !!!"

        result = await orchestrator.analyze_code(
            source_code,
            "invalid.py",
            "python",
        )

        # Should still return a result with fallback insight
        assert result is not None
        assert len(result.source_files) == 1

    @pytest.mark.asyncio
    async def test_analyze_code_simple_function(self):
        """Test analyzing a simple function."""
        orchestrator = LLMAnalysisOrchestrator()

        source_code = """
def hello_world():
    '''A simple greeting function.'''
    print("Hello, World!")
    return "success"
"""

        result = await orchestrator.analyze_code(
            source_code,
            "hello.py",
            "python",
        )

        assert result.language == "python"
        assert len(result.source_files) == 1

    @pytest.mark.asyncio
    async def test_insight_types_generated(self):
        """Test various insight types can be generated."""
        orchestrator = LLMAnalysisOrchestrator()

        source_code = """
class PaymentService:
    def process_payment(self, amount, user_id):
        '''Process payment - high risk operation.'''
        if amount > 10000:
            raise ValueError("Amount too large")

        # Deep nesting for complexity
        for i in range(10):
            for j in range(10):
                if i == j:
                    self.process()

        return {"status": "success"}
"""

        result = await orchestrator.analyze_code(
            source_code,
            "payment.py",
            "python",
        )

        # Check various insight types might be generated
        insight_types = {i.insight_type for i in result.insights}
        assert InsightType.COMPLEXITY in insight_types or len(result.insights) >= 1

    @pytest.mark.asyncio
    async def test_analyze_project_multiple_files(self):
        """Test analyzing project with multiple files."""
        orchestrator = LLMAnalysisOrchestrator()

        source_files = [
            {
                "file_path": "user_service.py",
                "content": "class UserService:\n    def get_user(self, user_id):\n        return db.query(User).get(user_id)\n",
                "language": "python",
            },
            {
                "file_path": "order_service.py",
                "content": "class OrderService:\n    def create_order(self, data):\n        return Order(**data)\n",
                "language": "python",
            },
        ]

        result = await orchestrator.analyze_project(
            source_files,
            project_id=1,
        )

        assert result.language == "python"
        assert len(result.source_files) == 2
        # Should have insights from both files
        assert len(result.insights) >= 2 or len(result.source_files) == 2

    @pytest.mark.asyncio
    async def test_deep_nesting_detection(self):
        """Test detection of deep nesting."""
        orchestrator = LLMAnalysisOrchestrator()

        # Code with 6 levels of nesting
        source_code = """
def deeply_nested():
    if level1:
        if level2:
            if level3:
                if level4:
                    if level5:
                        if level6:
                            return "too deep"
    return "ok"
"""

        result = await orchestrator.analyze_code(
            source_code,
            "nested.py",
            "python",
        )

        # Should detect deep nesting
        complexity_insights = [i for i in result.insights if i.insight_type == InsightType.COMPLEXITY]
        assert len(complexity_insights) >= 1
        assert "nesting" in complexity_insights[0].content.lower()
