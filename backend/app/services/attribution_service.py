# -----------------------------------------------------------------------------
# backend/app/services/attribution_service.py
#
# Resolves which click is credited for a conversion (REF-005).
#   * If the caller supplies click_id, that click is credited only if it is the
#     partner's, real, unused and inside the attribution window.
#   * Otherwise the configured model decides among the partner's eligible
#     clicks in the window: first_click = oldest, last_click = newest.
#     For code-based conversions, clicks recorded against that code are
#     preferred; if there are none, the partner's link clicks are used.
# Returns the click (or None) together with the model that was applied, so
# the conversion row stores exactly what was used.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralClick
from app.repositories.referral_click_repository import ReferralClickRepository
from app.services.setting_service import SettingService


class AttributionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._click_repo = ReferralClickRepository(session)
        self._settings = SettingService(session)

    async def attribute_conversion(
        self,
        partner_id: uuid.UUID,
        referral_code_id: Optional[uuid.UUID] = None,
        click_id: Optional[uuid.UUID] = None,
    ) -> tuple[Optional[ReferralClick], str]:
        model: str = await self._settings.get("referral.attribution_model")
        window_days = int(await self._settings.get("referral.attribution_window_days"))
        window_start: datetime = datetime.now(timezone.utc) - timedelta(days=window_days)

        if click_id is not None:
            click = await self._click_repo.get_click_in_window(click_id, partner_id, window_start)
            return click, model

        click = None
        if referral_code_id is not None:
            click = await self._click_repo.find_attributable_click(
                partner_id, window_start, model, referral_code_id=referral_code_id
            )
        if click is None:
            click = await self._click_repo.find_attributable_click(partner_id, window_start, model)
        return click, model
