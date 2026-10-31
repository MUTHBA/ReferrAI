# -----------------------------------------------------------------------------
# backend/app/schemas/ai_score.py
#
# Pydantic response schema for the GET /ai-scores/{entity_id} endpoint
# (AI-XAI-003). Returns the most recent ai_scores row for a given entity and
# score type. Used by the frontend to display explanations alongside score
# badges on admin and partner dashboard pages.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AIScoreResponse(BaseModel):
    """Most recent AI score row for a given entity and score type."""

    model_config = ConfigDict(from_attributes=True)

    entity_id: uuid.UUID
    score_type: str
    # None when the model was unavailable or failed (graceful degradation).
    score: Optional[float] = None
    status: str = "ok"
    model_version: Optional[str] = None
    explanation: Optional[str] = None
    contributing_factors: Optional[dict] = None
    calculated_at: datetime


class PartnerScoreRow(BaseModel):
    """One real partner with their latest score of a given type (churn/ranking pages)."""

    partner_id: uuid.UUID
    name: str
    business_name: Optional[str] = None
    email: str
    status: str
    tier_name: Optional[str] = None
    joined_at: datetime
    total_conversions: int
    total_revenue: Decimal
    last_conversion_at: Optional[datetime] = None
    score: Optional[float] = None
    score_status: Optional[str] = None  # None = never scored
    explanation: Optional[str] = None
    contributing_factors: Optional[dict] = None
    calculated_at: Optional[datetime] = None
