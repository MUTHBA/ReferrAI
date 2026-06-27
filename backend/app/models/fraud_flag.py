# -----------------------------------------------------------------------------
# backend/app/models/fraud_flag.py
#
# AI-generated fraud alerts routed to the admin review queue. Per CLAUDE.md,
# AI models must never auto-suspend accounts — they only create FraudFlag rows.
# An active pending_review flag blocks withdrawal auto-approval in the service
# layer. The status workflow is: pending_review → confirmed or dismissed.
# reviewed_by and reviewed_at are nullable until an admin acts on the flag.
# Each flag links to the AIScore row that triggered it for full auditability.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FraudFlag(Base):
    __tablename__ = "fraud_flags"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_review', 'confirmed', 'dismissed')",
            name="ck_fraud_flags_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False, index=True
    )
    ai_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_scores.id"), nullable=False
    )
    referral_click_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("referral_clicks.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending_review",
        server_default=text("'pending_review'"),
        index=True,
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
