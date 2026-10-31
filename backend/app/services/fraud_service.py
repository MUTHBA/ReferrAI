# -----------------------------------------------------------------------------
# backend/app/services/fraud_service.py
#
# Admin fraud review queue (AI-FRD-005). Flags are raised by AI scoring with
# status 'pending_review' and are NEVER acted on automatically — an admin
# confirms or dismisses each one here (audited). Confirming a flag does not
# suspend the partner either; suspension is a separate, explicit admin action
# (PATCH /partners/{id}), as is reversing commissions.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Row
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


def _to_response(row: Row) -> FraudFlagResponse:
    flag, partner, score = row
    return FraudFlagResponse(
        id=flag.id,
        partner_id=flag.partner_id,
        partner_name=partner.name,
        ai_score_id=flag.ai_score_id,
        referral_click_id=flag.referral_click_id,
        score=float(score.score) if score.score is not None else None,
        explanation=score.explanation,
        contributing_factors=score.contributing_factors,
        status=flag.status,
        reviewed_by=flag.reviewed_by,
        reviewed_at=flag.reviewed_at,
        created_at=flag.created_at,
    )


class FraudFlagService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FraudFlagRepository(session)

    async def list_flags(self, status: Optional[str] = None, limit: Optional[int] = None) -> List[FraudFlagResponse]:
        return [_to_response(r) for r in await self.repo.list_with_details(status, limit)]

    async def review_flag(
        self,
        flag_id: uuid.UUID,
        action: str,
        reviewer_id: uuid.UUID,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> FraudFlagResponse:
        flag = await self.repo.get_by_id(flag_id, for_update=True)
        if flag is None:
            raise FraudFlagNotFoundError(flag_id)
        if flag.status != "pending_review":
            raise FraudFlagAlreadyReviewedError(flag_id)

        flag.status = action
        flag.reviewed_by = reviewer_id
        flag.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()

        await AuditLogService(self.session).log(
            user_id=reviewer_id,
            action=f"fraud_flag.{action}",
            entity_type="fraud_flag",
            entity_id=flag.id,
            old_value={"status": "pending_review"},
            new_value={"status": action, "partner_id": flag.partner_id, "notes": notes},
            ip_address=ip_address,
        )
        await self.session.commit()

        row = await self.repo.get_with_details(flag_id)
        if row is None:
            raise FraudFlagNotFoundError(flag_id)
        return _to_response(row)
