# -----------------------------------------------------------------------------
# backend/app/schemas/commission.py
#
# Pydantic response shape for commission records, used in the CSV export
# (RPT-003) and any future commission-listing endpoint. Mirrors the
# Commission ORM model columns that are safe to expose externally.
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
