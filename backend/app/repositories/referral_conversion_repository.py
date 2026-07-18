# -----------------------------------------------------------------------------
# backend/app/repositories/referral_conversion_repository.py
#
# Append-only data access for the referral_conversions table. create() flushes
# but does not commit so ReferralConversionService can compose the conversion
# insert, commission calculation, and partner counter update into a single
# atomic transaction before calling session.commit() once.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralConversion


class ReferralConversionRepository:
    """Data access for referral_conversions — insert only, no updates."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_partner_and_reference(
        self, partner_id: uuid.UUID, external_reference: str
    ) -> Optional[ReferralConversion]:
        """Return the existing conversion for this partner + order ID, or None."""
        result = await self.session.execute(
            select(ReferralConversion).where(
                ReferralConversion.partner_id == partner_id,
                ReferralConversion.external_reference == external_reference,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, conversion: ReferralConversion) -> ReferralConversion:
        """Persist a new conversion row; flush within the caller's transaction."""
        self.session.add(conversion)
        await self.session.flush()
        return conversion
