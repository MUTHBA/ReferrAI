# -----------------------------------------------------------------------------
# backend/app/repositories/referral_conversion_repository.py
#
# Append-only data access for the referral_conversions table. create() flushes
# but does not commit so ReferralConversionService can compose the conversion
# insert, commission calculation, and partner counter update into a single
# atomic transaction before calling session.commit() once.
# -----------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralConversion


class ReferralConversionRepository:
    """Data access for referral_conversions — insert only, no updates."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, conversion: ReferralConversion) -> ReferralConversion:
        """Persist a new conversion row; flush within the caller's transaction."""
        self.session.add(conversion)
        await self.session.flush()
        return conversion
