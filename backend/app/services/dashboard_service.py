"""Dashboard service — Epic 6, Story 6.1.

Aggregates data from multiple sources (projects, compliance_snapshots,
analysis_results, test_cases, user_tenants, audit_logs) into a single
dashboard payload.

Activity feed reuses `audit_service.query_logs()` — no new tables.
Plan usage reads Redis counter via QuotaService.get_usage().
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis_result import AnalysisResult, AnalysisStatus
from app.models.compliance_snapshot import ComplianceSnapshot
from app.models.project import Project
from app.models.tenant import PlanType, Tenant
from app.models.test_case import TestCase
from app.models.user import User
from app.models.user_tenant import UserTenant
from app.schemas.dashboard import (
    AuditLogListResponse,
    AuditLogResponse,
    DashboardSummaryResponse,
    PlanUsageResponse,
    ProjectDashboardItem,
    StatisticsCards,
)
from app.services.admin.audit_service import query_logs as query_audit_logs
from app.services.quota_service import QuotaService

logger = logging.getLogger(__name__)


def _is_owner_or_admin(current_user: User) -> bool:
    """Check if user can see plan usage widget."""
    if getattr(current_user, "is_admin", False):
        return True
    role = getattr(current_user, "_tenant_role", "user")
    return role == "owner"


async def _fetch_project_rows(db: AsyncSession, tenant_id: uuid.UUID) -> list[ProjectDashboardItem]:
    """Fetch projects with latest compliance snapshot and test case count.

    Uses LATERAL subquery for the latest snapshot per project to avoid N+1.
    """
    # Latest snapshot per project — LATERAL join
    latest_snapshot = (
        select(ComplianceSnapshot.score)
        .where(ComplianceSnapshot.project_id == Project.id)
        .order_by(ComplianceSnapshot.created_at.desc())
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )

    # Latest analysis timestamp per project
    latest_analysis = (
        select(AnalysisResult.completed_at)
        .where(
            AnalysisResult.project_id == Project.id,
            AnalysisResult.status == AnalysisStatus.COMPLETED,
        )
        .order_by(AnalysisResult.completed_at.desc().nullslast())
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )

    # Test case count per project — through analysis_results join
    tc_count = (
        select(func.count(TestCase.id))
        .where(
            TestCase.analysis_result_id == AnalysisResult.id,
            AnalysisResult.project_id == Project.id,
        )
        .correlate(Project)
        .scalar_subquery()
    )

    stmt = (
        select(
            Project.id,
            Project.name,
            Project.status,
            latest_snapshot.label("compliance_score"),
            latest_analysis.label("last_analysis_at"),
            tc_count.label("test_cases_count"),
        )
        .where(Project.tenant_id == tenant_id, Project.is_deleted.is_(False))
        .order_by(Project.created_at.desc())
    )

    result = await db.execute(stmt)
    rows = result.all()
    return [
        ProjectDashboardItem(
            id=row.id,
            name=row.name,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            compliance_score=row.compliance_score,
            last_analysis_at=row.last_analysis_at,
            test_cases_count=row.test_cases_count or 0,
        )
        for row in rows
    ]


async def _compute_statistics(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_ids: list[uuid.UUID],
) -> StatisticsCards:
    """Compute the 4 statistics cards."""
    # Total projects
    total_projects = len(project_ids)

    # Analyses this month
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    analyses_stmt = select(func.count(AnalysisResult.id)).where(
        AnalysisResult.tenant_id == tenant_id,
        AnalysisResult.completed_at >= month_start,
        AnalysisResult.status == AnalysisStatus.COMPLETED,
    )
    analyses_this_month = (await db.execute(analyses_stmt)).scalar_one() if total_projects >= 0 else 0

    # Avg compliance from latest snapshot per project
    avg_compliance: float | None = None
    if project_ids:
        # For each project pick its latest snapshot, then average
        latest_per_project = (
            select(
                ComplianceSnapshot.project_id,
                func.max(ComplianceSnapshot.created_at).label("max_created"),
            )
            .where(ComplianceSnapshot.project_id.in_(project_ids))
            .group_by(ComplianceSnapshot.project_id)
            .subquery()
        )
        avg_stmt = select(func.avg(ComplianceSnapshot.score)).join(
            latest_per_project,
            (ComplianceSnapshot.project_id == latest_per_project.c.project_id)
            & (ComplianceSnapshot.created_at == latest_per_project.c.max_created),
        )
        avg_compliance = (await db.execute(avg_stmt)).scalar_one_or_none()

    # Total test cases across tenant — Story 6.1 AC2: 4. karta statystyki.
    # TestCase nie ma tenant_id bezpośrednio — łączymy przez AnalysisResult.
    tc_total_stmt = (
        select(func.count(TestCase.id))
        .join(
            AnalysisResult,
            TestCase.analysis_result_id == AnalysisResult.id,
        )
        .where(AnalysisResult.tenant_id == tenant_id)
    )
    total_test_cases = (await db.execute(tc_total_stmt)).scalar_one()

    # Active users in tenant (distinct users in user_tenants) — utrzymujemy
    # dla ewentualnych innych konsumentów, mimo że dashboard FE już tego
    # nie renderuje jako 4. karty (zastąpione przez total_test_cases).
    active_users_stmt = select(func.count(UserTenant.user_id.distinct())).where(UserTenant.tenant_id == tenant_id)
    active_users = (await db.execute(active_users_stmt)).scalar_one()

    return StatisticsCards(
        total_projects=total_projects,
        analyses_this_month=analyses_this_month or 0,
        avg_compliance=float(avg_compliance) if avg_compliance is not None else None,
        total_test_cases=total_test_cases or 0,
        active_users=active_users or 0,
    )


async def _compute_plan_usage(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    current_user: User,
    total_projects: int,
) -> PlanUsageResponse | None:
    """Plan usage widget — only for Owner/Admin."""
    if not _is_owner_or_admin(current_user):
        return None

    # Get tenant plan
    tenant_stmt = select(Tenant.plan).where(Tenant.id == tenant_id)
    plan_value = (await db.execute(tenant_stmt)).scalar_one_or_none()
    plan: PlanType = plan_value if isinstance(plan_value, PlanType) else PlanType.FREEMIUM

    try:
        quota = QuotaService().get_usage(tenant_id, plan)
    except Exception as exc:  # Redis down? don't break dashboard
        logger.warning("QuotaService.get_usage failed: %s", exc)
        quota = {
            "plan": plan.value,
            "analyses_used": 0,
            "analyses_limit": 0,
        }

    return PlanUsageResponse(
        plan=quota["plan"],
        analyses_used=quota["analyses_used"],
        analyses_limit=quota["analyses_limit"],
        projects_count=total_projects,
    )


async def get_summary(db: AsyncSession, tenant_id: uuid.UUID, current_user: User) -> DashboardSummaryResponse:
    """Build full dashboard summary."""
    projects = await _fetch_project_rows(db, tenant_id)
    project_ids = [p.id for p in projects]
    statistics = await _compute_statistics(db, tenant_id, project_ids)
    plan_usage = await _compute_plan_usage(db, tenant_id, current_user, total_projects=len(projects))

    return DashboardSummaryResponse(
        projects=projects,
        statistics=statistics,
        plan_usage=plan_usage,
    )


async def list_audit_logs(db: AsyncSession, tenant_id: uuid.UUID, limit: int = 20) -> AuditLogListResponse:
    """List audit log entries for the activity feed.

    Reuses `audit_service.query_logs()`. Joins User for email display.
    """
    limit = max(1, min(limit, 50))
    logs = await query_audit_logs(db, tenant_id=tenant_id, limit=limit)

    if not logs:
        return AuditLogListResponse(items=[], total=0)

    # Fetch user emails in one query
    user_ids = {log.user_id for log in logs if log.user_id}
    emails: dict[uuid.UUID, str] = {}
    if user_ids:
        email_stmt = select(User.id, User.email).where(User.id.in_(user_ids))
        for uid, email in (await db.execute(email_stmt)).all():
            emails[uid] = email

    items = [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=str(log.resource_id) if log.resource_id else None,
            details=log.details,
            created_at=log.created_at,
            user_email=emails.get(log.user_id) if log.user_id else None,
        )
        for log in logs
    ]
    return AuditLogListResponse(items=items, total=len(items))
