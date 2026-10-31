# -----------------------------------------------------------------------------
# backend/app/repositories/commission_repository.py
#
# Data access for commissions. list_with_conversion() returns
# (Commission, ReferralConversion, Partner) rows for the partner commission
# history and the admin commission list, excluding synthetic records, plus
# the total row count for pagination.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission import Commission
from app.models.partner import Partner
from app.models.referral import ReferralConversion


class CommissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, commission: Commission) -> Commission:
        self.session.add(commission)
        await self.session.flush()
        return commission

    async def get_by_id(self, commission_id: uuid.UUID, for_update: bool = False) -> Optional[Commission]:
        stmt = select(Commission).where(Commission.id == commission_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_conversion_id(self, conversion_id: uuid.UUID) -> Optional[Commission]:
        result = await self.session.execute(
            select(Commission).where(Commission.conversion_id == conversion_id)
        )
        return result.scalar_one_or_none()

    async def list_with_conversion(
        self,
        partner_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> tuple[Sequence[Row], int]:
        base = (
            select(Commission, ReferralConversion, Partner)
            .join(ReferralConversion, Commission.conversion_id == ReferralConversion.id)
            .join(Partner, Commission.partner_id == Partner.id)
            .where(ReferralConversion.is_synthetic == False)  # noqa: E712
            .where(Partner.is_synthetic == False)  # noqa: E712
        )
        if partner_id is not None:
            base = base.where(Commission.partner_id == partner_id)
        if status:
            base = base.where(Commission.status == status)
        if search:
            like = f"%{search.strip()}%"
            base = base.where(ReferralConversion.external_reference.ilike(like) | Partner.name.ilike(like))

        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            await self.session.execute(
                base.order_by(Commission.calculated_at.desc()).limit(limit).offset(offset)
            )
        ).all()
        return rows, int(total)

    async def sums_by_status(
        self, partner_id: Optional[uuid.UUID] = None, search: Optional[str] = None
    ) -> dict[str, Decimal]:
        stmt = (
            select(Commission.status, func.coalesce(func.sum(Commission.amount), 0))
            .join(ReferralConversion, Commission.conversion_id == ReferralConversion.id)
            .join(Partner, Commission.partner_id == Partner.id)
            .where(ReferralConversion.is_synthetic == False)  # noqa: E712
            .where(Partner.is_synthetic == False)  # noqa: E712
            .group_by(Commission.status)
        )
        if partner_id is not None:
            stmt = stmt.where(Commission.partner_id == partner_id)
        if search:
            like = f"%{search.strip()}%"
            stmt = stmt.where(ReferralConversion.external_reference.ilike(like) | Partner.name.ilike(like))
        return {status: Decimal(str(total)) for status, total in (await self.session.execute(stmt)).all()}
