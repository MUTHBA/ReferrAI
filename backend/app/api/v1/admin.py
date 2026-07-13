# -----------------------------------------------------------------------------
# backend/app/api/v1/admin.py
#
# Admin-only API endpoints that don't belong to a specific domain router.
# Exposes five endpoints:
#   POST /api/v1/admin/synthetic-data            — triggers synthetic ML
#       training data generation (AI-DATA-001/002).
#   POST /api/v1/admin/run-churn-scoring         — scores every active
#       non-synthetic partner for churn risk (AI-CHURN-003).
#   POST /api/v1/admin/run-ranking               — computes composite ranking
#       scores for every active non-synthetic partner (AI-RANK-001).
#   POST /api/v1/admin/discovery/candidates      — score JSON array of
#       candidate businesses via PartnerDiscovery, insert DiscoveredPartner
#       records, return ranked results (AI-DISC-002).
#   PATCH /api/v1/admin/discovery/candidates/{id} — update a candidate's
#       status (invited / dismissed / reviewed) (AI-DISC-003).
# -----------------------------------------------------------------------------

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.partner import Partner
from app.models.user import User
from app.schemas.discovery import (
    DiscoveryCandidatesRequest,
    DiscoveredPartnerResponse,
    DiscoveryStatusUpdateRequest,
)
from app.schemas.synthetic_data import (
    ChurnScoringResponse,
    RankingScoringResponse,
    SyntheticDataRequest,
    SyntheticDataResponse,
)
from app.services import ai_service
from app.services.discovery_service import CandidateNotFoundError, DiscoveryService
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


@router.post(
    "/discovery/candidates",
    response_model=list[DiscoveredPartnerResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Score and store a batch of discovery candidates (AI-DISC-002)",
)
async def score_discovery_candidates(
    payload: DiscoveryCandidatesRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DiscoveredPartnerResponse]:
    """Accept a JSON array of candidate businesses, run PartnerDiscovery scoring
    for each, insert DiscoveredPartner rows, and return results ranked by
    potential_score descending. Scoring degrades to 0.0 when the embedding
    model is unavailable — records are still inserted so the admin can review
    manually.
    """
    candidates = [c.model_dump() for c in payload.candidates]
    results = await DiscoveryService(db).score_and_insert_candidates(candidates)
    return [DiscoveredPartnerResponse.model_validate(dp) for dp in results]


@router.patch(
    "/discovery/candidates/{candidate_id}",
    response_model=DiscoveredPartnerResponse,
    summary="Update a discovery candidate's status (AI-DISC-003)",
)
async def update_discovery_candidate_status(
    candidate_id: uuid.UUID,
    payload: DiscoveryStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DiscoveredPartnerResponse:
    """Transition a DiscoveredPartner to invited, dismissed, or reviewed."""
    try:
        dp = await DiscoveryService(db).update_status(candidate_id, payload.status)
    except CandidateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discovery candidate not found",
        )
    return DiscoveredPartnerResponse.model_validate(dp)
