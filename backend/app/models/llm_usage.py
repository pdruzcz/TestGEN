"""LLM usage tracking model for cost monitoring and dashboard."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LLMProvider(StrEnum):
    """LLM provider options."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


class LLMUsage(Base):
    """Track LLM API calls for cost analysis and tenant limits."""

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)

    # Provider info
    provider: Mapped[str] = mapped_column(String(50))  # openai, anthropic
    model: Mapped[str] = mapped_column(String(100))

    # Token usage
    tokens_input: Mapped[int] = mapped_column(Integer)
    tokens_output: Mapped[int] = mapped_column(Integer)
    total_tokens: Mapped[int] = mapped_column(Integer)

    # Cost tracking
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(scale=6, precision=10))

    # Performance
    latency_ms: Mapped[int] = mapped_column(Integer)

    # Context
    module: Mapped[str] = mapped_column(String(100))  # code_analysis, doc_analysis, etc.
    task_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # extract_functions, etc.
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Error tracking
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fallback_to_native: Mapped[bool] = mapped_column(default=False)

    # Metadata
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<LLMUsage(tenant_id={self.tenant_id}, provider={self.provider}, model={self.model}, cost=${self.cost_usd})>"
