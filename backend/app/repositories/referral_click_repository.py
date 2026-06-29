# -----------------------------------------------------------------------------
# backend/app/repositories/referral_click_repository.py
#
# Append-only data access for the referral_clicks table. Only create() is
# exposed — clicks are never updated or deleted. The caller (ReferralClickService)
# wraps this in a try/except so a DB failure here never blocks the redirect.
# -----------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralClick


class ReferralClickRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, click: ReferralClick) -> ReferralClick:
        self.session.add(click)
        await self.session.flush()
        return click
