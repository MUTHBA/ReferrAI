# -----------------------------------------------------------------------------
# backend/app/services/referral_code_service.py
#
# Business logic for referral code generation. Codes are 8-character strings
# drawn from uppercase letters + digits using secrets.choice (cryptographically
# random). Uniqueness is checked against the DB before insert with up to 10
# retries — the collision probability is negligible in practice (~1/36^8).
# -----------------------------------------------------------------------------

import secrets
import string
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralCode
from app.repositories.partner_repository import PartnerRepository
from app.repositories.referral_code_repository import ReferralCodeRepository
from app.services.referral_link_service import PartnerProfileNotFoundError

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


class ReferralCodeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ReferralCodeRepository(session)

    async def list_for_partner(self, user_id: uuid.UUID) -> list[ReferralCode]:
        """Return all codes owned by the partner associated with this user."""
        partner = await PartnerRepository(self.session).get_by_user_id(user_id)
        if partner is None:
            return []
        return await self.repo.list_by_partner(partner.id)

    async def _unique_code(self) -> str:
        for _ in range(10):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            if await self.repo.get_by_code(code) is None:
                return code
        raise RuntimeError("Could not generate a unique referral code after 10 attempts")

    async def create(self, user_id: uuid.UUID) -> ReferralCode:
        partner = await PartnerRepository(self.session).get_by_user_id(user_id)
        if partner is None:
            raise PartnerProfileNotFoundError(user_id)

        code_str = await self._unique_code()
        code = ReferralCode(
            id=uuid.uuid4(),
            partner_id=partner.id,
            code=code_str,
            is_active=True,
        )
        await self.repo.create(code)
        await self.session.commit()
        return code
