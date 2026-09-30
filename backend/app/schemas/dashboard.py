"""Pydantic schemas for dashboard endpoints — Epic 6, Story 6.1."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectDashboardItem(BaseModel):
    """Single project row in the dashboard list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    last_analysis_at: datetime | None = None
    compliance_score: float | None = None
    test_cases_count: int = 0
    status: str


class StatisticsCards(BaseModel):
    """Four KPI cards on top of the dashboard."""

    model_config = ConfigDict(extra="ignore")

    total_projects: int
    analyses_this_month: int
    avg_compliance: float | None
    total_test_cases: int = 0
    # Utrzymujemy active_users w modelu, bo backend liczyl go dotychczas i
    # fronend mógłby jeszcze czytać — Story 6.1 AC2 wymaga test case'ów jako
    # 4. karty, ale nie chcemy psuć innych konsumentów pola.
    active_users: int = 0


class PlanUsageResponse(BaseModel):
    """Plan usage widget — visible only for Owner/Admin."""

    model_config = ConfigDict(extra="ignore")

    plan: str
    analyses_used: int
    analyses_limit: int | None  # None = unlimited (Premium)
    projects_count: int


class AuditLogResponse(BaseModel):
    """Single audit log entry in activity feed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict | None = None
    created_at: datetime
    user_email: str | None = None


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""

    model_config = ConfigDict(extra="ignore")

    items: list[AuditLogResponse]
    total: int


class DashboardSummaryResponse(BaseModel):
    """Aggregated dashboard payload (single round-trip from FE)."""

    model_config = ConfigDict(extra="ignore")

    projects: list[ProjectDashboardItem]
    statistics: StatisticsCards
    plan_usage: PlanUsageResponse | None = None
