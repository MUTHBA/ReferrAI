# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/commissions.py
#
# Commission endpoints. Partners: paginated history of their own commissions
# (GET /me/commissions). Admins: list all commissions (GET /commissions) and
# reverse one, e.g. after confirming fraud (POST /commissions/{id}/reverse),
# which debits the partner's wallet and writes an audit row.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import client_ip, get_current_partner, require_admin
from app.models.partner import Partner
from app.models.user import User
from app.schemas.commission import (
    CommissionDetailResponse,
    CommissionPage,
    CommissionResponse,
    CommissionReverseRequest,
)
from app.services.commission_service import (
    CommissionNotFoundError,
    CommissionNotReversibleError,
    CommissionService,
)
from app.services.wallet_service import InsufficientBalanceError

router = APIRouter(tags=["commissions"])


def _page(rows, total: int, limit: int, offset: int, totals: Optional[dict] = None) -> CommissionPage:
    return CommissionPage(
        items=[
            CommissionDetailResponse.model_validate(c).model_copy(
                update={
                    "partner_name": p.name,
                    "external_reference": conv.external_reference,
                    "conversion_value": conv.conversion_value,
                    "converted_at": conv.converted_at,
                }
            )
            for c, conv, p in rows
        ],
        total=total,
        totals=totals or {},
        limit=limit,
        offset=offset,
    )


@router.get("/me/commissions", response_model=CommissionPage)
async def list_my_commissions(
    commission_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    partner: Partner = Depends(get_current_partner),
    db: AsyncSession = Depends(get_db),
) -> CommissionPage:
    service = CommissionService(db)
    rows, total = await service.list_for_partner(partner.id, limit, offset, commission_status, search)
    return _page(rows, total, limit, offset, await service.sums_by_status(partner.id, search))


@router.get("/commissions", response_model=CommissionPage)
async def list_commissions(
    commission_status: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None, max_length=100),
    partner_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CommissionPage:
    service = CommissionService(db)
    rows, total = await service.list_all(commission_status, limit, offset, search, partner_id)
    return _page(rows, total, limit, offset, await service.sums_by_status(partner_id, search))


@router.post("/commissions/{commission_id}/reverse", response_model=CommissionResponse)
async def reverse_commission(
    commission_id: uuid.UUID,
    request: Request,
    payload: Optional[CommissionReverseRequest] = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CommissionResponse:
    try:
        commission = await CommissionService(db).reverse(
            commission_id, current_user.id, payload.reason if payload else None, client_ip(request)
        )
    except CommissionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commission not found")
    except CommissionNotReversibleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except InsufficientBalanceError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The partner's balance is lower than the commission amount; it may already have been withdrawn",
        )
    return CommissionResponse.model_validate(commission)
