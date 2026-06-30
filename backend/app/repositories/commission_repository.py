# -----------------------------------------------------------------------------
# backend/app/repositories/commission_repository.py
#
# Data access for the commissions table. create() flushes but does not commit
# so CommissionService can be composed with WalletService.credit() in one
# atomic transaction (wired together in COM-003). get_by_conversion_id() lets
# the service guard against double-calculation before inserting.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission import Commission


class CommissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, commission: Commission) -> Commission:
        self.session.add(commission)
        await self.session.flush()
        return commission

    async def get_by_conversion_id(self, conversion_id: uuid.UUID) -> Optional[Commission]:
        result = await self.session.execute(
            select(Commission).where(Commission.conversion_id == conversion_id)
        )
        return result.scalar_one_or_none()
