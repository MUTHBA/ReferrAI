# -----------------------------------------------------------------------------
# backend/app/schemas/synthetic_data.py
#
# Request and response schemas for the admin synthetic-data generation endpoint
# (AI-DATA-002) and batch scoring endpoints (AI-CHURN-003, AI-RANK-001).
# Validation bounds prevent accidental runaway inserts: partner count capped at
# 500 (avoids multi-minute bcrypt wall), clicks per partner capped at 200,
# conversions capped at 10 000.
# -----------------------------------------------------------------------------

from pydantic import BaseModel, Field


class SyntheticDataRequest(BaseModel):
    num_partners: int = Field(default=10, ge=1, le=500)
    num_clicks_per_partner: int = Field(default=20, ge=1, le=200)
    num_conversions: int = Field(default=50, ge=0, le=10_000)
    fraud_ratio: float = Field(default=0.2, ge=0.0, le=1.0)
    churn_ratio: float = Field(default=0.3, ge=0.0, le=1.0)


class SyntheticDataResponse(BaseModel):
    partners_created: int
    clicks_created: int
    conversions_created: int
    fraud_labeled_clicks_created: int
    churned_partners_created: int


class ChurnScoringResponse(BaseModel):
    partners_scored: int


class RankingScoringResponse(BaseModel):
    partners_scored: int
