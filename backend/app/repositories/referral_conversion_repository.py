# -----------------------------------------------------------------------------
# backend/app/repositories/referral_conversion_repository.py
#
# Data access for referral_conversions (insert-only table). Also provides the
# partner's conversion history joined with each conversion's latest AI
# quality score — quality is stored per conversion (entity_type='referral').
# -----------------------------------------------------------------------------

import uuid
from typing import Optional, Sequence

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_score import AIScore
from app.models.commission import Commission
from app.models.referral import ReferralClick, ReferralConversion


class ReferralConversionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, conversion_id: uuid.UUID) -> Optional[ReferralConversion]:
        result = await self.session.execute(
            select(ReferralConversion).where(ReferralConversion.id == conversion_id)
        )
        return result.scalar_one_or_none()

    async def get_by_partner_and_reference(
        self, partner_id: uuid.UUID, external_reference: str
    ) -> Optional[ReferralConversion]:
        result = await self.session.execute(
            select(ReferralConversion).where(
                ReferralConversion.partner_id == partner_id,
                ReferralConversion.external_reference == external_reference,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, conversion: ReferralConversion) -> ReferralConversion:
        self.session.add(conversion)
        await self.session.flush()
        return conversion

    async def list_for_partner_with_quality(
        self, partner_id: uuid.UUID, limit: int = 200, offset: int = 0
    ) -> Sequence[Row]:
        """(ReferralConversion, quality_score, quality_status, quality_explanation,
        quality_factors, Commission|None, ReferralClick|None), newest first."""

        def latest(column):
            return (
                select(column)
                .where(AIScore.entity_id == ReferralConversion.id)
                .where(AIScore.entity_type == "referral")
                .where(AIScore.score_type == "quality")
                .order_by(AIScore.calculated_at.desc())
                .limit(1)
                .correlate(ReferralConversion)
                .scalar_subquery()
            )

        stmt = (
            select(
                ReferralConversion,
                latest(AIScore.score).label("quality_score"),
                latest(AIScore.status).label("quality_status"),
                latest(AIScore.explanation).label("quality_explanation"),
                latest(AIScore.contributing_factors).label("quality_factors"),
                Commission,
                ReferralClick,
            )
            .outerjoin(Commission, Commission.conversion_id == ReferralConversion.id)
            .outerjoin(ReferralClick, ReferralClick.id == ReferralConversion.click_id)
            .where(ReferralConversion.partner_id == partner_id)
            .where(ReferralConversion.is_synthetic == False)  # noqa: E712
            .order_by(ReferralConversion.converted_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.execute(stmt)).all()

    async def usage_counts(self, partner_id: uuid.UUID) -> dict[str, dict[uuid.UUID, int]]:
        """Real (non-synthetic) clicks and conversions per link and per code."""

        async def grouped(model, column) -> dict[uuid.UUID, int]:
            rows = await self.session.execute(
                select(column, func.count())
                .where(model.partner_id == partner_id)
                .where(model.is_synthetic == False)  # noqa: E712
                .where(column.is_not(None))
                .group_by(column)
            )
            return {k: int(v) for k, v in rows.all()}

        return {
            "link_clicks": await grouped(ReferralClick, ReferralClick.referral_link_id),
            "link_conversions": await grouped(ReferralConversion, ReferralConversion.referral_link_id),
            "code_conversions": await grouped(ReferralConversion, ReferralConversion.referral_code_id),
        }
