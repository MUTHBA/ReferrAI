# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/wallet.py
#
# Wallet and withdrawal endpoints. Partners: view wallet + ledger, request a
# withdrawal, view their own withdrawal history. Admins: list the payout
# queue (with partner name/email), approve/reject a pending request, and mark
# an approved request as paid. Business rules live in WalletService.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import client_ip, get_current_partner, require_active_partner, require_admin
from app.models.partner import Partner
from app.models.user import User
from app.schemas.wallet import (
    TransactionResponse,
    WalletResponse,
    WithdrawalPaidRequest,
    WithdrawalRequest,
    WithdrawalResponse,
    WithdrawalReviewRequest,
)
from app.services.setting_service import SettingService
from app.services.wallet_service import (
    BelowMinimumWithdrawalError,
    InsufficientBalanceError,
    PartnerNotActiveError,
    WalletNotFoundError,
    WalletService,
    WithdrawalAlreadyProcessedError,
    WithdrawalNotFoundError,
)

router = APIRouter(tags=["wallet"])


@router.get("/wallet", response_model=WalletResponse)
async def get_wallet(
    partner: Partner = Depends(get_current_partner),
    db: AsyncSession = Depends(get_db),
) -> WalletResponse:
    try:
        wallet, pending = await WalletService(db).get_wallet(partner.id)
    except WalletNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    settings_svc = SettingService(db)
    return WalletResponse.model_validate(wallet).model_copy(
        update={
            "pending_withdrawals": pending,
            "min_withdrawal_amount": Decimal(str(await settings_svc.get("wallet.min_withdrawal_amount"))),
            "auto_approval_threshold": Decimal(str(await settings_svc.get("wallet.auto_approval_threshold"))),
        }
    )


@router.get("/wallet/transactions", response_model=list[TransactionResponse])
async def get_transactions(
    partner: Partner = Depends(get_current_partner),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionResponse]:
    service = WalletService(db)
    try:
        transactions = await service.get_transactions(partner.id)
    except WalletNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    labels = await service.describe_transactions(transactions)
    return [
        TransactionResponse.model_validate(t).model_copy(update={"description": labels.get(t.id)})
        for t in transactions
    ]


@router.post("/withdrawals", response_model=WithdrawalResponse, status_code=status.HTTP_201_CREATED)
async def request_withdrawal(
    payload: WithdrawalRequest,
    partner: Partner = Depends(require_active_partner),
    db: AsyncSession = Depends(get_db),
) -> WithdrawalResponse:
    try:
        withdrawal = await WalletService(db).request_withdrawal(partner, payload.amount)
    except BelowMinimumWithdrawalError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Amount is below the minimum withdrawal of {exc.minimum}",
        )
    except InsufficientBalanceError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Insufficient wallet balance")
    except PartnerNotActiveError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except WalletNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    return WithdrawalResponse.model_validate(withdrawal)


@router.get("/me/withdrawals", response_model=list[WithdrawalResponse])
async def list_my_withdrawals(
    partner: Partner = Depends(get_current_partner),
    db: AsyncSession = Depends(get_db),
) -> list[WithdrawalResponse]:
    rows = await WalletService(db).list_partner_withdrawals(partner.id)
    return [WithdrawalResponse.model_validate(w) for w in rows]


@router.get("/withdrawals", response_model=list[WithdrawalResponse])
async def list_withdrawals(
    withdrawal_status: Optional[str] = Query(None, alias="status"),
    partner_id: Optional[uuid.UUID] = Query(None),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[WithdrawalResponse]:
    service = WalletService(db)
    rows = await service.list_withdrawals(withdrawal_status, partner_id)
    flagged = await service.partners_with_open_fraud_flags()
    return [
        WithdrawalResponse.model_validate(w).model_copy(
            update={
                "partner_name": p.name,
                "partner_email": p.email,
                "wallet_balance": balance,
                "open_fraud_flag": p.id in flagged,
            }
        )
        for w, p, balance in rows
    ]


@router.patch("/withdrawals/{withdrawal_id}", response_model=WithdrawalResponse)
async def review_withdrawal(
    withdrawal_id: uuid.UUID,
    payload: WithdrawalReviewRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WithdrawalResponse:
    try:
        withdrawal = await WalletService(db).review_withdrawal(
            withdrawal_id=withdrawal_id,
            action=payload.status,
            reviewer_id=current_user.id,
            notes=payload.notes,
            ip_address=client_ip(request),
        )
    except WithdrawalNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Withdrawal not found")
    except WithdrawalAlreadyProcessedError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Withdrawal has already been processed")
    return WithdrawalResponse.model_validate(withdrawal)


@router.post("/withdrawals/{withdrawal_id}/paid", response_model=WithdrawalResponse)
async def mark_withdrawal_paid(
    withdrawal_id: uuid.UUID,
    request: Request,
    payload: Optional[WithdrawalPaidRequest] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WithdrawalResponse:
    try:
        withdrawal = await WalletService(db).mark_paid(
            withdrawal_id, current_user.id, payload.notes if payload else None, client_ip(request)
        )
    except WithdrawalNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Withdrawal not found")
    except WithdrawalAlreadyProcessedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Only approved withdrawals can be marked as paid"
        )
    return WithdrawalResponse.model_validate(withdrawal)
