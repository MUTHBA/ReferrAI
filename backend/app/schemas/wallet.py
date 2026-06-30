# -----------------------------------------------------------------------------
# backend/app/schemas/wallet.py
#
# Pydantic request/response shapes for the wallet and withdrawal endpoints.
# WalletResponse exposes balances; TransactionResponse covers the ledger
# history. WithdrawalRequest validates the requested amount (must be positive).
# WithdrawalReviewRequest is admin-only — status must be "approved" or
# "rejected". WithdrawalResponse is shared across partner and admin views.
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    balance: Decimal
    total_earned: Decimal
    total_withdrawn: Decimal

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: uuid.UUID
    wallet_id: uuid.UUID
    reference_id: uuid.UUID
    reference_type: str
    amount: Decimal
    balance_after: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class WithdrawalRequest(BaseModel):
    amount: Decimal = Field(gt=0, description="Amount to withdraw — must be positive")


class WithdrawalResponse(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    wallet_id: uuid.UUID
    amount: Decimal
    status: str
    requires_manual_review: bool
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class WithdrawalReviewRequest(BaseModel):
    status: Literal["approved", "rejected"]
    notes: Optional[str] = None
