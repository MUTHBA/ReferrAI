# -----------------------------------------------------------------------------
# backend/app/api/v1/admin.py
#
# Admin-only API endpoints that don't belong to a specific domain router.
# Exposes three endpoints:
#   POST /api/v1/admin/synthetic-data       — triggers synthetic ML training
#       data generation (AI-DATA-001/002). Intentionally slow for large
#       requests; callers should not set aggressive timeouts.
#   POST /api/v1/admin/run-churn-scoring    — scores every active non-synthetic
#       partner for churn risk (AI-CHURN-003). Calls score_churn() per partner
#       sequentially; each call commits independently and swallows exceptions
#       so a single model failure does not abort the batch.
#   POST /api/v1/admin/run-ranking          — computes composite ranking scores
#       for every active non-synthetic partner (AI-RANK-001). Same batch
#       pattern as run-churn-scoring.
# -----------------------------------------------------------------------------

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.partner import Partner
from app.models.user import User
from app.schemas.synthetic_data import (
    ChurnScoringResponse,
    RankingScoringResponse,
    SyntheticDataRequest,
    SyntheticDataResponse,
)
from app.services import ai_service
from app.services.synthetic_data_service import generate_and_insert

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/synthetic-data",
    response_model=SyntheticDataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate synthetic ML training data",
)
async def generate_synthetic_data(
    payload: SyntheticDataRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> SyntheticDataResponse:
    return await generate_and_insert(db, payload)


@router.post(
    "/run-churn-scoring",
    response_model=ChurnScoringResponse,
    summary="Score all active partners for churn risk",
)
async def run_churn_scoring(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> ChurnScoringResponse:
    """Compute and persist a churn risk score for every active non-synthetic partner.

    Iterates all partners with status='active' and is_synthetic=False, calling
    score_churn() for each. Each call commits independently and swallows its own
    exceptions, so a single model failure or missing feature does not abort the
    batch. The final count reflects the number of partners attempted, not
    necessarily the number of successfully stored scores.
    """
    partners_result = await db.execute(
        select(Partner)
        .where(Partner.status == "active")
        .where(Partner.is_synthetic == False)  # noqa: E712
    )
    partners = partners_result.scalars().all()

    for partner in partners:
        await ai_service.score_churn(db, partner.id)

    return ChurnScoringResponse(partners_scored=len(partners))


@router.post(
    "/run-ranking",
    response_model=RankingScoringResponse,
    summary="Compute ranking scores for all active partners",
)
async def run_ranking(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> RankingScoringResponse:
    """Compute and persist a composite ranking score for every active non-synthetic partner.

    Iterates all partners with status='active' and is_synthetic=False, calling
    score_ranking() for each. Each call commits independently and swallows its own
    exceptions so a single partner failure does not abort the batch.
    """
    partners_result = await db.execute(
        select(Partner)
        .where(Partner.status == "active")
        .where(Partner.is_synthetic == False)  # noqa: E712
    )
    partners = partners_result.scalars().all()

    for partner in partners:
        await ai_service.score_ranking(db, partner.id)

    return RankingScoringResponse(partners_scored=len(partners))
