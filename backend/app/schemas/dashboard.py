# -----------------------------------------------------------------------------
# backend/app/schemas/dashboard.py
#
# Response shapes for the admin (RPT-001) and partner (RPT-002) dashboards.
# All figures exclude synthetic records. Money values are Decimal (serialised
# as strings); scores are 0-100 floats or null when not yet computed / when
# the model is unavailable. Daily series are zero-filled, UTC-dated.
# -----------------------------------------------------------------------------

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class VolumeDataPoint(BaseModel):
    date: date
    clicks: int
    conversions: int
    revenue: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")


class ChurnAtRiskPartner(BaseModel):
    partner_id: uuid.UUID
    name: str
    churn_score: float


class TopPartner(BaseModel):
    partner_id: uuid.UUID
    name: str
    tier_name: Optional[str] = None
    conversions: int
    revenue: Decimal
    commission: Decimal
    rank_score: Optional[float] = None


class RecentFraudFlag(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    partner_name: str
    score: Optional[float] = None
    explanation: Optional[str] = None
    created_at: datetime


class PendingWithdrawalSummary(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    partner_name: str
    amount: Decimal
    requested_at: datetime


class AdminKPIs(BaseModel):
    total_conversions: int
    active_partners: int
    total_commission: Decimal
    pending_payout_count: int
    pending_payout_amount: Decimal
    fraud_alert_count: int
    churn_alert_count: int
    # Period figures (last `days` days).
    total_revenue: Decimal = Decimal("0")
    period_clicks: int = 0
    period_conversions: int = 0
    period_revenue: Decimal = Decimal("0")
    period_commission: Decimal = Decimal("0")
    conversion_rate: Optional[float] = None  # period conversions / period clicks, 0-1
    total_paid_out: Decimal = Decimal("0")


class AdminDashboardResponse(BaseModel):
    days: int = 30
    kpis: AdminKPIs
    volume_chart: list[VolumeDataPoint]
    churn_at_risk_partners: list[ChurnAtRiskPartner] = []
    top_partners: list[TopPartner] = []
    recent_fraud_flags: list[RecentFraudFlag] = []
    pending_withdrawals: list[PendingWithdrawalSummary] = []


class PartnerKPIs(BaseModel):
    # Number of real conversions credited to the partner.
    referral_count: int
    conversion_count: int
    total_earnings: Decimal
    wallet_balance: Decimal
    link_count: int = 0
    code_count: int = 0
    click_count: int = 0
    pending_withdrawals: Decimal = Decimal("0")
    total_withdrawn: Decimal = Decimal("0")
    conversion_rate: Optional[float] = None


class EarningsDataPoint(BaseModel):
    date: date
    clicks: int
    conversions: int
    earnings: Decimal


class TierProgress(BaseModel):
    current_tier: Optional[str] = None
    current_rate_label: Optional[str] = None
    next_tier: Optional[str] = None
    next_rate_label: Optional[str] = None
    referrals_needed: Optional[int] = None
    revenue_needed: Optional[Decimal] = None
    progress: Optional[float] = None  # 0-1 toward the next tier


class PartnerDashboardResponse(BaseModel):
    days: int = 30
    kpis: PartnerKPIs
    quality_score: Optional[Decimal] = None
    churn_score: Optional[Decimal] = None
    # ok | model_unavailable | insufficient_data | error, or None if never scored
    churn_status: Optional[str] = None
    rank_score: Optional[Decimal] = None
    rank_position: Optional[int] = None
    total_ranked_partners: Optional[int] = None
    earnings_chart: list[EarningsDataPoint] = []
    tier: TierProgress = TierProgress()
