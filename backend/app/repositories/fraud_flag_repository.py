# -----------------------------------------------------------------------------
# backend/app/repositories/fraud_flag_repository.py
#
# Data access for fraud_flags. has_active_flag() uses EXISTS, so a partner
# with several flags pending review (one is raised per scoring event) is
# handled correctly. get_with_details() / list_with_details() join the
# partner and the AI score that raised the flag for the admin review queue.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import Row, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_score import AIScore
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner


class FraudFlagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, flag: FraudFlag) -> FraudFlag:
        self.session.add(flag)
        await self.session.flush()
        return flag

    async def has_active_flag(self, partner_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(
                exists().where(
                    FraudFlag.partner_id == partner_id,
                    FraudFlag.status == "pending_review",
                )
            )
        )
        return bool(result.scalar())

    async def has_open_flag_since(self, partner_id: uuid.UUID, since: datetime) -> bool:
        """True if a pending flag was already raised for this partner since `since`
        (used to avoid raising one flag per click during a burst)."""
        result = await self.session.execute(
            select(
                exists().where(
                    FraudFlag.partner_id == partner_id,
                    FraudFlag.status == "pending_review",
                    FraudFlag.created_at >= since,
                )
            )
        )
        return bool(result.scalar())

    def _details_stmt(self):
        return (
            select(FraudFlag, Partner, AIScore)
            .join(Partner, FraudFlag.partner_id == Partner.id)
            .join(AIScore, FraudFlag.ai_score_id == AIScore.id)
            .where(Partner.is_synthetic == False)  # noqa: E712
        )

    async def list_with_details(self, status: Optional[str] = None, limit: Optional[int] = None) -> Sequence[Row]:
        """Return (FraudFlag, Partner, AIScore) rows, newest first."""
        stmt = self._details_stmt().order_by(FraudFlag.created_at.desc())
        if status:
            stmt = stmt.where(FraudFlag.status == status)
        if limit:
            stmt = stmt.limit(limit)
        return (await self.session.execute(stmt)).all()

    async def get_with_details(self, flag_id: uuid.UUID) -> Optional[Row]:
        stmt = self._details_stmt().where(FraudFlag.id == flag_id)
        return (await self.session.execute(stmt)).first()

    async def get_by_id(self, flag_id: uuid.UUID, for_update: bool = False) -> Optional[FraudFlag]:
        stmt = select(FraudFlag).where(FraudFlag.id == flag_id)
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()
