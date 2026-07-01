# -----------------------------------------------------------------------------
# backend/app/services/attribution_service.py
#
# Resolves which ReferralClick to credit for a conversion. The attribution
# model (first_click or last_click) and the window length (days) are read
# from the settings table at call time so they can be changed without a
# redeploy. Isolating this here keeps ReferralConversionService focused on
# persistence and free of attribution branching logic.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralClick
from app.repositories.referral_click_repository import ReferralClickRepository
from app.services.setting_service import SettingService


class AttributionService:
    """Resolves the click that should be credited for a given conversion event."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._click_repo = ReferralClickRepository(session)
        self._settings = SettingService(session)

    async def attribute_conversion(
        self,
        partner_id: uuid.UUID,
        referral_code_id: Optional[uuid.UUID] = None,
        click_id: Optional[uuid.UUID] = None,
    ) -> Optional[ReferralClick]:
        """Return the click that should be credited for this conversion, or None.

        Priority: if a specific click_id is supplied it is verified and returned
        (or None if it fails validation). Otherwise clicks are resolved from the
        referral_code within the attribution window using the configured model.
        """
        attribution_model: str = await self._settings.get(
            "referral.attribution_model", "last_click"
        )
        window_days: int = int(
            await self._settings.get("referral.attribution_window_days", 30)
        )
        window_start: datetime = datetime.now(timezone.utc) - timedelta(days=window_days)

        if click_id is not None:
            return await self._click_repo.get_click_in_window(
                click_id=click_id,
                partner_id=partner_id,
                window_start=window_start,
            )

        if referral_code_id is not None:
            if attribution_model == "first_click":
                return await self._click_repo.get_first_click_in_window(
                    partner_id=partner_id,
                    referral_code_id=referral_code_id,
                    window_start=window_start,
                )
            # Default to last_click for any unrecognised value as well
            return await self._click_repo.get_last_click_in_window(
                partner_id=partner_id,
                referral_code_id=referral_code_id,
                window_start=window_start,
            )

        return None
