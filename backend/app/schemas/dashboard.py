# -----------------------------------------------------------------------------
# backend/app/schemas/dashboard.py
#
# Pydantic response shapes for the admin and partner dashboard endpoints
# (RPT-001, RPT-002). VolumeDataPoint holds one day's click/conversion
# counts for the volume chart. AdminKPIs and PartnerKPIs are the top-level
# stat cards. Scores are Optional[Decimal] — null until Phase 4 AI models
# are trained and scoring runs have been executed.
# Added rank_position and total_ranked_partners for AI-RANK-003 — populated
# after run-ranking has been executed; null until then.
# AI-CHURN-004: added ChurnAtRiskPartner and churn_at_risk_partners list to
# AdminDashboardResponse so the admin dashboard can surface the at-risk list
# without a separate endpoint.
# -----------------------------------------------------------------------------

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class VolumeDataPoint(BaseModel):
    date: date
    clicks: int
    conversions: int


class ChurnAtRiskPartner(BaseModel):
    partner_id: uuid.UUID
    name: str
    churn_score: float


class AdminKPIs(BaseModel):
    total_conversions: int
    active_partners: int
    total_commission: Decimal
    pending_payout_count: int
    pending_payout_amount: Decimal
    fraud_alert_count: int
    churn_alert_count: int


class AdminDashboardResponse(BaseModel):
    kpis: AdminKPIs
    volume_chart: list[VolumeDataPoint]
    churn_at_risk_partners: list[ChurnAtRiskPartner] = []


class PartnerKPIs(BaseModel):
    referral_count: int
    conversion_count: int
    total_earnings: Decimal
    wallet_balance: Decimal


class PartnerDashboardResponse(BaseModel):
    kpis: PartnerKPIs
    quality_score: Optional[Decimal] = None
    churn_score: Optional[Decimal] = None
    rank_score: Optional[Decimal] = None
    rank_position: Optional[int] = None
    total_ranked_partners: Optional[int] = None
