# -----------------------------------------------------------------------------
# backend/app/repositories/referral_click_repository.py
#
# Data access for the referral_clicks table. create() is append-only;
# get_click_in_window() and find_attributable_click() are used by
# AttributionService to resolve which click to credit for a conversion. Both
# ignore synthetic clicks and clicks already credited to another conversion.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralClick, ReferralConversion


class ReferralClickRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, click: ReferralClick) -> ReferralClick:
        """Append a new click row; flush so callers can compose into a transaction."""
        self.session.add(click)
        await self.session.flush()
        return click

    @staticmethod
    def _unused():
        """Clicks that have not already been credited to a conversion."""
        return ~exists().where(ReferralConversion.click_id == ReferralClick.id)

    async def get_click_in_window(
        self,
        click_id: uuid.UUID,
        partner_id: uuid.UUID,
        window_start: datetime,
    ) -> Optional[ReferralClick]:
        """Return a specific click only if it belongs to the partner, is real
        (non-synthetic), unused, and inside the attribution window."""
        result = await self.session.execute(
            select(ReferralClick).where(
                ReferralClick.id == click_id,
                ReferralClick.partner_id == partner_id,
                ReferralClick.clicked_at >= window_start,
                ReferralClick.is_synthetic == False,  # noqa: E712
                self._unused(),
            )
        )
        return result.scalar_one_or_none()

    async def find_attributable_click(
        self,
        partner_id: uuid.UUID,
        window_start: datetime,
        model: str,
        referral_code_id: Optional[uuid.UUID] = None,
    ) -> Optional[ReferralClick]:
        """Pick the click to credit under first_click (oldest) or last_click (newest).

        Considers only the partner's real, unused clicks inside the window. When
        referral_code_id is given, only clicks recorded against that code count.
        """
        stmt = select(ReferralClick).where(
            ReferralClick.partner_id == partner_id,
            ReferralClick.clicked_at >= window_start,
            ReferralClick.is_synthetic == False,  # noqa: E712
            self._unused(),
        )
        if referral_code_id is not None:
            stmt = stmt.where(ReferralClick.referral_code_id == referral_code_id)
        order = ReferralClick.clicked_at.asc() if model == "first_click" else ReferralClick.clicked_at.desc()
        result = await self.session.execute(stmt.order_by(order, ReferralClick.id).limit(1))
        return result.scalar_one_or_none()
