# -----------------------------------------------------------------------------
# backend/app/schemas/fraud.py
#
# Pydantic request/response shapes for the fraud flag review endpoints
# (AI-FRD-005). FraudFlagResponse is a flat projection that joins FraudFlag
# with Partner (name) and AIScore (score, explanation, contributing_factors)
# so the frontend gets everything it needs in a single response — no follow-up
# requests to /ai-scores or /partners required.
# FraudFlagReviewRequest accepts only "confirmed" or "dismissed" (the two valid
# terminal statuses per the FraudFlag status CHECK constraint).
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


class FraudFlagResponse(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    partner_name: str
    ai_score_id: uuid.UUID
    score: float
    explanation: Optional[str] = None
    contributing_factors: Optional[Dict[str, Any]] = None
    status: str
    reviewed_by: Optional[uuid.UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class FraudFlagReviewRequest(BaseModel):
    status: Literal["confirmed", "dismissed"]
