# -----------------------------------------------------------------------------
# backend/app/api/v1/ai_scores.py
#
# Read-only AI score lookup endpoint (AI-XAI-003). Returns the most recent
# ai_scores row for any entity (conversion, partner, click) by entity_id and
# score_type. Accessible to any authenticated user (admin or partner) — score
# data is display-only and carries no privileged information beyond what is
# already visible on the respective dashboards.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.ai_score import AIScore
from app.models.user import User
from app.schemas.ai_score import AIScoreResponse

router = APIRouter(prefix="/ai-scores", tags=["ai-scores"])


@router.get(
    "/{entity_id}",
    response_model=AIScoreResponse,
    summary="Get the latest AI score for an entity",
)
async def get_latest_score(
    entity_id: uuid.UUID,
    score_type: str = Query(..., description="Score type: quality, fraud_risk, churn_risk"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AIScoreResponse:
    """Return the most recent non-synthetic ai_scores row for the given entity.

    Args:
        entity_id:  UUID of the scored entity (conversion_id for quality scores;
                    partner_id for churn_risk and partner-level fraud_risk scores;
                    click_id for click-level fraud_risk scores).
        score_type: One of 'quality', 'fraud_risk', 'churn_risk', 'ranking',
                    'partner_potential'.

    Returns:
        The latest AIScoreResponse row.

    Raises:
        404: If no score has been computed yet for this entity / score_type pair.
    """
    result = await db.execute(
        select(AIScore)
        .where(AIScore.entity_id == entity_id)
        .where(AIScore.score_type == score_type)
        .where(AIScore.is_synthetic == False)  # noqa: E712
        .order_by(AIScore.calculated_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {score_type} score found for entity {entity_id}",
        )

    return AIScoreResponse(
        entity_id=row.entity_id,
        score_type=row.score_type,
        score=float(row.score),
        explanation=row.explanation,
        contributing_factors=row.contributing_factors,
        calculated_at=row.calculated_at,
    )
