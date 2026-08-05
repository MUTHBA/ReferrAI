# -----------------------------------------------------------------------------
# backend/app/schemas/referral_conversion.py
#
# Pydantic schemas for the conversion recording endpoint (REF-004).
# ConversionCreate accepts the referral_code as a human-readable string (not
# UUID) because callers know the code they issued, not its database ID — the
# service resolves it. ConversionResponse mirrors every column of the
# ReferralConversion model and uses from_attributes for ORM compatibility.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ConversionCreate(BaseModel):
    """Payload for recording a new referral conversion.

    partner_id is not supplied by the caller — the route derives it
    server-side from click_id (via referral_clicks) or referral_code (via
    referral_codes), so a caller cannot submit a mismatched pair.
    """

    partner_id: Optional[uuid.UUID] = None
    external_reference: str
    referral_code: Optional[str] = None
    click_id: Optional[uuid.UUID] = None
    conversion_value: Decimal


class ConversionResponse(BaseModel):
    """Full representation of a recorded ReferralConversion row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    partner_id: uuid.UUID
    external_reference: str
    click_id: Optional[uuid.UUID]
    referral_link_id: Optional[uuid.UUID]
    referral_code_id: Optional[uuid.UUID]
    conversion_value: Decimal
    attribution_model: str
    converted_at: datetime
    is_synthetic: bool


class ConversionWithScoreResponse(BaseModel):
    """Conversion summary with its most recent AI quality score (AI-QUAL-004/AI-XAI-003).

    quality_score is None when the background scoring task has not completed
    yet — the UI should display "Pending" in that case.
    quality_explanation is the plain-language SHAP explanation string, or None
    if explanation generation has not run yet.
    """

    id: uuid.UUID
    conversion_value: Decimal
    attribution_model: str
    converted_at: datetime
    quality_score: Optional[float] = None
    quality_explanation: Optional[str] = None
