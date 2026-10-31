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
from app.models.partner import Partner
from app.repositories.referral_code_repository import ReferralCodeRepository

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


class ReferralCodeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ReferralCodeRepository(session)

    async def list_for_partner(self, partner_id: uuid.UUID) -> list[ReferralCode]:
        return await self.repo.list_by_partner(partner_id)

    async def _unique_code(self) -> str:
        for _ in range(10):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
            if await self.repo.get_by_code(code) is None:
                return code
        raise RuntimeError("Could not generate a unique referral code after 10 attempts")

    async def create(self, partner: Partner) -> ReferralCode:

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
