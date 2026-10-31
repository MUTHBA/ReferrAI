# -----------------------------------------------------------------------------
# backend/app/repositories/ai_score_repository.py
#
# Data access for the append-only ai_scores table. "Latest" queries always
# exclude synthetic rows. partner_quality_averages() aggregates the latest
# quality score of every conversion up to the partner that owns it — quality
# is stored per conversion (entity_type='referral'), never per partner.
# -----------------------------------------------------------------------------

import uuid
from typing import Iterable, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_score import AIScore
from app.models.referral import ReferralConversion


class AIScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, score: AIScore) -> AIScore:
        self.session.add(score)
        await self.session.flush()
        return score

    async def get_latest(
        self,
        entity_id: uuid.UUID,
        score_type: str,
        entity_type: Optional[str] = None,
    ) -> Optional[AIScore]:
        stmt = (
            select(AIScore)
            .where(AIScore.entity_id == entity_id)
            .where(AIScore.score_type == score_type)
            .where(AIScore.is_synthetic == False)  # noqa: E712
        )
        if entity_type:
            stmt = stmt.where(AIScore.entity_type == entity_type)
        stmt = stmt.order_by(AIScore.calculated_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def latest_by_entity(
        self, score_type: str, entity_type: str = "partner"
    ) -> dict[uuid.UUID, Optional[float]]:
        """Return {entity_id: latest score} for every entity with a score of this type."""
        ranked = (
            select(
                AIScore.entity_id,
                AIScore.score,
                func.row_number()
                .over(partition_by=AIScore.entity_id, order_by=AIScore.calculated_at.desc())
                .label("rn"),
            )
            .where(AIScore.score_type == score_type)
            .where(AIScore.entity_type == entity_type)
            .where(AIScore.is_synthetic == False)  # noqa: E712
            .subquery()
        )
        rows = await self.session.execute(
            select(ranked.c.entity_id, ranked.c.score).where(ranked.c.rn == 1)
        )
        return {r.entity_id: (float(r.score) if r.score is not None else None) for r in rows}

    async def partner_quality_averages(
        self, partner_ids: Optional[Iterable[uuid.UUID]] = None
    ) -> dict[uuid.UUID, float]:
        """Average of the latest non-null quality score per conversion, grouped by partner."""
        ranked = (
            select(
                AIScore.entity_id.label("conversion_id"),
                AIScore.score,
                func.row_number()
                .over(partition_by=AIScore.entity_id, order_by=AIScore.calculated_at.desc())
                .label("rn"),
            )
            .where(AIScore.score_type == "quality")
            .where(AIScore.entity_type == "referral")
            .where(AIScore.is_synthetic == False)  # noqa: E712
            .subquery()
        )
        stmt = (
            select(ReferralConversion.partner_id, func.avg(ranked.c.score).label("avg_q"))
            .join(
                ranked,
                and_(ranked.c.conversion_id == ReferralConversion.id, ranked.c.rn == 1),
            )
            .where(ranked.c.score.is_not(None))
            .where(ReferralConversion.is_synthetic == False)  # noqa: E712
            .group_by(ReferralConversion.partner_id)
        )
        if partner_ids is not None:
            stmt = stmt.where(ReferralConversion.partner_id.in_(list(partner_ids)))
        rows = await self.session.execute(stmt)
        return {r.partner_id: round(float(r.avg_q), 2) for r in rows}

    async def latest_rows(self, score_type: str, entity_type: str = "partner") -> dict[uuid.UUID, AIScore]:
        """Return {entity_id: latest AIScore row} for every entity with a score of this type."""
        ranked = (
            select(
                AIScore.id,
                func.row_number()
                .over(partition_by=AIScore.entity_id, order_by=AIScore.calculated_at.desc())
                .label("rn"),
            )
            .where(AIScore.score_type == score_type)
            .where(AIScore.entity_type == entity_type)
            .where(AIScore.is_synthetic == False)  # noqa: E712
            .subquery()
        )
        rows = await self.session.execute(
            select(AIScore).join(ranked, ranked.c.id == AIScore.id).where(ranked.c.rn == 1)
        )
        return {row.entity_id: row for row in rows.scalars().all()}
