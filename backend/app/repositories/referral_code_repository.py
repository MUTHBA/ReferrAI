# -----------------------------------------------------------------------------
# backend/app/repositories/referral_code_repository.py
#
# Data access for the referral_codes table. get_by_code is used during
# code generation to check for collisions before insert — the service retries
# until it finds a code that returns None here. Flush-not-commit pattern lets
# the service control the transaction boundary.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralCode


class ReferralCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, code: ReferralCode) -> ReferralCode:
        self.session.add(code)
        await self.session.flush()
        return code

    async def get_by_code(self, code: str) -> Optional[ReferralCode]:
        result = await self.session.execute(
            select(ReferralCode).where(ReferralCode.code == code)
        )
        return result.scalar_one_or_none()

    async def list_by_partner(self, partner_id: uuid.UUID) -> list[ReferralCode]:
        result = await self.session.execute(
            select(ReferralCode)
            .where(ReferralCode.partner_id == partner_id)
            .order_by(ReferralCode.created_at.desc())
        )
        return list(result.scalars().all())
