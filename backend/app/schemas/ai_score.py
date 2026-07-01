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
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AIScoreResponse(BaseModel):
    """Most recent AI score row for a given entity and score type."""

    model_config = ConfigDict(from_attributes=True)

    entity_id: uuid.UUID
    score_type: str
    score: float
    explanation: Optional[str] = None
    contributing_factors: Optional[dict] = None
    calculated_at: datetime
