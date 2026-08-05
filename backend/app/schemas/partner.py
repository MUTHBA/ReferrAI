# -----------------------------------------------------------------------------
# backend/app/schemas/partner.py
#
# Pydantic request/response shapes for the partner and tier endpoints.
# PartnerResponse is shared between admin and partner views — the admin sees
# all partners, the partner sees only their own. PartnerUpdateRequest allows
# different fields per role: admins can change status/tier, partners can
# only update name/contact. TierResponse/TierCreateRequest/TierUpdateRequest
# cover the admin-only tier CRUD (PRT-002).
# Added rank_score: Optional[float] for AI-RANK-002 — populated only in the
# ranked partner list (GET /partners?sort=rank); null for all other fetches.
# AI-CHURN-004: added churn_score: Optional[float] — populated on every partner
# list response (non-synthetic only) using the latest churn_risk ai_score.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TierResponse(BaseModel):
    id: uuid.UUID
    name: str
    rank_order: int
    min_referral_count: int
    min_revenue_contribution: Decimal
    commission_type: str
    commission_value: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class TierCreateRequest(BaseModel):
    name: str
    rank_order: int = Field(ge=1)
    min_referral_count: int = Field(ge=0, default=0)
    min_revenue_contribution: Decimal = Field(ge=0, default=Decimal("0"))
    commission_type: Literal["percentage", "fixed", "tier_based"]
    commission_value: Decimal = Field(ge=0)


class TierUpdateRequest(BaseModel):
    name: Optional[str] = None
    rank_order: Optional[int] = Field(None, ge=1)
    min_referral_count: Optional[int] = Field(None, ge=0)
    min_revenue_contribution: Optional[Decimal] = Field(None, ge=0)
    commission_type: Optional[Literal["percentage", "fixed", "tier_based"]] = None
    commission_value: Optional[Decimal] = Field(None, ge=0)


class PartnerResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    business_name: Optional[str] = None
    category: Optional[str] = None
    email: str
    phone: Optional[str] = None
    status: str
    tier_id: Optional[uuid.UUID] = None
    total_referral_count: int
    total_revenue_contribution: Decimal
    created_at: datetime
    # Populated only when listing with sort=rank (AI-RANK-002); null otherwise.
    rank_score: Optional[float] = None
    # Latest churn_risk score (0–100) from ai_scores; null until scoring runs.
    churn_score: Optional[float] = None

    model_config = {"from_attributes": True}


class AdminPartnerUpdateRequest(BaseModel):
    name: Optional[str] = None
    business_name: Optional[str] = None
    category: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[Literal["active", "suspended", "pending"]] = None
    tier_id: Optional[uuid.UUID] = None


class PartnerSelfUpdateRequest(BaseModel):
    name: Optional[str] = None
    business_name: Optional[str] = None
    category: Optional[str] = None
    phone: Optional[str] = None
