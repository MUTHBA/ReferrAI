# -----------------------------------------------------------------------------
# backend/app/services/referral_click_service.py
#
# Records a click on a referral link (REF-004). The visitor is ALWAYS
# redirected if the link exists and is active; recording the click is best
# effort. Clicks are not recorded for partners that are not active (a
# suspended partner cannot keep earning attribution). device_info stores the
# raw user agent plus a parsed device_type (desktop/mobile/tablet/bot) — the
# same feature the fraud and quality models are trained on.
# -----------------------------------------------------------------------------

import logging
import re
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.features import fingerprint_for
from app.models.referral import ReferralClick
from app.repositories.partner_repository import PartnerRepository
from app.repositories.referral_click_repository import ReferralClickRepository
from app.repositories.referral_link_repository import ReferralLinkRepository

logger = logging.getLogger(__name__)

_BOT = re.compile(r"bot|crawl|spider|slurp|curl|wget|python-requests|httpclient|headless", re.I)
_TABLET = re.compile(r"ipad|tablet|kindle|silk|playbook|(android(?!.*mobile))", re.I)
_MOBILE = re.compile(r"mobi|iphone|ipod|android|blackberry|opera mini|iemobile|windows phone", re.I)


def device_type_from_user_agent(user_agent: Optional[str]) -> str:
    if not user_agent:
        return "unknown"
    if _BOT.search(user_agent):
        return "bot"
    if _TABLET.search(user_agent):
        return "tablet"
    if _MOBILE.search(user_agent):
        return "mobile"
    return "desktop"


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
        """Return (destination_url, click_id). destination is None if the slug
        is unknown/inactive; click_id is None if the click was not recorded."""
        link = await ReferralLinkRepository(self.session).get_by_slug(slug)
        if link is None or not link.is_active:
            return None, None

        partner = await PartnerRepository(self.session).get_by_id(link.partner_id)
        if partner is None or partner.status != "active":
            return link.destination_url, None

        click_id: Optional[uuid.UUID] = None
        try:
            click = ReferralClick(
                id=uuid.uuid4(),
                referral_link_id=link.id,
                referral_code_id=None,
                partner_id=link.partner_id,
                ip_address=ip_address,
                device_info={
                    "user_agent": user_agent,
                    "device_type": device_type_from_user_agent(user_agent),
                    # IP + user agent: a user agent alone is shared by millions of visitors.
                    "fingerprint": fingerprint_for(ip_address, user_agent),
                },
                source=utm_source,
                is_synthetic=False,
            )
            await ReferralClickRepository(self.session).create(click)
            await self.session.commit()
            click_id = click.id
        except Exception:
            logger.exception("Failed to record referral click for slug %r — redirecting anyway", slug)
            await self.session.rollback()

        return link.destination_url, click_id
