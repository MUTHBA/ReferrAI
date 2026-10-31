# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/partners.py
#
# Partner profile endpoints (PRT-001) and tier CRUD (PRT-002). Admin partner
# lists exclude synthetic partners and include each partner's latest AI
# scores and tier name. Admin mutations are audited by PartnerService.
# -----------------------------------------------------------------------------

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import client_ip, get_current_user, require_admin, require_partner
from app.models.partner import Partner
from app.models.user import User
from app.schemas.dashboard import PartnerDashboardResponse
from app.schemas.referral_conversion import ConversionWithScoreResponse
from app.schemas.partner import (
    AdminPartnerUpdateRequest,
    PartnerResponse,
    PartnerSelfUpdateRequest,
    TierCreateRequest,
    TierResponse,
    TierUpdateRequest,
)
from app.services.partner_service import (
    AccessDeniedError,
    InvalidTierRateError,
    PartnerNotFoundError,
    PartnerService,
    TierInUseError,
    TierNotFoundError,
    TierRankConflictError,
)

router = APIRouter(tags=["partners"])


async def _enriched(service: PartnerService, partners: list[Partner]) -> list[PartnerResponse]:
    maps = await service.score_maps()
    tiers = await service.tier_names()
    return [
        PartnerResponse.model_validate(p).model_copy(
            update={
                **{name: values.get(p.id) for name, values in maps.items()},
                "tier_name": tiers.get(p.tier_id) if p.tier_id else None,
            }
        )
        for p in partners
    ]


# ------------------------------------------------------------------ #
# Partner profile endpoints (PRT-001)
# ------------------------------------------------------------------ #
@router.get("/partners", response_model=list[PartnerResponse])
async def list_partners(
    sort: Optional[Literal["rank", "newest", "revenue", "churn"]] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=100),
    partner_status: Optional[Literal["active", "suspended", "pending"]] = Query(default=None, alias="status"),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[PartnerResponse]:
    service = PartnerService(db)
    items = await _enriched(service, await service.list_partners(search, partner_status))
    if sort == "rank":
        items.sort(key=lambda p: (p.rank_score is None, -(p.rank_score or 0)))
    elif sort == "revenue":
        items.sort(key=lambda p: p.total_revenue_contribution, reverse=True)
    elif sort == "churn":
        items.sort(key=lambda p: (p.churn_score is None, -(p.churn_score or 0)))
    return items


@router.get("/partners/{partner_id}", response_model=PartnerResponse)
async def get_partner(
    partner_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PartnerResponse:
    service = PartnerService(db)
    try:
        partner = await service.get_partner(partner_id, current_user.id, current_user.role)
    except PartnerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    except AccessDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if current_user.role == "admin":
        return (await _enriched(service, [partner]))[0]
    return PartnerResponse.model_validate(partner)


@router.get("/partners/{partner_id}/conversions", response_model=list[ConversionWithScoreResponse])
async def list_partner_conversions(
    partner_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[ConversionWithScoreResponse]:
    from app.api.v1.routes.referrals import conversion_rows_to_response
    from app.services.referral_conversion_service import ReferralConversionService

    rows = await ReferralConversionService(db).list_for_partner_with_quality(partner_id, limit, offset)
    return conversion_rows_to_response(rows)


@router.get("/partners/{partner_id}/dashboard", response_model=PartnerDashboardResponse)
async def partner_dashboard_as_admin(
    partner_id: uuid.UUID,
    days: int = Query(default=30, ge=1, le=90),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PartnerDashboardResponse:
    """The partner's own dashboard figures, for the admin partner-detail page."""
    from app.services.dashboard_service import DashboardService

    partner = await db.get(Partner, partner_id)
    if partner is None or partner.is_synthetic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    return await DashboardService(db).partner_dashboard_for(partner, days)


@router.patch("/partners/{partner_id}", response_model=PartnerResponse)
async def update_partner(
    partner_id: uuid.UUID,
    payload: AdminPartnerUpdateRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PartnerResponse:
    service = PartnerService(db)
    try:
        partner = await service.update_partner_as_admin(partner_id, payload, current_user.id, client_ip(request))
    except PartnerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    except TierNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
    return (await _enriched(service, [partner]))[0]


@router.get("/me/partner", response_model=PartnerResponse)
async def get_own_profile(
    current_user: User = Depends(require_partner),
    db: AsyncSession = Depends(get_db),
) -> PartnerResponse:
    service = PartnerService(db)
    try:
        partner = await service.get_own_partner(current_user.id)
    except PartnerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner profile not found")
    tiers = await service.tier_names()
    return PartnerResponse.model_validate(partner).model_copy(
        update={"tier_name": tiers.get(partner.tier_id) if partner.tier_id else None}
    )


@router.patch("/me/partner", response_model=PartnerResponse)
async def update_own_profile(
    payload: PartnerSelfUpdateRequest,
    current_user: User = Depends(require_partner),
    db: AsyncSession = Depends(get_db),
) -> PartnerResponse:
    try:
        partner = await PartnerService(db).update_partner_as_self(current_user.id, payload)
    except PartnerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner profile not found")
    return PartnerResponse.model_validate(partner)


# ------------------------------------------------------------------ #
# Tier CRUD endpoints (PRT-002)
# ------------------------------------------------------------------ #
@router.get("/tiers", response_model=list[TierResponse])
async def list_tiers(
    # Readable by any authenticated user so partners can show tier progress.
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TierResponse]:
    return [TierResponse.model_validate(t) for t in await PartnerService(db).list_tiers()]


@router.post("/tiers", response_model=TierResponse, status_code=status.HTTP_201_CREATED)
async def create_tier(
    payload: TierCreateRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TierResponse:
    try:
        tier = await PartnerService(db).create_tier(
            name=payload.name,
            rank_order=payload.rank_order,
            min_referral_count=payload.min_referral_count,
            min_revenue_contribution=payload.min_revenue_contribution,
            commission_type=payload.commission_type,
            commission_value=payload.commission_value,
            admin_id=current_user.id,
            ip_address=client_ip(request),
        )
    except TierRankConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return TierResponse.model_validate(tier)


@router.patch("/tiers/{tier_id}", response_model=TierResponse)
async def update_tier(
    tier_id: uuid.UUID,
    payload: TierUpdateRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TierResponse:
    try:
        tier = await PartnerService(db).update_tier(tier_id, payload, current_user.id, client_ip(request))
    except TierNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
    except TierRankConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InvalidTierRateError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return TierResponse.model_validate(tier)


@router.delete("/tiers/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tier(
    tier_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await PartnerService(db).delete_tier(tier_id, current_user.id, client_ip(request))
    except TierNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
    except TierInUseError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
