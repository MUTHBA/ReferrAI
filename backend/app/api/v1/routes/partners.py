# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/partners.py
#
# Partner and tier endpoints. Admin-only routes: list all partners, view any
# partner, update any partner (including status/tier), full tier CRUD.
# Partner-only routes: view own profile, update own profile (name/contact
# fields only — no status or tier changes). Mounted in main.py with
# prefix="/api/v1".
# -----------------------------------------------------------------------------

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin, require_partner
from app.models.user import User
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
    PartnerNotFoundError,
    PartnerService,
    TierNotFoundError,
    TierRankConflictError,
)

router = APIRouter(tags=["partners"])


# ------------------------------------------------------------------ #
# Partner profile endpoints (PRT-001)
# ------------------------------------------------------------------ #

@router.get("/partners", response_model=list[PartnerResponse])
async def list_partners(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[PartnerResponse]:
    partners = await PartnerService(db).list_partners()
    return [PartnerResponse.model_validate(p) for p in partners]


@router.get("/partners/{partner_id}", response_model=PartnerResponse)
async def get_partner(
    partner_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PartnerResponse:
    try:
        partner = await PartnerService(db).get_partner(partner_id, current_user.id, current_user.role)
    except PartnerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    except AccessDeniedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return PartnerResponse.model_validate(partner)


@router.patch("/partners/{partner_id}", response_model=PartnerResponse)
async def update_partner(
    partner_id: uuid.UUID,
    payload: AdminPartnerUpdateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PartnerResponse:
    try:
        partner = await PartnerService(db).update_partner_as_admin(partner_id, payload)
    except PartnerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    except TierNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
    return PartnerResponse.model_validate(partner)


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
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TierResponse]:
    tiers = await PartnerService(db).list_tiers()
    return [TierResponse.model_validate(t) for t in tiers]


@router.post("/tiers", response_model=TierResponse, status_code=status.HTTP_201_CREATED)
async def create_tier(
    payload: TierCreateRequest,
    _: User = Depends(require_admin),
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
        )
    except TierRankConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return TierResponse.model_validate(tier)


@router.patch("/tiers/{tier_id}", response_model=TierResponse)
async def update_tier(
    tier_id: uuid.UUID,
    payload: TierUpdateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TierResponse:
    try:
        tier = await PartnerService(db).update_tier(tier_id, payload)
    except TierNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
    except TierRankConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return TierResponse.model_validate(tier)


@router.delete("/tiers/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tier(
    tier_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await PartnerService(db).delete_tier(tier_id)
    except TierNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
