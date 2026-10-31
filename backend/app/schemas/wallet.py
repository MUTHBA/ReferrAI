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
    # Spendable balance. Funds held by pending withdrawals are already deducted.
    balance: Decimal
    total_earned: Decimal
    total_withdrawn: Decimal
    # Amount currently held by withdrawals awaiting admin review.
    pending_withdrawals: Decimal = Decimal("0.00")
    # Current withdrawal rules (from settings), so the partner UI can explain them.
    min_withdrawal_amount: Optional[Decimal] = None
    auto_approval_threshold: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: uuid.UUID
    wallet_id: uuid.UUID
    reference_id: uuid.UUID
    reference_type: str
    amount: Decimal
    balance_after: Decimal
    created_at: datetime
    # Plain-language label, e.g. "Commission for demo-order-2041".
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class WithdrawalRequest(BaseModel):
    amount: Decimal = Field(
        gt=0, max_digits=12, decimal_places=2, description="Amount to withdraw — positive, at most 2 decimals"
    )


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
    # Populated on admin listings.
    partner_name: Optional[str] = None
    partner_email: Optional[str] = None
    wallet_balance: Optional[Decimal] = None
    open_fraud_flag: Optional[bool] = None

    model_config = {"from_attributes": True}


class WithdrawalPaidRequest(BaseModel):
    notes: Optional[str] = None


class WithdrawalReviewRequest(BaseModel):
    status: Literal["approved", "rejected"]
    notes: Optional[str] = None
