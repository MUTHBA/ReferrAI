# -----------------------------------------------------------------------------
# backend/app/api/v1/routes/referrals.py
#
# Referral endpoints. Partners: list/create links and codes (creation needs an
# ACTIVE partner), list their conversions with AI quality scores. Admins:
# record a conversion (POST /referrals/conversions), which triggers
# attribution, commission, wallet credit and tier evaluation in one
# transaction. Public: GET /r/{slug} tracks a click and redirects; fraud
# scoring runs afterwards as a background task in its own DB session.
# Change: POST /conversions requires click_id or referral_code (422 otherwise) and never trusts a caller partner_id - week-11 hardening merged.
# -----------------------------------------------------------------------------

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import client_ip, get_current_partner, require_active_partner, require_admin
from app.models.partner import Partner
from app.models.referral import ReferralLink
from app.models.user import User
from app.schemas.referral import ReferralCodeResponse, ReferralLinkCreateRequest, ReferralLinkResponse
from app.schemas.referral_conversion import (
    ConversionCreate,
    ConversionResponse,
    ConversionWithScoreResponse,
)
from app.services import ai_service
from app.services.referral_click_service import ReferralClickService
from app.services.referral_code_service import ReferralCodeService
from app.services.referral_conversion_service import (
    ConversionClickNotFoundError,
    ConversionPartnerInactiveError,
    ConversionPartnerNotFoundError,
    DuplicateConversionError,
    ReferralCodeNotFoundError,
    ReferralConversionService,
)
from app.services.referral_link_service import ReferralLinkService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/referrals", tags=["referrals"])
redirect_router = APIRouter(tags=["referrals"])  # public /r/{slug}, no /api/v1 prefix


def conversion_rows_to_response(rows) -> list[ConversionWithScoreResponse]:
    """Shape repository rows for the partner (and admin partner-detail) views."""
    out = []
    for conv, score, q_status, explanation, factors, commission, click in rows:
        device = (click.device_info or {}).get("device_type") if click is not None else None
        out.append(
            ConversionWithScoreResponse(
                id=conv.id,
                external_reference=conv.external_reference,
                conversion_value=conv.conversion_value,
                attribution_model=conv.attribution_model,
                converted_at=conv.converted_at,
                quality_score=float(score) if score is not None else None,
                quality_status=q_status,
                quality_explanation=explanation,
                quality_factors=(factors or {}).get("top_factors") if isinstance(factors, dict) else None,
                commission_amount=commission.amount if commission is not None else None,
                commission_type=commission.commission_type if commission is not None else None,
                commission_status=commission.status if commission is not None else None,
                source=click.source if click is not None else None,
                device_type=device,
                clicked_at=click.clicked_at if click is not None else None,
                via_code=conv.referral_code_id is not None,
            )
        )
    return out


def _link_response(link: ReferralLink, base_url: str, clicks: int = 0, conversions: int = 0) -> ReferralLinkResponse:
    return ReferralLinkResponse(
        id=link.id,
        partner_id=link.partner_id,
        slug=link.slug,
        referral_url=f"{base_url}r/{link.slug}",
        destination_url=link.destination_url,
        qr_code_data=link.qr_code_data,
        is_active=link.is_active,
        created_at=link.created_at,
        click_count=clicks,
        conversion_count=conversions,
    )


@router.get("/conversions", response_model=list[ConversionWithScoreResponse])
async def list_my_conversions(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    partner: Partner = Depends(get_current_partner),
) -> list[ConversionWithScoreResponse]:
    rows = await ReferralConversionService(db).list_for_partner_with_quality(partner.id, limit, offset)
    return conversion_rows_to_response(rows)


@router.get("/links", response_model=list[ReferralLinkResponse])
async def list_referral_links(
    request: Request,
    db: AsyncSession = Depends(get_db),
    partner: Partner = Depends(get_current_partner),
) -> list[ReferralLinkResponse]:
    links = await ReferralLinkService(db).list_for_partner(partner.id)
    counts = await ReferralConversionService(db).usage_counts(partner.id)
    return [
        _link_response(
            link,
            str(request.base_url),
            counts["link_clicks"].get(link.id, 0),
            counts["link_conversions"].get(link.id, 0),
        )
        for link in links
    ]


@router.get("/codes", response_model=list[ReferralCodeResponse])
async def list_referral_codes(
    db: AsyncSession = Depends(get_db),
    partner: Partner = Depends(get_current_partner),
) -> list[ReferralCodeResponse]:
    codes = await ReferralCodeService(db).list_for_partner(partner.id)
    counts = await ReferralConversionService(db).usage_counts(partner.id)
    return [
        ReferralCodeResponse.model_validate(c).model_copy(
            update={"conversion_count": counts["code_conversions"].get(c.id, 0)}
        )
        for c in codes
    ]


@router.post("/links", response_model=ReferralLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_referral_link(
    payload: ReferralLinkCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    partner: Partner = Depends(require_active_partner),
) -> ReferralLinkResponse:
    link = await ReferralLinkService(db).create(
        partner=partner, destination_url=payload.destination_url, base_url=str(request.base_url)
    )
    return _link_response(link, str(request.base_url))


@router.post("/codes", response_model=ReferralCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_referral_code(
    db: AsyncSession = Depends(get_db),
    partner: Partner = Depends(require_active_partner),
) -> ReferralCodeResponse:
    code = await ReferralCodeService(db).create(partner)
    return ReferralCodeResponse.model_validate(code)


@router.post("/conversions", response_model=ConversionResponse, status_code=status.HTTP_201_CREATED)
async def record_conversion(
    payload: ConversionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> ConversionResponse:
    # The partner is always derived from the click or code (never the caller).
    if payload.click_id is None and not payload.referral_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either click_id or referral_code is required",
        )
    payload.partner_id = None
    try:
        conversion = await ReferralConversionService(db).record_conversion(payload, background_tasks)
    except DuplicateConversionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except (ReferralCodeNotFoundError, ConversionClickNotFoundError, ConversionPartnerNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ConversionPartnerInactiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return ConversionResponse.model_validate(conversion)


@redirect_router.get("/r/{slug}", name="track_click")
async def track_click(
    slug: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    utm_source: Optional[str] = None,
) -> RedirectResponse:
    destination, click_id = await ReferralClickService(db).track(
        slug=slug,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        utm_source=utm_source,
    )
    if destination is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral link not found or inactive")
    if click_id is not None:
        background_tasks.add_task(ai_service.run_in_new_session, ai_service.score_fraud, click_id)
    return RedirectResponse(url=destination, status_code=302)
