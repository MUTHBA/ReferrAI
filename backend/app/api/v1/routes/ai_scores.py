# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/ai_scores.py
#
# Read-only AI score lookup (AI-XAI-003): the latest non-synthetic ai_scores
# row for an entity + score type. Ownership rules live in AIScoreService —
# partners only see their own quality/churn/ranking scores; fraud scores are
# admin-only.
# -----------------------------------------------------------------------------

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User
from app.schemas.ai_score import AIScoreResponse, PartnerScoreRow
from app.services.ai_score_service import (
    AIScoreService,
    ScoreAccessDeniedError,
    ScoreNotFoundError,
)

router = APIRouter(prefix="/ai-scores", tags=["ai-scores"])

ScoreType = Literal["quality", "fraud_risk", "churn_risk", "ranking", "partner_potential"]


@router.get(
    "",
    response_model=list[PartnerScoreRow],
    summary="Every real partner with their latest partner-level score (admin)",
)
async def list_partner_scores(
    score_type: Literal["churn_risk", "ranking", "fraud_risk"] = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[PartnerScoreRow]:
    return [PartnerScoreRow(**row) for row in await AIScoreService(db).partner_rows(score_type)]


@router.get("/{entity_id}", response_model=AIScoreResponse, summary="Get the latest AI score for an entity")
async def get_latest_score(
    entity_id: uuid.UUID,
    score_type: ScoreType = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIScoreResponse:
    try:
        row = await AIScoreService(db).get_latest_for_user(current_user, entity_id, score_type)
    except ScoreAccessDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except ScoreNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {score_type} score found for entity {entity_id}",
        )
    return AIScoreResponse.model_validate(row)
