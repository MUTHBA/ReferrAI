# -----------------------------------------------------------------------------
# backend/app/schemas/discovery.py
#
# Pydantic request/response shapes for the partner discovery endpoints
# (AI-DISC-002, AI-DISC-003).
# CandidateInput: one candidate record submitted for scoring.
# DiscoveryCandidatesRequest: the POST body — an array of candidates.
# DiscoveredPartnerResponse: single discovered-partner row returned after
#   scoring; potential_score and score_factors are always populated (may be
#   0.0 / default factors when the embedding model is unavailable).
# DiscoveryStatusUpdateRequest: PATCH body for invite/dismiss actions.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel


class CandidateInput(BaseModel):
    business_name: str
    category: str
    description: str = ""
    city: str = ""
    country: str = ""


class DiscoveryCandidatesRequest(BaseModel):
    candidates: list[CandidateInput]


class DiscoveredPartnerResponse(BaseModel):
    id: uuid.UUID
    candidate_name: str
    business_category: Optional[str] = None
    geographic_data: Optional[dict] = None
    raw_data: Optional[dict] = None
    potential_score: Optional[float] = None
    score_factors: Optional[dict] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DiscoveryStatusUpdateRequest(BaseModel):
    status: Literal["invited", "dismissed", "reviewed"]
