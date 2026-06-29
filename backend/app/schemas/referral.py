# -----------------------------------------------------------------------------
# backend/app/schemas/referral.py
#
# Pydantic schemas for the referral link and code endpoints. ReferralLinkResponse
# includes a computed referral_url field (the shareable /r/{slug} URL) that is
# not stored on the ORM model, so it cannot use from_attributes — it is built
# explicitly in the route. ReferralCodeResponse is built directly from the ORM.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ReferralLinkCreateRequest(BaseModel):
    destination_url: str


class ReferralLinkResponse(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    slug: str
    referral_url: str
    destination_url: str
    qr_code_data: Optional[str]
    is_active: bool
    created_at: datetime


class ReferralCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    partner_id: uuid.UUID
    code: str
    is_active: bool
    created_at: datetime
