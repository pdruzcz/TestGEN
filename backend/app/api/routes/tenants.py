"""Tenant management API routes."""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.models.tenant import PlanType
from app.models.user import User
from app.schemas.users import ChangePlanRequest, ChangePlanResponse
from app.services.user.user_service import change_plan

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.put("/{tenant_id}/plan", response_model=ChangePlanResponse)
async def admin_change_plan(
    tenant_id: uuid.UUID,
    body: ChangePlanRequest,
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Admin changes a tenant's subscription plan."""
    plan = PlanType(body.plan.value)
    tenant = await change_plan(
        db,
        admin=current_user,
        tenant_id=tenant_id,
        new_plan=plan,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return {"message": "Plan został zaktualizowany", "tenant_id": str(tenant.id), "plan": tenant.plan.value}
