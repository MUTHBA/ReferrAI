# -----------------------------------------------------------------------------
# backend/app/repositories/partner_repository.py
#
# Data access for the partners and partner_tiers tables. create() and
# get_by_user_id() were added during AUTH-001 for registration. get_by_id()
# and get_tier_by_id() are added here (COM-001) so CommissionService can
# resolve a partner's current tier without a separate repository file — both
# models live in models/partner.py and are logically the same domain.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner, PartnerTier


class PartnerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, partner: Partner) -> Partner:
        self.session.add(partner)
        await self.session.flush()
        return partner

    async def get_by_id(self, partner_id: uuid.UUID) -> Optional[Partner]:
        result = await self.session.execute(
            select(Partner).where(Partner.id == partner_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: uuid.UUID) -> Optional[Partner]:
        result = await self.session.execute(
            select(Partner).where(Partner.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_tier_by_id(self, tier_id: uuid.UUID) -> Optional[PartnerTier]:
        result = await self.session.execute(
            select(PartnerTier).where(PartnerTier.id == tier_id)
        )
        return result.scalar_one_or_none()
