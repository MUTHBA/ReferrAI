# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/referrals.py
#
# Two routers live here: `router` handles the versioned partner API (POST
# /api/v1/referrals/links, POST /api/v1/referrals/codes — both require_partner);
# `redirect_router` handles the public click-tracking redirect (GET /r/{slug} —
# no auth, registered at root in main.py). Keeping them together avoids splitting
# referral route logic across files.
# -----------------------------------------------------------------------------

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_partner
from app.models.user import User
from app.schemas.referral import (
    ReferralCodeResponse,
    ReferralLinkCreateRequest,
    ReferralLinkResponse,
)
from app.services.referral_click_service import ReferralClickService
from app.services.referral_code_service import ReferralCodeService
from app.services.referral_link_service import PartnerProfileNotFoundError, ReferralLinkService

logger = logging.getLogger(__name__)

# Versioned partner API — mounted at /api/v1 in main.py
router = APIRouter(prefix="/referrals", tags=["referrals"])

# Public redirect — mounted at root (no prefix) in main.py
redirect_router = APIRouter(tags=["referrals"])


@router.post("/links", response_model=ReferralLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_referral_link(
    payload: ReferralLinkCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_partner),
) -> ReferralLinkResponse:
    service = ReferralLinkService(db)
    try:
        link = await service.create(
            user_id=current_user.id,
            destination_url=payload.destination_url,
            base_url=str(request.base_url),
        )
    except PartnerProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner profile not found for this user",
        )

    referral_url = str(request.base_url) + f"r/{link.slug}"
    return ReferralLinkResponse(
        id=link.id,
        partner_id=link.partner_id,
        slug=link.slug,
        referral_url=referral_url,
        destination_url=link.destination_url,
        qr_code_data=link.qr_code_data,
        is_active=link.is_active,
        created_at=link.created_at,
    )


@router.post("/codes", response_model=ReferralCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_referral_code(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_partner),
) -> ReferralCodeResponse:
    service = ReferralCodeService(db)
    try:
        code = await service.create(user_id=current_user.id)
    except PartnerProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner profile not found for this user",
        )

    return ReferralCodeResponse.model_validate(code)


@redirect_router.get("/r/{slug}", name="track_click")
async def track_click(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    utm_source: Optional[str] = None,
) -> RedirectResponse:
    service = ReferralClickService(db)
    destination = await service.track(
        slug=slug,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        utm_source=utm_source,
    )
    if destination is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral link not found or inactive",
        )
    return RedirectResponse(url=destination, status_code=302)
