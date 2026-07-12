# -----------------------------------------------------------------------------
# backend/app/repositories/fraud_flag_repository.py
#
# Data access for the fraud_flags table. has_active_flag() is the hot path
# called by WalletService before auto-approving a withdrawal — a single
# pending_review flag blocks auto-approval regardless of amount.
# AI-FRD-005: added list_with_details() (joined query for admin review list)
# and get_by_id() for the PATCH review endpoint.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional, Sequence

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_score import AIScore
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner


class FraudFlagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def has_active_flag(self, partner_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(FraudFlag).where(
                FraudFlag.partner_id == partner_id,
                FraudFlag.status == "pending_review",
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_with_details(
        self, status: Optional[str] = None
    ) -> Sequence[Row]:
        """Return (FraudFlag, Partner, AIScore) rows, newest first."""
        stmt = (
            select(FraudFlag, Partner, AIScore)
            .join(Partner, FraudFlag.partner_id == Partner.id)
            .join(AIScore, FraudFlag.ai_score_id == AIScore.id)
            .order_by(FraudFlag.created_at.desc())
        )
        if status:
            stmt = stmt.where(FraudFlag.status == status)
        result = await self.session.execute(stmt)
        return result.all()

    async def get_by_id(self, flag_id: uuid.UUID) -> Optional[FraudFlag]:
        result = await self.session.execute(
            select(FraudFlag).where(FraudFlag.id == flag_id)
        )
        return result.scalar_one_or_none()
