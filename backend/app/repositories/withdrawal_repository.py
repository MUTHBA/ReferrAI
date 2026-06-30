# -----------------------------------------------------------------------------
# backend/app/repositories/withdrawal_repository.py
#
# Data access for the withdrawals table. list_by_partner() backs the partner's
# own withdrawal history; list_by_status() backs the admin review queue
# (passing status=None returns all). get_by_id() is used by the admin review
# PATCH endpoint before approving or rejecting.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Withdrawal


class WithdrawalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, withdrawal: Withdrawal) -> Withdrawal:
        self.session.add(withdrawal)
        await self.session.flush()
        return withdrawal

    async def get_by_id(self, withdrawal_id: uuid.UUID) -> Optional[Withdrawal]:
        result = await self.session.execute(
            select(Withdrawal).where(Withdrawal.id == withdrawal_id)
        )
        return result.scalar_one_or_none()

    async def list_by_partner(self, partner_id: uuid.UUID) -> list[Withdrawal]:
        result = await self.session.execute(
            select(Withdrawal)
            .where(Withdrawal.partner_id == partner_id)
            .order_by(Withdrawal.requested_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_status(self, status: Optional[str] = None) -> list[Withdrawal]:
        query = select(Withdrawal).order_by(Withdrawal.requested_at.desc())
        if status:
            query = query.where(Withdrawal.status == status)
        result = await self.session.execute(query)
        return list(result.scalars().all())
