# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/wallet.py
#
# Wallet and withdrawal endpoints. Partner routes (/wallet, /withdrawals POST)
# use require_partner; admin routes (/withdrawals GET and PATCH) use
# require_admin. Route handlers translate WalletService exceptions into the
# appropriate HTTP status codes — business logic stays in the service layer.
# Mounted in main.py with prefix="/api/v1".
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin, require_partner
from app.models.user import User
from app.repositories.partner_repository import PartnerRepository
from app.schemas.wallet import (
    TransactionResponse,
    WalletResponse,
    WithdrawalRequest,
    WithdrawalResponse,
    WithdrawalReviewRequest,
)
from app.services.wallet_service import (
    BelowMinimumWithdrawalError,
    InsufficientBalanceError,
    WalletNotFoundError,
    WalletService,
    WithdrawalAlreadyProcessedError,
    WithdrawalNotFoundError,
)

router = APIRouter(tags=["wallet"])


@router.get("/wallet", response_model=WalletResponse)
async def get_wallet(
    current_user: User = Depends(require_partner),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    partner = await PartnerRepository(db).get_by_user_id(current_user.id)
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner profile not found")
    try:
        wallet = await WalletService(db).get_wallet(partner.id)
    except WalletNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    return WalletResponse.model_validate(wallet)


@router.get("/wallet/transactions", response_model=list[TransactionResponse])
async def get_transactions(
    current_user: User = Depends(require_partner),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionResponse]:
    partner = await PartnerRepository(db).get_by_user_id(current_user.id)
    if partner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner profile not found")
    transactions = await WalletService(db).get_transactions(partner.id)
    return [TransactionResponse.model_validate(t) for t in transactions]


@router.post("/withdrawals", response_model=WithdrawalResponse, status_code=status.HTTP_201_CREATED)
async def request_withdrawal(
    payload: WithdrawalRequest,
    current_user: User = Depends(require_partner),
    db: AsyncSession = Depends(get_db),
) -> WithdrawalResponse:
    try:
        withdrawal = await WalletService(db).request_withdrawal(current_user.id, payload.amount)
    except BelowMinimumWithdrawalError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Amount is below the minimum withdrawal of {exc.minimum}",
        )
    except InsufficientBalanceError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient wallet balance",
        )
    return WithdrawalResponse.model_validate(withdrawal)


@router.get("/withdrawals", response_model=list[WithdrawalResponse])
async def list_withdrawals(
    withdrawal_status: Optional[str] = Query(None, alias="status"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[WithdrawalResponse]:
    withdrawals = await WalletService(db).list_withdrawals(withdrawal_status)
    return [WithdrawalResponse.model_validate(w) for w in withdrawals]


@router.patch("/withdrawals/{withdrawal_id}", response_model=WithdrawalResponse)
async def review_withdrawal(
    withdrawal_id: uuid.UUID,
    payload: WithdrawalReviewRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WithdrawalResponse:
    try:
        withdrawal = await WalletService(db).review_withdrawal(
            withdrawal_id=withdrawal_id,
            action=payload.status,
            reviewer_id=current_user.id,
            notes=payload.notes,
        )
    except WithdrawalNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Withdrawal not found")
    except WithdrawalAlreadyProcessedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Withdrawal has already been processed",
        )
    except InsufficientBalanceError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Insufficient wallet balance to approve withdrawal",
        )
    return WithdrawalResponse.model_validate(withdrawal)
