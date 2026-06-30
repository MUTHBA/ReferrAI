# -----------------------------------------------------------------------------
# backend/app/services/commission_service.py
#
# Business logic for commission calculation (COM-001). calculate_for_conversion()
# resolves the correct commission rate in priority order: partner's current tier
# first, then the platform-wide defaults from the settings table. It flushes
# the Commission row but does NOT commit — COM-003 will call this alongside
# WalletService.credit() and commit both together atomically. Raises
# ConversionNotFoundError if the conversion_id doesn't exist, and
# DuplicateCommissionError if one has already been calculated for that
# conversion (idempotency guard).
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission import Commission
from app.repositories.commission_repository import CommissionRepository
from app.repositories.partner_repository import PartnerRepository
from app.repositories.referral_repository import ReferralRepository
from app.services.setting_service import SettingService


class ConversionNotFoundError(Exception):
    def __init__(self, conversion_id: uuid.UUID) -> None:
        super().__init__(f"ReferralConversion {conversion_id} not found")
        self.conversion_id = conversion_id


class DuplicateCommissionError(Exception):
    def __init__(self, conversion_id: uuid.UUID) -> None:
        super().__init__(f"Commission already calculated for conversion {conversion_id}")
        self.conversion_id = conversion_id


class CommissionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.commission_repo = CommissionRepository(session)
        self.referral_repo = ReferralRepository(session)
        self.partner_repo = PartnerRepository(session)
        self.setting_service = SettingService(session)

    async def calculate_for_conversion(self, conversion_id: uuid.UUID) -> Commission:
        if await self.commission_repo.get_by_conversion_id(conversion_id):
            raise DuplicateCommissionError(conversion_id)

        conversion = await self.referral_repo.get_conversion_by_id(conversion_id)
        if conversion is None:
            raise ConversionNotFoundError(conversion_id)

        partner = await self.partner_repo.get_by_id(conversion.partner_id)
        tier_id: uuid.UUID | None = None

        if partner and partner.tier_id:
            tier = await self.partner_repo.get_tier_by_id(partner.tier_id)
            if tier:
                commission_type = tier.commission_type
                rate = tier.commission_value
                tier_id = tier.id
            else:
                commission_type, rate = await self._default_type_and_rate()
        else:
            commission_type, rate = await self._default_type_and_rate()

        amount = self._calculate_amount(commission_type, rate, conversion.conversion_value)

        commission = Commission(
            id=uuid.uuid4(),
            partner_id=conversion.partner_id,
            conversion_id=conversion_id,
            amount=amount,
            commission_type=commission_type,
            tier_id=tier_id,
            status="approved",
        )
        return await self.commission_repo.create(commission)

    async def _default_type_and_rate(self) -> tuple[str, Decimal]:
        commission_type = await self.setting_service.get(
            "commission.default_type", "percentage"
        )
        if commission_type == "fixed":
            rate = Decimal(
                str(await self.setting_service.get("commission.default_fixed_amount", 10.0))
            )
        else:
            commission_type = "percentage"
            rate = Decimal(
                str(await self.setting_service.get("commission.default_percentage", 0.10))
            )
        return commission_type, rate

    @staticmethod
    def _calculate_amount(
        commission_type: str, rate: Decimal, conversion_value: Decimal
    ) -> Decimal:
        if commission_type == "fixed":
            return rate.quantize(Decimal("0.01"))
        # percentage and tier_based both multiply the rate against conversion_value
        return (conversion_value * rate).quantize(Decimal("0.01"))
