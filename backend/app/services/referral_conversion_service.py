# -----------------------------------------------------------------------------
# backend/app/services/referral_conversion_service.py
#
# Records a referral conversion and everything that follows from it, in ONE
# database transaction (all-or-nothing):
#   0. lock the partner row and check it exists and is active
#   1. idempotency: reject a repeated (partner_id, external_reference)
#   2. resolve the referral code (must be active AND belong to this partner)
#   3. attribute the conversion to a click (first/last-click, window)
#   4. insert the conversion
#   5. calculate the commission (tier rate or settings defaults)
#   6. credit the wallet (ledger row references the commission)
#   7. update the partner's denormalised counters
#   8. evaluate a tier upgrade (applies to FUTURE conversions only)
# After commit, AI quality scoring is scheduled as a background task that
# opens its own database session; it can never block or roll back the above.
# -----------------------------------------------------------------------------

import uuid

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
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
from app.services.wallet_service import WalletService


class ReferralCodeNotFoundError(Exception):
    """The submitted referral code does not exist, is inactive, or belongs to another partner."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Referral code '{code}' not found or inactive for this partner")
        self.code = code


class ConversionPartnerNotFoundError(Exception):
    def __init__(self, partner_id: uuid.UUID) -> None:
        super().__init__(f"Partner {partner_id} not found")
        self.partner_id = partner_id


class ConversionPartnerInactiveError(Exception):
    def __init__(self, partner_id: uuid.UUID, status: str) -> None:
        super().__init__(f"Partner {partner_id} is {status}; conversions cannot be credited")
        self.partner_id = partner_id


class DuplicateConversionError(Exception):
    """A conversion with the same partner_id + external_reference already exists (HTTP 409)."""

    def __init__(self, partner_id: uuid.UUID, external_reference: str) -> None:
        super().__init__(
            f"Conversion for partner {partner_id} with reference '{external_reference}' already exists"
        )
        self.partner_id = partner_id
        self.external_reference = external_reference


class ReferralConversionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversion_repo = ReferralConversionRepository(session)

    async def record_conversion(
        self,
        data: ConversionCreate,
        background_tasks: BackgroundTasks,
    ) -> ReferralConversion:
        try:
            conversion = await self._record(data)
        except IntegrityError as exc:
            # Lost a race with an identical concurrent request: the unique
            # (partner_id, external_reference) constraint fired.
            await self.session.rollback()
            if "external_ref" in str(exc.orig):
                raise DuplicateConversionError(data.partner_id, data.external_reference) from exc
            raise
        except Exception:
            await self.session.rollback()
            raise

        background_tasks.add_task(
            ai_service.run_in_new_session, ai_service.score_referral_quality, conversion.id
        )
        return conversion

    async def _record(self, data: ConversionCreate) -> ReferralConversion:
        # 0. Partner must exist and be active. Row lock serialises counter updates.
        partner = await PartnerRepository(self.session).get_by_id(data.partner_id, for_update=True)
        if partner is None:
            raise ConversionPartnerNotFoundError(data.partner_id)
        if partner.status != "active":
            raise ConversionPartnerInactiveError(data.partner_id, partner.status)

        # 1. Idempotency.
        if await self.conversion_repo.get_by_partner_and_reference(data.partner_id, data.external_reference):
            raise DuplicateConversionError(data.partner_id, data.external_reference)

        # 2. Referral code must be active and owned by this partner.
        referral_code_id: uuid.UUID | None = None
        if data.referral_code:
            code_row = await ReferralCodeRepository(self.session).get_by_code(data.referral_code)
            if code_row is None or not code_row.is_active or code_row.partner_id != partner.id:
                raise ReferralCodeNotFoundError(data.referral_code)
            referral_code_id = code_row.id

        # 3. Attribution.
        click, model = await AttributionService(self.session).attribute_conversion(
            partner_id=partner.id, referral_code_id=referral_code_id, click_id=data.click_id
        )

        # 4. Conversion row.
        conversion = ReferralConversion(
            id=uuid.uuid4(),
            partner_id=partner.id,
            external_reference=data.external_reference,
            click_id=click.id if click else None,
            referral_link_id=click.referral_link_id if click else None,
            referral_code_id=referral_code_id,
            conversion_value=data.conversion_value,
            attribution_model=model,
            is_synthetic=False,
        )
        await self.conversion_repo.create(conversion)

        # 5-6. Commission at the partner's CURRENT tier, then wallet credit.
        commission = await CommissionService(self.session).calculate_for_conversion(conversion, partner)
        await WalletService(self.session).credit(
            partner_id=partner.id,
            amount=commission.amount,
            reference_id=commission.id,
            reference_type="commission",
        )

        # 7. Counters.
        partner.total_referral_count += 1
        partner.total_revenue_contribution = partner.total_revenue_contribution + data.conversion_value
        await self.session.flush()

        # 8. Tier upgrade (not retroactive: this conversion was already priced above).
        await PartnerService(self.session).evaluate_tier_upgrade(partner)

        await self.session.commit()
        return conversion

    async def usage_counts(self, partner_id: uuid.UUID):
        return await self.conversion_repo.usage_counts(partner_id)

    async def list_for_partner_with_quality(self, partner_id: uuid.UUID, limit: int = 200, offset: int = 0):
        return await self.conversion_repo.list_for_partner_with_quality(partner_id, limit, offset)
