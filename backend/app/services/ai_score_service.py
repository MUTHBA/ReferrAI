# -----------------------------------------------------------------------------
# backend/app/services/ai_score_service.py
#
# Read access to AI scores with ownership rules. Admins may read any score.
# Partners may read only quality / churn_risk / ranking scores that belong to
# them — their own partner_id, or a conversion they own. Fraud scores are
# admin-only because their explanations reveal the detection rules.
# -----------------------------------------------------------------------------

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_score import AIScore
from app.models.referral import ReferralConversion
from app.models.user import User
from app.repositories.ai_score_repository import AIScoreRepository
from app.repositories.partner_repository import PartnerRepository

PARTNER_VISIBLE_SCORE_TYPES = {"quality", "churn_risk", "ranking"}


class ScoreNotFoundError(Exception):
    pass


class ScoreAccessDeniedError(Exception):
    pass


class AIScoreService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AIScoreRepository(session)

    async def _partner_owns_entity(self, partner_id: uuid.UUID, entity_id: uuid.UUID) -> bool:
        if entity_id == partner_id:
            return True
        owner = await self.session.execute(
            select(ReferralConversion.partner_id).where(ReferralConversion.id == entity_id)
        )
        return owner.scalar_one_or_none() == partner_id

    async def get_latest_for_user(
        self, user: User, entity_id: uuid.UUID, score_type: str
    ) -> AIScore:
        if user.role != "admin":
            if score_type not in PARTNER_VISIBLE_SCORE_TYPES:
                raise ScoreAccessDeniedError()
            partner = await PartnerRepository(self.session).get_by_user_id(user.id)
            if partner is None or not await self._partner_owns_entity(partner.id, entity_id):
                raise ScoreAccessDeniedError()

        row = await self.repo.get_latest(entity_id, score_type)
        if row is None:
            raise ScoreNotFoundError()
        return row


    async def partner_rows(self, score_type: str) -> list[dict]:
        """Every active/suspended real partner with their latest score of this type."""
        from sqlalchemy import func, select

        from app.models.partner import Partner, PartnerTier
        from app.models.referral import ReferralConversion

        latest = await AIScoreRepository(self.session).latest_rows(score_type)
        last_sale = dict(
            (
                await self.session.execute(
                    select(ReferralConversion.partner_id, func.max(ReferralConversion.converted_at))
                    .where(ReferralConversion.is_synthetic == False)  # noqa: E712
                    .group_by(ReferralConversion.partner_id)
                )
            ).all()
        )
        rows = (
            await self.session.execute(
                select(Partner, PartnerTier.name)
                .outerjoin(PartnerTier, PartnerTier.id == Partner.tier_id)
                .where(Partner.is_synthetic == False)  # noqa: E712
                .order_by(Partner.name)
            )
        ).all()
        out = []
        for partner, tier_name in rows:
            score = latest.get(partner.id)
            out.append(
                {
                    "partner_id": partner.id,
                    "name": partner.name,
                    "business_name": partner.business_name,
                    "email": partner.email,
                    "status": partner.status,
                    "tier_name": tier_name,
                    "joined_at": partner.created_at,
                    "total_conversions": partner.total_referral_count,
                    "total_revenue": partner.total_revenue_contribution,
                    "last_conversion_at": last_sale.get(partner.id),
                    "score": float(score.score) if score is not None and score.score is not None else None,
                    "score_status": score.status if score is not None else None,
                    "explanation": score.explanation if score is not None else None,
                    "contributing_factors": score.contributing_factors if score is not None else None,
                    "calculated_at": score.calculated_at if score is not None else None,
                }
            )
        return out
