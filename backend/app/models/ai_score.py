import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AIScore(Base):
    """Append-only score store — insert a new row on each re-score, never update."""

    __tablename__ = "ai_scores"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('referral', 'partner', 'candidate')",
            name="ck_ai_scores_entity_type",
        ),
        CheckConstraint(
            "score_type IN ('quality', 'fraud_risk', 'churn_risk', 'ranking', 'partner_potential')",
            name="ck_ai_scores_score_type",
        ),
        CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_ai_scores_score_range",
        ),
        Index("ix_ai_scores_entity", "entity_type", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    score_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    contributing_factors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE")
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
