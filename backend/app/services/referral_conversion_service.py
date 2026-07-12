# -----------------------------------------------------------------------------
# backend/app/services/referral_conversion_service.py
#
# Orchestrates the full conversion recording flow: code resolution, attribution,
# conversion insert, commission calculation, wallet credit, partner counter
# increment, and automatic tier evaluation — all flushed and committed in one
# transaction.
# CommissionService.calculate_for_conversion() and WalletService.credit() both
# flush without committing so they can be composed here with a single commit.
# PartnerService.evaluate_tier_upgrade() is called after counters are flushed
# so it reads the updated totals (PRT-003). It commits internally when a tier
# upgrade occurs; the outer commit is a no-op in that case.
# AI quality scoring is dispatched as a FastAPI background task after commit.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import ReferralConversion
from app.repositories.partner_repository import PartnerRepository
from app.repositories.referral_code_repository import ReferralCodeRepository
from app.repositories.referral_conversion_repository import ReferralConversionRepository
from app.schemas.referral_conversion import ConversionCreate
from app.services import ai_service
from app.services.attribution_service import AttributionService
from app.services.commission_service import CommissionService
from app.services.partner_service import PartnerService
from app.services.setting_service import SettingService
from app.services.wallet_service import WalletService


class ReferralCodeNotFoundError(Exception):
    """Raised when the submitted referral code does not exist or is inactive."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Referral code '{code}' not found or inactive")
        self.code = code


class ConversionPartnerNotFoundError(Exception):
    """Raised when partner_id on the conversion payload does not exist."""

    def __init__(self, partner_id: uuid.UUID) -> None:
        super().__init__(f"Partner {partner_id} not found")
        self.partner_id = partner_id


class ReferralConversionService:
    """Records a referral conversion and triggers downstream commission calculation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_conversion(
        self,
        data: ConversionCreate,
        background_tasks: BackgroundTasks,
    ) -> ReferralConversion:
        """Record a conversion, calculate commission, credit wallet, update counters.

        All writes are flushed individually but committed together so the
        transaction is all-or-nothing.
        """
        # 1. Resolve referral_code string → ReferralCode UUID if provided.
        referral_code_id: uuid.UUID | None = None
        if data.referral_code:
            code_row = await ReferralCodeRepository(self.session).get_by_code(
                data.referral_code
            )
            if code_row is None or not code_row.is_active:
                raise ReferralCodeNotFoundError(data.referral_code)
            referral_code_id = code_row.id

        # 2. Attribute the conversion to a click via the configured model + window.
        attributed_click = await AttributionService(self.session).attribute_conversion(
            partner_id=data.partner_id,
            referral_code_id=referral_code_id,
            click_id=data.click_id,
        )

        # 3. Read attribution model for storage on the conversion row.
        attribution_model: str = await SettingService(self.session).get(
            "referral.attribution_model", "last_click"
        )

        # 4. Insert the conversion row (flush, not commit).
        conversion = ReferralConversion(
            id=uuid.uuid4(),
            partner_id=data.partner_id,
            click_id=attributed_click.id if attributed_click else None,
            referral_link_id=attributed_click.referral_link_id if attributed_click else None,
            referral_code_id=referral_code_id,
            conversion_value=data.conversion_value,
            attribution_model=attribution_model,
            is_synthetic=False,
        )
        await ReferralConversionRepository(self.session).create(conversion)

        # 5. Calculate commission (flushes commission row, does not commit).
        commission = await CommissionService(self.session).calculate_for_conversion(
            conversion.id
        )

        # 6. Credit the partner's wallet with the commission amount (flushes, no commit).
        await WalletService(self.session).credit(
            partner_id=data.partner_id,
            amount=commission.amount,
            reference_id=conversion.id,
        )

        # 7. Increment denormalised partner counters in the same transaction.
        partner = await PartnerRepository(self.session).get_by_id(data.partner_id)
        if partner is None:
            raise ConversionPartnerNotFoundError(data.partner_id)
        partner.total_referral_count += 1
        partner.total_revenue_contribution = (
            partner.total_revenue_contribution + data.conversion_value
        )
        await self.session.flush()

        # 7b. Evaluate tier upgrade after counters are flushed so the updated
        # totals are visible to the query inside evaluate_tier_upgrade (PRT-003).
        # Only upgrades — never downgrades (enforced by rank_order comparison).
        # Commits internally when a tier changes; no-op return means no upgrade.
        await PartnerService(self.session).evaluate_tier_upgrade(data.partner_id)

        # 8. Commit: conversion + commission + wallet credit + counters atomically.
        # evaluate_tier_upgrade already committed when a tier upgrade occurred;
        # this commit handles the no-upgrade path.
        await self.session.commit()

        # 9. AI quality scoring runs after the response is sent (AI-QUAL-002).
        background_tasks.add_task(
            ai_service.score_referral_quality, self.session, conversion.id
        )

        return conversion
