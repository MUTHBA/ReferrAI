import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DiscoveredPartner(Base):
    __tablename__ = "discovered_partners"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'reviewed', 'invited', 'dismissed')",
            name="ck_discovered_partners_status",
        ),
        CheckConstraint(
            "potential_score IS NULL OR (potential_score >= 0 AND potential_score <= 100)",
            name="ck_discovered_partners_potential_score_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    geographic_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    potential_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True, index=True
    )
    score_factors: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ai_score_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_scores.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
        server_default=text("'new'"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
