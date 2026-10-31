# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/fraud.py
#
# Fraud flag review queue endpoints (AI-FRD-005).
# GET  /fraud-flags          — list flags; defaults to pending_review when no
#                              ?status= is supplied. Pass ?status=all to see
#                              every flag regardless of status.
# PATCH /fraud-flags/{id}    — admin confirms or dismisses a flag
# Both endpoints require require_admin (RBAC). Review action writes to
# audit_logs via FraudFlagService (same pattern as wallet review). Registered
# in main.py with prefix="/api/v1".
# AI-FRD-005 update: default changed from None→all to "pending_review" so the
# admin review queue surfaces actionable items without an explicit filter.
# -----------------------------------------------------------------------------

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import client_ip, require_admin
from app.models.user import User
from app.schemas.fraud import FraudFlagResponse, FraudFlagReviewRequest
from app.services.fraud_service import (
    FraudFlagAlreadyReviewedError,
    FraudFlagNotFoundError,
    FraudFlagService,
)

router = APIRouter(tags=["fraud"])


@router.get("/fraud-flags", response_model=List[FraudFlagResponse])
async def list_fraud_flags(
    flag_status: str = Query("pending_review", alias="status"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> List[FraudFlagResponse]:
    # "all" is a sentinel that disables the status filter entirely.
    effective_status = None if flag_status == "all" else flag_status
    return await FraudFlagService(db).list_flags(effective_status)


@router.patch("/fraud-flags/{flag_id}", response_model=FraudFlagResponse)
async def review_fraud_flag(
    flag_id: uuid.UUID,
    payload: FraudFlagReviewRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> FraudFlagResponse:
    try:
        return await FraudFlagService(db).review_flag(
            flag_id=flag_id,
            action=payload.status,
            reviewer_id=current_user.id,
            notes=payload.notes,
            ip_address=client_ip(request),
        )
    except FraudFlagNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud flag not found")
    except FraudFlagAlreadyReviewedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fraud flag has already been reviewed",
        )
