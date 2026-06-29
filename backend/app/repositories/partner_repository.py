# -----------------------------------------------------------------------------
# backend/app/repositories/partner_repository.py
#
# Data access for the partners table. Currently just create(), used by
# AuthService.register() to bootstrap a Partner row alongside the User when
# registering with role="partner". Add lookup methods here as later
# partner-management tasks need them.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner


class PartnerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, partner: Partner) -> Partner:
        self.session.add(partner)
        await self.session.flush()
        return partner

    async def get_by_user_id(self, user_id: uuid.UUID) -> Optional[Partner]:
        result = await self.session.execute(
            select(Partner).where(Partner.user_id == user_id)
        )
        return result.scalar_one_or_none()
