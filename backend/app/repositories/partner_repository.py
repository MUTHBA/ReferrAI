from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner


class PartnerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, partner: Partner) -> Partner:
        self.session.add(partner)
        await self.session.flush()
        return partner
