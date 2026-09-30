"""Persistence helpers for reconstructed user flows (Epic 3, Story 3.7).

Tenant isolation is enforced by Postgres RLS; queries additionally scope by
``project_id`` for belt-and-suspenders safety.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user_flow import FlowStatus, UserFlow


class UserFlowRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_project(
        self, project_id: uuid.UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[UserFlow], int]:
        base_stmt = select(UserFlow).where(UserFlow.project_id == project_id)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = (await self._db.execute(count_stmt)).scalar() or 0

        stmt = (
            base_stmt.options(selectinload(UserFlow.flow_steps))
            .order_by(UserFlow.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_by_id(self, project_id: uuid.UUID, flow_id: uuid.UUID) -> UserFlow | None:
        stmt = (
            select(UserFlow)
            .options(selectinload(UserFlow.flow_steps))
            .where(UserFlow.id == flow_id, UserFlow.project_id == project_id)
        )
        return (await self._db.execute(stmt)).scalar_one_or_none()

    async def update_status(
        self, project_id: uuid.UUID, flow_id: uuid.UUID, status: FlowStatus
    ) -> UserFlow | None:
        flow = await self.get_by_id(project_id, flow_id)
        if flow is None:
            return None
        flow.status = status
        await self._db.flush()
        return flow
