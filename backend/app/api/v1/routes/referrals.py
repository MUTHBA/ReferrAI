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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin, require_partner
from app.models.ai_score import AIScore
from app.models.referral import ReferralConversion
from app.models.user import User
from app.repositories.partner_repository import PartnerRepository
from app.schemas.referral import (
    ReferralCodeResponse,
    ReferralLinkCreateRequest,
    ReferralLinkResponse,
)
from app.schemas.referral_conversion import (
    ConversionCreate,
    ConversionResponse,
    ConversionWithScoreResponse,
)
from app.services import ai_service
from app.services.referral_click_service import ReferralClickService
from app.services.referral_code_service import ReferralCodeService
from app.services.referral_conversion_service import (
    ConversionPartnerNotFoundError,
    ReferralCodeNotFoundError,
    ReferralConversionService,
)
from app.services.referral_link_service import PartnerProfileNotFoundError, ReferralLinkService

logger = logging.getLogger(__name__)

# Versioned partner API — mounted at /api/v1 in main.py
router = APIRouter(prefix="/referrals", tags=["referrals"])

# Public redirect — mounted at root (no prefix) in main.py
redirect_router = APIRouter(tags=["referrals"])


@router.get("/conversions", response_model=list[ConversionWithScoreResponse])
async def list_my_conversions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_partner),
) -> list[ConversionWithScoreResponse]:
    """Return the authenticated partner's conversions with their latest quality score."""
    partner = await PartnerRepository(db).get_by_user_id(current_user.id)
    if partner is None:
        return []

    # Two correlated scalar subqueries — both target the most recent quality
    # ai_scores row per conversion. Separate subqueries are needed because
    # SQLAlchemy scalar_subquery() can only SELECT one column at a time.
    def _quality_subquery(column):
        return (
            select(column)
            .where(AIScore.entity_id == ReferralConversion.id)
            .where(AIScore.entity_type == "referral")
            .where(AIScore.score_type == "quality")
            .order_by(AIScore.calculated_at.desc())
            .limit(1)
            .correlate(ReferralConversion)
            .scalar_subquery()
        )

    latest_quality = _quality_subquery(AIScore.score)
    latest_explanation = _quality_subquery(AIScore.explanation)

    stmt = (
        select(
            ReferralConversion,
            latest_quality.label("quality_score"),
            latest_explanation.label("quality_explanation"),
        )
        .where(ReferralConversion.partner_id == partner.id)
        .where(ReferralConversion.is_synthetic == False)  # noqa: E712
        .order_by(ReferralConversion.converted_at.desc())
    )

    rows = (await db.execute(stmt)).all()
    return [
        ConversionWithScoreResponse(
            id=conv.id,
            conversion_value=conv.conversion_value,
            attribution_model=conv.attribution_model,
            converted_at=conv.converted_at,
            quality_score=float(score) if score is not None else None,
            quality_explanation=explanation,
        )
        for conv, score, explanation in rows
    ]


@router.get("/links", response_model=list[ReferralLinkResponse])
async def list_referral_links(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_partner),
) -> list[ReferralLinkResponse]:
    """Return all referral links belonging to the authenticated partner."""
    service = ReferralLinkService(db)
    links = await service.list_for_partner(current_user.id)
    base_url = str(request.base_url)
    return [
        ReferralLinkResponse(
            id=link.id,
            partner_id=link.partner_id,
            slug=link.slug,
            referral_url=f"{base_url}r/{link.slug}",
            destination_url=link.destination_url,
            qr_code_data=link.qr_code_data,
            is_active=link.is_active,
            created_at=link.created_at,
        )
        for link in links
    ]


@router.get("/codes", response_model=list[ReferralCodeResponse])
async def list_referral_codes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_partner),
) -> list[ReferralCodeResponse]:
    """Return all referral codes belonging to the authenticated partner."""
    service = ReferralCodeService(db)
    codes = await service.list_for_partner(current_user.id)
    return [ReferralCodeResponse.model_validate(c) for c in codes]


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


@router.post(
    "/conversions",
    response_model=ConversionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_conversion(
    payload: ConversionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> ConversionResponse:
    """Record a referral conversion, attribute it to a click, and calculate commission."""
    service = ReferralConversionService(db)
    try:
        conversion = await service.record_conversion(payload, background_tasks)
    except ReferralCodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConversionPartnerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return ConversionResponse.model_validate(conversion)


@redirect_router.get("/r/{slug}", name="track_click")
async def track_click(
    slug: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    utm_source: Optional[str] = None,
) -> RedirectResponse:
    service = ReferralClickService(db)
    destination, click_id = await service.track(
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
    if click_id is not None:
        background_tasks.add_task(ai_service.score_fraud, db, click_id)
    return RedirectResponse(url=destination, status_code=302)
