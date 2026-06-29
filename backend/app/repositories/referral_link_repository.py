# -----------------------------------------------------------------------------
# backend/app/repositories/referral_link_repository.py
#
# Data access for the referral_links table. get_by_slug is the hot path hit
# on every public redirect (GET /r/{slug}), so it queries on the indexed slug
# column. list_by_partner supports the partner dashboard. No business logic —
# slug uniqueness checking and QR generation live in the service layer.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralLink


class ReferralLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, link: ReferralLink) -> ReferralLink:
        self.session.add(link)
        await self.session.flush()
        return link

    async def get_by_slug(self, slug: str) -> Optional[ReferralLink]:
        result = await self.session.execute(
            select(ReferralLink).where(ReferralLink.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_by_partner(self, partner_id: uuid.UUID) -> list[ReferralLink]:
        result = await self.session.execute(
            select(ReferralLink)
            .where(ReferralLink.partner_id == partner_id)
            .order_by(ReferralLink.created_at.desc())
        )
        return list(result.scalars().all())
