# -----------------------------------------------------------------------------
# backend/app/services/referral_click_service.py
#
# Orchestrates click tracking for the public redirect endpoint. The redirect
# must always succeed even if the DB write fails — the try/except with rollback
# ensures the session is clean before returning regardless of outcome. This
# resilience contract is required by ARCHITECTURE.md; never move it to the route.
# -----------------------------------------------------------------------------

import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralClick
from app.repositories.referral_click_repository import ReferralClickRepository
from app.repositories.referral_link_repository import ReferralLinkRepository

logger = logging.getLogger(__name__)


class ReferralClickService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def track(
        self,
        slug: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
        utm_source: Optional[str],
    ) -> tuple[Optional[str], Optional[uuid.UUID]]:
        """Return (destination_url, click_id) if the slug is active, (None, None) otherwise.

        The click insert is best-effort: if it fails the exception is logged,
        the session is rolled back, and (destination_url, None) is returned so
        the visitor's redirect is never blocked. Callers that schedule fraud
        scoring as a background task must guard on click_id being non-None.
        """
        link = await ReferralLinkRepository(self.session).get_by_slug(slug)
        if link is None or not link.is_active:
            return None, None

        click_id: Optional[uuid.UUID] = None
        try:
            click = ReferralClick(
                id=uuid.uuid4(),
                referral_link_id=link.id,
                referral_code_id=None,
                partner_id=link.partner_id,
                ip_address=ip_address,
                device_info={"user_agent": user_agent} if user_agent else None,
                source=utm_source,
            )
            await ReferralClickRepository(self.session).create(click)
            await self.session.commit()
            click_id = click.id
        except Exception:
            logger.exception(
                "Failed to record referral click for slug %r — redirecting anyway", slug
            )
            await self.session.rollback()

        return link.destination_url, click_id
