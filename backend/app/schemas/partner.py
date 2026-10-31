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

from pydantic import BaseModel, Field, model_validator


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


def _check_rate(commission_type: Optional[str], value: Optional[Decimal]) -> None:
    """Percentage / tier_based rates are fractions: 0 < value <= 1 (0.10 = 10%)."""
    if commission_type in ("percentage", "tier_based") and value is not None:
        if not (Decimal("0") < value <= Decimal("1")):
            raise ValueError(
                "commission_value for percentage tiers must be a fraction between 0 and 1 (e.g. 0.10 for 10%)"
            )


class TierCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    rank_order: int = Field(ge=1)
    min_referral_count: int = Field(ge=0, default=0)
    min_revenue_contribution: Decimal = Field(ge=0, default=Decimal("0"))
    commission_type: Literal["percentage", "fixed", "tier_based"]
    commission_value: Decimal = Field(ge=0, max_digits=10, decimal_places=4)

    @model_validator(mode="after")
    def _validate_rate(self) -> "TierCreateRequest":
        _check_rate(self.commission_type, self.commission_value)
        return self


class TierUpdateRequest(BaseModel):
    name: Optional[str] = None
    rank_order: Optional[int] = Field(None, ge=1)
    min_referral_count: Optional[int] = Field(None, ge=0)
    min_revenue_contribution: Optional[Decimal] = Field(None, ge=0)
    commission_type: Optional[Literal["percentage", "fixed", "tier_based"]] = None
    commission_value: Optional[Decimal] = Field(None, ge=0, max_digits=10, decimal_places=4)

    @model_validator(mode="after")
    def _validate_rate(self) -> "TierUpdateRequest":
        # When only the value changes, the service re-checks against the stored type.
        _check_rate(self.commission_type, self.commission_value)
        return self


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
    # Latest partner-level fraud_risk score (0–100); admin lists only.
    fraud_score: Optional[float] = None
    # Average of the latest quality score across the partner's conversions.
    quality_score: Optional[float] = None
    tier_name: Optional[str] = None

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
