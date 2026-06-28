# -----------------------------------------------------------------------------
# backend/app/repositories/partner_repository.py
#
# Data access for the partners table. Currently just create(), used by
# AuthService.register() to bootstrap a Partner row alongside the User when
# registering with role="partner". Add lookup methods here as later
# partner-management tasks need them.
# -----------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner


class PartnerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, partner: Partner) -> Partner:
        self.session.add(partner)
        await self.session.flush()
        return partner
