# -----------------------------------------------------------------------------
# backend/app/repositories/referral_repository.py
#
# Data access for the referral_conversions table. get_conversion_by_id() is
# used by CommissionService to load conversion_value and partner_id before
# calculating the commission amount. Conversion creation lives in REF-004
# (Vidyuth's task); that endpoint will extend this repository with create().
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralConversion


class ReferralRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_conversion_by_id(self, conversion_id: uuid.UUID) -> Optional[ReferralConversion]:
        result = await self.session.execute(
            select(ReferralConversion).where(ReferralConversion.id == conversion_id)
        )
        return result.scalar_one_or_none()
