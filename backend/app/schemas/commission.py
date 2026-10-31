# -----------------------------------------------------------------------------
# backend/app/schemas/commission.py
#
# Response shapes for the commission endpoints: a single commission joined
# with the conversion it was earned on (and the partner, for admin lists),
# plus a paginated wrapper.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CommissionResponse(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    conversion_id: uuid.UUID
    amount: Decimal
    commission_type: str
    tier_id: Optional[uuid.UUID] = None
    status: str
    calculated_at: datetime

    model_config = {"from_attributes": True}


class CommissionDetailResponse(CommissionResponse):
    partner_name: Optional[str] = None
    external_reference: Optional[str] = None
    conversion_value: Optional[Decimal] = None
    converted_at: Optional[datetime] = None


class CommissionPage(BaseModel):
    items: list[CommissionDetailResponse]
    total: int
    limit: int
    offset: int
    # Sum of commission amounts per status for the same partner/search filter
    # (ignores the status filter), e.g. {"approved": "120.00", "paid": "80.00"}.
    totals: dict[str, Decimal] = {}


class CommissionReverseRequest(BaseModel):
    reason: Optional[str] = None
