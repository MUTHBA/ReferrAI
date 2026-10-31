# -----------------------------------------------------------------------------
# backend/app/repositories/withdrawal_repository.py
#
# Data access for withdrawals. get_by_id(for_update=True) locks the row so two
# admins reviewing the same request cannot both act on it. list_with_partner()
# joins the partner so the admin payout queue can show who is being paid.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner
from app.models.wallet import Withdrawal


class WithdrawalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, withdrawal: Withdrawal) -> Withdrawal:
        self.session.add(withdrawal)
        await self.session.flush()
        return withdrawal

    async def get_by_id(
        self, withdrawal_id: uuid.UUID, for_update: bool = False
    ) -> Optional[Withdrawal]:
        stmt = select(Withdrawal).where(Withdrawal.id == withdrawal_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_partner(self, partner_id: uuid.UUID) -> list[Withdrawal]:
        result = await self.session.execute(
            select(Withdrawal)
            .where(Withdrawal.partner_id == partner_id)
            .order_by(Withdrawal.requested_at.desc())
        )
        return list(result.scalars().all())

    async def list_with_partner(
        self, status: Optional[str] = None, partner_id: Optional[uuid.UUID] = None
    ) -> Sequence[Row]:
        """Return (Withdrawal, Partner, wallet balance) rows, newest first, excluding synthetic partners."""
        from app.models.wallet import Wallet

        stmt = (
            select(Withdrawal, Partner, Wallet.balance)
            .join(Partner, Withdrawal.partner_id == Partner.id)
            .outerjoin(Wallet, Wallet.id == Withdrawal.wallet_id)
            .where(Partner.is_synthetic == False)  # noqa: E712
            .order_by(Withdrawal.requested_at.desc())
        )
        if status:
            stmt = stmt.where(Withdrawal.status == status)
        if partner_id is not None:
            stmt = stmt.where(Withdrawal.partner_id == partner_id)
        return (await self.session.execute(stmt)).all()

    async def sum_auto_approved_since(self, partner_id: uuid.UUID, since: datetime) -> Decimal:
        result = await self.session.execute(
            select(func.coalesce(func.sum(Withdrawal.amount), 0))
            .where(Withdrawal.partner_id == partner_id)
            .where(Withdrawal.requires_manual_review == False)  # noqa: E712
            .where(Withdrawal.status.in_(("approved", "paid")))
            .where(Withdrawal.requested_at >= since)
        )
        return Decimal(str(result.scalar_one()))

    async def sum_pending(self, partner_id: uuid.UUID) -> Decimal:
        result = await self.session.execute(
            select(func.coalesce(func.sum(Withdrawal.amount), 0))
            .where(Withdrawal.partner_id == partner_id)
            .where(Withdrawal.status == "pending")
        )
        return Decimal(str(result.scalar_one()))
