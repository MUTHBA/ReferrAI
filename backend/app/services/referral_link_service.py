# -----------------------------------------------------------------------------
# backend/app/services/referral_link_service.py
#
# Business logic for referral link creation. Slug generation uses
# secrets.token_urlsafe for URL-safe randomness and retries up to 10 times to
# guarantee uniqueness. QR codes are generated inline as base64 PNGs so the
# front-end can render them without a second request. All writes commit here.
# -----------------------------------------------------------------------------

import base64
import io
import secrets
import uuid

import qrcode
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralLink
from app.repositories.partner_repository import PartnerRepository
from app.repositories.referral_link_repository import ReferralLinkRepository


class PartnerProfileNotFoundError(Exception):
    def __init__(self, user_id: uuid.UUID) -> None:
        super().__init__(f"No partner profile found for user {user_id}")
        self.user_id = user_id


def _generate_qr_base64(url: str) -> str:
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


class ReferralLinkService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ReferralLinkRepository(session)

    async def _unique_slug(self) -> str:
        for _ in range(10):
            slug = secrets.token_urlsafe(8)
            if await self.repo.get_by_slug(slug) is None:
                return slug
        raise RuntimeError("Could not generate a unique referral slug after 10 attempts")

    async def create(
        self, user_id: uuid.UUID, destination_url: str, base_url: str
    ) -> ReferralLink:
        partner = await PartnerRepository(self.session).get_by_user_id(user_id)
        if partner is None:
            raise PartnerProfileNotFoundError(user_id)

        slug = await self._unique_slug()
        referral_url = f"{base_url}r/{slug}"
        qr_data = _generate_qr_base64(referral_url)

        link = ReferralLink(
            id=uuid.uuid4(),
            partner_id=partner.id,
            slug=slug,
            destination_url=destination_url,
            qr_code_data=qr_data,
            is_active=True,
        )
        await self.repo.create(link)
        await self.session.commit()
        return link
