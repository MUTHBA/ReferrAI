# -----------------------------------------------------------------------------
# backend/app/repositories/fraud_flag_repository.py
#
# Data access for the fraud_flags table. has_active_flag() is the hot path
# called by WalletService before auto-approving a withdrawal — a single
# pending_review flag blocks auto-approval regardless of amount. Full fraud
# flag CRUD (list, review) belongs to the fraud vertical (AI-FRD-005).
# -----------------------------------------------------------------------------

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fraud_flag import FraudFlag


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
