# -----------------------------------------------------------------------------
# backend/app/schemas/synthetic_data.py
#
# Request and response schemas for the admin synthetic-data generation endpoint
# (AI-DATA-002) and batch scoring endpoints (AI-CHURN-003, AI-RANK-001).
# Validation bounds prevent accidental runaway inserts: partner count capped at
# 500 (avoids multi-minute bcrypt wall), clicks per partner capped at 200,
# conversions capped at 10 000.
# -----------------------------------------------------------------------------

from typing import Literal, Optional

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


class ChurnScoringResponse(BaseModel):
    partners_scored: int


class RankingScoringResponse(BaseModel):
    partners_scored: int


class TrainModelsRequest(BaseModel):
    models: list[Literal["quality", "fraud", "churn"]] = ["quality", "fraud", "churn"]
    n_partners: int = Field(default=300, ge=50, le=2000, description="Synthetic partners to simulate")
    seed: int = 7


class ModelInfo(BaseModel):
    name: str
    trained: bool
    version: Optional[str] = None
    trained_at: Optional[str] = None
    algorithm: Optional[str] = None
    features: Optional[list[str]] = None
    feature_labels: Optional[list[str]] = None  # plain-language names, same order as features
    metrics: Optional[dict] = None
    training_rows: Optional[int] = None


class TrainingStatusResponse(BaseModel):
    state: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    models: list[str] = []
    error: Optional[str] = None
    results: dict = {}
    available_models: list[ModelInfo] = []
