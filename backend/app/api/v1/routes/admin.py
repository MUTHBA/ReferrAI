# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/admin.py
#
# Admin-only AI operations: synthetic training data generation, batch churn
# and ranking scoring, and partner discovery (score candidates, list them,
# change their status), and model training (start a background training run,
# poll its status). Each action writes an audit_logs row. Batch scoring runs
# every partner in its own DB session so one failure cannot abort it.
# -----------------------------------------------------------------------------

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import client_ip, require_admin
from app.models.user import User
from app.schemas.discovery import (
    DiscoveredPartnerResponse,
    DiscoveryCandidatesRequest,
    DiscoveryStatusUpdateRequest,
)
from app.schemas.synthetic_data import (
    ChurnScoringResponse,
    RankingScoringResponse,
    SyntheticDataRequest,
    SyntheticDataResponse,
    TrainingStatusResponse,
    TrainModelsRequest,
)
from app.services import ai_service, model_training_service
from app.services.audit_log_service import AuditLogService
from app.services.discovery_service import CandidateNotFoundError, DiscoveryService
from app.services.synthetic_data_service import generate_and_insert

router = APIRouter(prefix="/admin", tags=["admin"])


async def _audit(db: AsyncSession, user: User, action: str, new_value: dict, request: Request) -> None:
    await AuditLogService(db).log(
        user_id=user.id,
        action=action,
        entity_type="ai",
        entity_id=None,
        new_value=new_value,
        ip_address=client_ip(request),
    )
    await db.commit()


@router.post(
    "/synthetic-data",
    response_model=SyntheticDataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate synthetic ML training data",
)
async def generate_synthetic_data(
    payload: SyntheticDataRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> SyntheticDataResponse:
    result = await generate_and_insert(db, payload)
    await _audit(db, current_user, "ai.synthetic_data_generated", result.model_dump(), request)
    return result


@router.post("/run-churn-scoring", response_model=ChurnScoringResponse, summary="Score all active partners for churn risk")
async def run_churn_scoring(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ChurnScoringResponse:
    count = await ai_service.score_all_active_partners(ai_service.score_churn)
    await _audit(db, current_user, "ai.churn_scoring_run", {"partners_scored": count}, request)
    return ChurnScoringResponse(partners_scored=count)


@router.post("/run-ranking", response_model=RankingScoringResponse, summary="Compute ranking scores for all active partners")
async def run_ranking(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> RankingScoringResponse:
    count = await ai_service.score_all_active_partners(ai_service.score_ranking)
    await _audit(db, current_user, "ai.ranking_run", {"partners_scored": count}, request)
    return RankingScoringResponse(partners_scored=count)


@router.get("/discovery/candidates", response_model=list[DiscoveredPartnerResponse], summary="List discovery candidates")
async def list_discovery_candidates(
    candidate_status: Optional[Literal["new", "reviewed", "invited", "dismissed"]] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[DiscoveredPartnerResponse]:
    rows = await DiscoveryService(db).list_candidates(candidate_status)
    return [DiscoveredPartnerResponse.model_validate(dp) for dp in rows]


@router.post(
    "/discovery/candidates",
    response_model=list[DiscoveredPartnerResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Score and store a batch of discovery candidates (AI-DISC-002)",
)
async def score_discovery_candidates(
    payload: DiscoveryCandidatesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[DiscoveredPartnerResponse]:
    candidates = [c.model_dump() for c in payload.candidates]
    results = await DiscoveryService(db).score_and_insert_candidates(candidates)
    await _audit(db, current_user, "discovery.candidates_scored", {"count": len(results)}, request)
    return [DiscoveredPartnerResponse.model_validate(dp) for dp in results]


@router.patch(
    "/discovery/candidates/{candidate_id}",
    response_model=DiscoveredPartnerResponse,
    summary="Update a discovery candidate's status (AI-DISC-003)",
)
async def update_discovery_candidate_status(
    candidate_id: uuid.UUID,
    payload: DiscoveryStatusUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> DiscoveredPartnerResponse:
    try:
        dp = await DiscoveryService(db).update_status(
            candidate_id, payload.status, current_user.id, client_ip(request)
        )
    except CandidateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discovery candidate not found")
    return DiscoveredPartnerResponse.model_validate(dp)


@router.get("/ai/models", response_model=TrainingStatusResponse, summary="Model status and the latest training run")
async def model_status(_: User = Depends(require_admin)) -> TrainingStatusResponse:
    return TrainingStatusResponse(**model_training_service.status())


@router.post(
    "/ai/train",
    response_model=TrainingStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Train models in the background",
)
async def train_models(
    request: Request,
    payload: TrainModelsRequest = TrainModelsRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> TrainingStatusResponse:
    try:
        state = model_training_service.start(tuple(payload.models), payload.n_partners, payload.seed)
    except model_training_service.TrainingAlreadyRunningError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A training run is already in progress")
    await _audit(db, current_user, "ai.training_started", payload.model_dump(), request)
    return TrainingStatusResponse(**state)
