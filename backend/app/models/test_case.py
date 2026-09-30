"""TestCase model — generated test case from analysis - Story 1.31

Extended model with test code, execution tracking, and framework support.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class TestPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestType(StrEnum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    SECURITY = "security"
    PERFORMANCE = "performance"
    POSITIVE = "positive"  # Happy path
    NEGATIVE = "negative"  # Error cases
    BOUNDARY = "boundary"  # Edge cases
    ACCESSIBILITY = "accessibility"
    SEMANTIC = "semantic"
    DATABASE = "database"  # DB layer tests — Story 1.53 (FR70)


class TestFramework(StrEnum):
    PYTEST = "pytest"
    JUNIT = "junit"
    NUNIT = "nunit"
    MOCHA = "mocha"
    JEST = "jest"
    SELENIUM = "selenium"
    PLAYWRIGHT = "playwright"
    APPIUM = "appium"
    CYPRESS = "cypress"
    SIKULIX = "sikulix"
    PHPUNIT = "phpunit"  # PHP — Story 1.55 (FR24/FR12)
    PEST = "pest"  # PHP (DSL nad PHPUnit) — Story 1.55 (FR24/FR12)
    UNITTEST = "unittest"  # Python (natywny) — Story 1.57
    TESTNG = "testng"  # Java — Story 1.57
    MSTEST = "mstest"  # C# — Story 1.57


class TestCaseStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DISABLED = "disabled"


class GenerationEngine(StrEnum):
    NATIVE = "native"  # Template-based
    LLM = "llm"  # AI-powered
    HYBRID = "hybrid"  # Combination


class TestCase(Base, UUIDMixin, TenantMixin, TimestampMixin):
    __tablename__ = "test_cases"

    # Relations
    analysis_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="CASCADE"),
        index=True,
    )
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_files.id", ondelete="SET NULL"),
        default=None,
    )

    # Test metadata
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    priority: Mapped[TestPriority] = mapped_column(
        Enum(TestPriority, name="test_priority", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        default=TestPriority.MEDIUM,
    )
    type: Mapped[TestType] = mapped_column(
        Enum(TestType, name="test_type", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        default=TestType.UNIT,
    )

    # Framework and language
    framework: Mapped[str | None] = mapped_column(String(50), default=None)
    language: Mapped[str | None] = mapped_column(String(50), default=None)
    generation_engine: Mapped[str] = mapped_column(
        Enum(
            GenerationEngine, name="generation_engine", native_enum=True, values_callable=lambda e: [m.value for m in e]
        ),
        default=GenerationEngine.NATIVE,
    )

    # Source code reference
    source_function: Mapped[str | None] = mapped_column(String(255), default=None)
    source_class: Mapped[str | None] = mapped_column(String(255), default=None)
    source_endpoint: Mapped[str | None] = mapped_column(String(255), default=None)

    # Generated test code
    test_code: Mapped[str | None] = mapped_column(Text, default=None)
    imports: Mapped[str | None] = mapped_column(Text, default=None)
    setup_code: Mapped[str | None] = mapped_column(Text, default=None)
    teardown_code: Mapped[str | None] = mapped_column(Text, default=None)

    # Test data and behavior
    preconditions: Mapped[dict | None] = mapped_column(JSONB, default=None)
    steps: Mapped[dict | None] = mapped_column(JSONB, default=None)
    expected_result: Mapped[str | None] = mapped_column(Text, default=None)
    test_data: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Scenario info (for AI-generated tests)
    scenario_description: Mapped[str | None] = mapped_column(Text, default=None)
    scenario_rationale: Mapped[str | None] = mapped_column(Text, default=None)
    edge_case_description: Mapped[str | None] = mapped_column(Text, default=None)
    confidence_score: Mapped[float | None] = mapped_column(Float, default=None)

    # Status and execution
    status: Mapped[str] = mapped_column(
        Enum(TestCaseStatus, name="test_case_status", native_enum=True, values_callable=lambda e: [m.value for m in e]),
        default=TestCaseStatus.DRAFT,
        index=True,
    )

    # Powiązanie z systemem zarządzania testami (Story 8.11, AC5) — wypełniane
    # przez synchronizację, żeby lista przypadków mogła pokazać, gdzie test
    # żyje po drugiej stronie i kiedy ostatnio się z nią zrównał.
    tms_external_id: Mapped[str | None] = mapped_column(String(64), default=None)
    tms_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Execution tracking
    last_executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_execution_result: Mapped[dict | None] = mapped_column(JSONB, default=None)
    execution_count: Mapped[int] = mapped_column(Integer, default=0)
    pass_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)

    # Editing and review
    is_edited: Mapped[bool] = mapped_column(default=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)

    # Tags and meta
    tags: Mapped[dict | None] = mapped_column(JSONB, default=None)  # Array of tag strings
    meta: Mapped[dict | None] = mapped_column(JSONB, default=None)  # Additional metadata

    # Relationships
    analysis_result = relationship("AnalysisResult", lazy="raise")
    source_file = relationship("SourceFile", lazy="raise")
    reviewer = relationship("User", foreign_keys=[reviewed_by], lazy="raise")

    def __repr__(self) -> str:
        try:
            return f"<TestCase id={self.id} title={self.title!r} type={self.type.value} status={self.status.value}>"
        except Exception:
            return "<TestCase (detached)>"

    def to_dict(self) -> dict:
        """Convert test case to dictionary."""
        return {
            "id": str(self.id),
            "analysis_result_id": str(self.analysis_result_id),
            "source_file_id": str(self.source_file_id) if self.source_file_id else None,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value if self.priority else None,
            "type": self.type.value if self.type else None,
            "framework": self.framework,
            "language": self.language,
            "generation_engine": self.generation_engine.value if self.generation_engine else None,
            "source_function": self.source_function,
            "source_class": self.source_class,
            "source_endpoint": self.source_endpoint,
            "test_code": self.test_code,
            "imports": self.imports,
            "setup_code": self.setup_code,
            "teardown_code": self.teardown_code,
            "preconditions": self.preconditions,
            "steps": self.steps,
            "expected_result": self.expected_result,
            "test_data": self.test_data,
            "scenario_description": self.scenario_description,
            "scenario_rationale": self.scenario_rationale,
            "edge_case_description": self.edge_case_description,
            "confidence_score": self.confidence_score,
            "status": self.status.value if self.status else None,
            "last_executed_at": self.last_executed_at.isoformat() if self.last_executed_at else None,
            "last_execution_result": self.last_execution_result,
            "execution_count": self.execution_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "is_edited": self.is_edited,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewed_by": str(self.reviewed_by) if self.reviewed_by else None,
            "tags": self.tags or [],
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TestCaseExecution(Base, UUIDMixin, TimestampMixin):
    """Test case execution result model - Story 1.31"""

    __tablename__ = "test_case_executions"

    test_case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        index=True,
    )

    # Execution info
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    execution_duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)

    # Result
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # passed, failed, skipped, error
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    error_stack_trace: Mapped[str | None] = mapped_column(Text, default=None)

    # Output
    stdout: Mapped[str | None] = mapped_column(Text, default=None)
    stderr: Mapped[str | None] = mapped_column(Text, default=None)

    # Coverage
    lines_covered: Mapped[int | None] = mapped_column(Integer, default=None)
    branches_covered: Mapped[int | None] = mapped_column(Integer, default=None)
    coverage_percentage: Mapped[float | None] = mapped_column(Float, default=None)

    # Environment
    executed_by: Mapped[str | None] = mapped_column(String(100), default=None)  # CI, manual, scheduled
    environment: Mapped[str | None] = mapped_column(String(50), default=None)  # dev, staging, production
    runner_version: Mapped[str | None] = mapped_column(String(100), default=None)

    # Additional data
    meta: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Relationship
    test_case = relationship("TestCase", lazy="raise", back_populates="executions")

    def __repr__(self) -> str:
        try:
            return f"<TestCaseExecution id={self.id} test_case_id={self.test_case_id} status={self.status}>"
        except Exception:
            return "<TestCaseExecution (detached)>"

    def to_dict(self) -> dict:
        """Convert execution to dictionary."""
        return {
            "id": str(self.id),
            "test_case_id": str(self.test_case_id),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "execution_duration_ms": self.execution_duration_ms,
            "status": self.status,
            "error_message": self.error_message,
            "error_stack_trace": self.error_stack_trace,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "lines_covered": self.lines_covered,
            "branches_covered": self.branches_covered,
            "coverage_percentage": self.coverage_percentage,
            "executed_by": self.executed_by,
            "environment": self.environment,
            "runner_version": self.runner_version,
            "meta": self.meta,
        }


# Add back-relationship to TestCase
TestCase.executions = relationship("TestCaseExecution", back_populates="test_case", cascade="all, delete-orphan")
