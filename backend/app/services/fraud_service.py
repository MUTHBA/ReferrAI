# -----------------------------------------------------------------------------
# backend/app/services/fraud_service.py
#
# Business logic for the fraud flag review queue (AI-FRD-005).
# list_flags() returns a flat projection joining FraudFlag + Partner + AIScore.
# review_flag() updates status, stamps reviewer/timestamp, writes an audit row,
# and commits — same pattern as WalletService.review_withdrawal().
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.fraud_flag_repository import FraudFlagRepository
from app.schemas.fraud import FraudFlagResponse
from app.services.audit_log_service import AuditLogService


class FraudFlagNotFoundError(Exception):
    def __init__(self, flag_id: uuid.UUID) -> None:
        super().__init__(f"FraudFlag {flag_id} not found")


class FraudFlagAlreadyReviewedError(Exception):
    def __init__(self, flag_id: uuid.UUID) -> None:
        super().__init__(f"FraudFlag {flag_id} has already been reviewed")


class FraudFlagService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FraudFlagRepository(session)

    async def list_flags(self, status: Optional[str] = None) -> List[FraudFlagResponse]:
        rows = await self.repo.list_with_details(status)
        return [
            FraudFlagResponse(
                id=flag.id,
                partner_id=flag.partner_id,
                partner_name=partner.name,
                ai_score_id=flag.ai_score_id,
                score=float(score.score),
                explanation=score.explanation,
                contributing_factors=score.contributing_factors,
                status=flag.status,
                reviewed_by=flag.reviewed_by,
                reviewed_at=flag.reviewed_at,
                created_at=flag.created_at,
            )
            for flag, partner, score in rows
        ]

    async def review_flag(
        self,
        flag_id: uuid.UUID,
        action: str,
        reviewer_id: uuid.UUID,
    ) -> FraudFlagResponse:
        flag = await self.repo.get_by_id(flag_id)
        if flag is None:
            raise FraudFlagNotFoundError(flag_id)
        if flag.status != "pending_review":
            raise FraudFlagAlreadyReviewedError(flag_id)

        old_status = flag.status
        flag.status = action
        flag.reviewed_by = reviewer_id
        flag.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()

        await AuditLogService(self.session).log(
            user_id=reviewer_id,
            action=f"fraud_flag.{action}",
            entity_type="fraud_flag",
            entity_id=flag.id,
            old_value=old_status,
            new_value=action,
        )
        await self.session.commit()

        rows = await self.repo.list_with_details(None)
        for f, partner, score in rows:
            if f.id == flag_id:
                return FraudFlagResponse(
                    id=f.id,
                    partner_id=f.partner_id,
                    partner_name=partner.name,
                    ai_score_id=f.ai_score_id,
                    score=float(score.score),
                    explanation=score.explanation,
                    contributing_factors=score.contributing_factors,
                    status=f.status,
                    reviewed_by=f.reviewed_by,
                    reviewed_at=f.reviewed_at,
                    created_at=f.created_at,
                )

        # Fallback: return a minimal response if the join query can't find it after commit
        return FraudFlagResponse(
            id=flag.id,
            partner_id=flag.partner_id,
            partner_name="",
            ai_score_id=flag.ai_score_id,
            score=0.0,
            explanation=None,
            contributing_factors=None,
            status=flag.status,
            reviewed_by=flag.reviewed_by,
            reviewed_at=flag.reviewed_at,
            created_at=flag.created_at,
        )
