# -----------------------------------------------------------------------------
# backend/app/repositories/referral_click_repository.py
#
# Data access for the referral_clicks table. create() is append-only; the
# three window-query methods (get_click_in_window, get_first_click_in_window,
# get_last_click_in_window) are used exclusively by AttributionService to
# resolve which click to credit for a conversion. No attribution logic lives
# here — only parameterised queries ordered by clicked_at.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralClick


class ReferralClickRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, click: ReferralClick) -> ReferralClick:
        """Append a new click row; flush so callers can compose into a transaction."""
        self.session.add(click)
        await self.session.flush()
        return click

    async def get_click_in_window(
        self,
        click_id: uuid.UUID,
        partner_id: uuid.UUID,
        window_start: datetime,
    ) -> Optional[ReferralClick]:
        """Return a specific click only if it belongs to the partner and is within the attribution window."""
        result = await self.session.execute(
            select(ReferralClick).where(
                ReferralClick.id == click_id,
                ReferralClick.partner_id == partner_id,
                ReferralClick.clicked_at >= window_start,
            )
        )
        return result.scalar_one_or_none()

    async def get_first_click_in_window(
        self,
        partner_id: uuid.UUID,
        referral_code_id: uuid.UUID,
        window_start: datetime,
    ) -> Optional[ReferralClick]:
        """Return the oldest click for this code within the attribution window (first-click model)."""
        result = await self.session.execute(
            select(ReferralClick)
            .where(
                ReferralClick.partner_id == partner_id,
                ReferralClick.referral_code_id == referral_code_id,
                ReferralClick.clicked_at >= window_start,
            )
            .order_by(ReferralClick.clicked_at.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_last_click_in_window(
        self,
        partner_id: uuid.UUID,
        referral_code_id: uuid.UUID,
        window_start: datetime,
    ) -> Optional[ReferralClick]:
        """Return the most recent click for this code within the attribution window (last-click model)."""
        result = await self.session.execute(
            select(ReferralClick)
            .where(
                ReferralClick.partner_id == partner_id,
                ReferralClick.referral_code_id == referral_code_id,
                ReferralClick.clicked_at >= window_start,
            )
            .order_by(ReferralClick.clicked_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
