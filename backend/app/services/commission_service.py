# -----------------------------------------------------------------------------
# backend/app/services/commission_service.py
#
# Commission calculation (COM-001) and commission administration.
#
# Rate resolution, in priority order:
#   1. the partner's current tier (commission_type + commission_value), then
#   2. the platform defaults from the settings table.
# Rates for 'percentage' and 'tier_based' are decimal fractions (0.10 = 10%)
# applied to conversion_value; 'fixed' is a flat currency amount. Amounts are
# rounded half-up to cents. calculate_for_conversion() flushes but never
# commits — ReferralConversionService commits it together with the wallet
# credit. reverse() claws back a commission (e.g. after confirmed fraud).
# -----------------------------------------------------------------------------

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Sequence

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission import Commission
from app.models.partner import Partner
from app.models.referral import ReferralConversion
from app.repositories.commission_repository import CommissionRepository
from app.repositories.partner_repository import PartnerRepository
from app.services.audit_log_service import AuditLogService
from app.services.setting_service import SettingService

CENT = Decimal("0.01")


class ConversionNotFoundError(Exception):
    def __init__(self, conversion_id: uuid.UUID) -> None:
        super().__init__(f"ReferralConversion {conversion_id} not found")
        self.conversion_id = conversion_id


class DuplicateCommissionError(Exception):
    def __init__(self, conversion_id: uuid.UUID) -> None:
        super().__init__(f"Commission already calculated for conversion {conversion_id}")
        self.conversion_id = conversion_id


class CommissionNotFoundError(Exception):
    def __init__(self, commission_id: uuid.UUID) -> None:
        super().__init__(f"Commission {commission_id} not found")


class CommissionNotReversibleError(Exception):
    def __init__(self, status: str) -> None:
        super().__init__(f"A commission with status '{status}' cannot be reversed")


class CommissionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.commission_repo = CommissionRepository(session)
        self.partner_repo = PartnerRepository(session)
        self.setting_service = SettingService(session)

    # ------------------------------------------------------------------ #
    # Calculation
    # ------------------------------------------------------------------ #
    async def calculate_for_conversion(
        self, conversion: ReferralConversion, partner: Optional[Partner] = None
    ) -> Commission:
        if await self.commission_repo.get_by_conversion_id(conversion.id):
            raise DuplicateCommissionError(conversion.id)

        if partner is None:
            partner = await self.partner_repo.get_by_id(conversion.partner_id)

        commission_type, rate, tier_id = await self._resolve_rate(partner)
        amount = self.calculate_amount(commission_type, rate, conversion.conversion_value)

        commission = Commission(
            id=uuid.uuid4(),
            partner_id=conversion.partner_id,
            conversion_id=conversion.id,
            amount=amount,
            commission_type=commission_type,
            tier_id=tier_id,
            status="approved",
        )
        return await self.commission_repo.create(commission)

    async def _resolve_rate(self, partner: Optional[Partner]) -> tuple[str, Decimal, Optional[uuid.UUID]]:
        if partner is not None and partner.tier_id:
            tier = await self.partner_repo.get_tier_by_id(partner.tier_id)
            if tier is not None:
                return tier.commission_type, Decimal(str(tier.commission_value)), tier.id

        commission_type = await self.setting_service.get("commission.default_type")
        if commission_type == "fixed":
            rate = await self.setting_service.get("commission.default_fixed_amount")
        else:
            commission_type = "percentage"
            rate = await self.setting_service.get("commission.default_percentage")
        return commission_type, Decimal(str(rate)), None

    @staticmethod
    def calculate_amount(commission_type: str, rate: Decimal, conversion_value: Decimal) -> Decimal:
        if commission_type == "fixed":
            return Decimal(rate).quantize(CENT, rounding=ROUND_HALF_UP)
        if commission_type in ("percentage", "tier_based"):
            # Both are a fraction of the order value; tier_based simply means the
            # fraction comes from the partner's tier rather than the defaults.
            return (Decimal(conversion_value) * Decimal(rate)).quantize(CENT, rounding=ROUND_HALF_UP)
        raise ValueError(f"Unknown commission type {commission_type!r}")

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #
    async def list_for_partner(
        self,
        partner_id: uuid.UUID,
        limit: int,
        offset: int,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[Sequence[Row], int]:
        return await self.commission_repo.list_with_conversion(
            partner_id=partner_id, status=status, limit=limit, offset=offset, search=search
        )

    async def list_all(
        self,
        status: Optional[str],
        limit: int,
        offset: int,
        search: Optional[str] = None,
        partner_id: Optional[uuid.UUID] = None,
    ) -> tuple[Sequence[Row], int]:
        return await self.commission_repo.list_with_conversion(
            partner_id=partner_id, status=status, limit=limit, offset=offset, search=search
        )

    async def sums_by_status(
        self, partner_id: Optional[uuid.UUID] = None, search: Optional[str] = None
    ) -> dict[str, Decimal]:
        return await self.commission_repo.sums_by_status(partner_id, search)

    # ------------------------------------------------------------------ #
    # Reversal (admin)
    # ------------------------------------------------------------------ #
    async def reverse(
        self,
        commission_id: uuid.UUID,
        admin_id: uuid.UUID,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Commission:
        # Imported here to avoid a circular import (wallet -> settings -> ...).
        from app.services.wallet_service import WalletService

        commission = await self.commission_repo.get_by_id(commission_id, for_update=True)
        if commission is None:
            raise CommissionNotFoundError(commission_id)
        if commission.status not in ("approved", "pending"):
            raise CommissionNotReversibleError(commission.status)

        await WalletService(self.session).debit(
            commission.partner_id, commission.amount, commission.id, "commission_reversal"
        )
        old_status = commission.status
        commission.status = "reversed"
        await self.session.flush()

        await AuditLogService(self.session).log(
            user_id=admin_id,
            action="commission.reversed",
            entity_type="commission",
            entity_id=commission.id,
            old_value={"status": old_status},
            new_value={"status": "reversed", "amount": commission.amount, "reason": reason},
            ip_address=ip_address,
        )
        await self.session.commit()
        return commission
