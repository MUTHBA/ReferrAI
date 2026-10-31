# -----------------------------------------------------------------------------
# backend/app/services/partner_service.py
#
# Partner profiles (PRT-001), tier CRUD (PRT-002) and automatic tier upgrades
# (PRT-003). Admin-facing lists exclude synthetic partners and are enriched
# with each partner's latest AI scores (churn, fraud, ranking) and average
# conversion quality. Every admin mutation writes an audit_logs row.
#
# evaluate_tier_upgrade() only FLUSHES — it runs inside the conversion
# transaction, which commits once. Upgrades are never retroactive: the
# conversion that triggers an upgrade has already been priced at the old tier.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commission import Commission
from app.models.partner import Partner, PartnerTier
from app.repositories.ai_score_repository import AIScoreRepository
from app.repositories.partner_repository import PartnerRepository
from app.schemas.partner import AdminPartnerUpdateRequest, PartnerSelfUpdateRequest
from app.services.audit_log_service import AuditLogService


class PartnerNotFoundError(Exception):
    def __init__(self, partner_id: uuid.UUID) -> None:
        super().__init__(f"Partner {partner_id} not found")


class AccessDeniedError(Exception):
    pass


class TierNotFoundError(Exception):
    def __init__(self, tier_id: uuid.UUID) -> None:
        super().__init__(f"Tier {tier_id} not found")


class TierRankConflictError(Exception):
    def __init__(self, rank_order: int) -> None:
        super().__init__(f"rank_order {rank_order} is already in use")


class TierInUseError(Exception):
    def __init__(self, tier_id: uuid.UUID, partners: int) -> None:
        super().__init__(
            f"Tier {tier_id} is assigned to {partners} partner(s) or referenced by commissions; "
            "move them to another tier first"
        )


class InvalidTierRateError(Exception):
    pass


class PartnerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PartnerRepository(session)
        self.scores = AIScoreRepository(session)

    # ------------------------------------------------------------------ #
    # Partner profile (PRT-001)
    # ------------------------------------------------------------------ #
    async def get_partner(
        self, partner_id: uuid.UUID, requesting_user_id: uuid.UUID, requesting_role: str
    ) -> Partner:
        partner = await self.repo.get_by_id(partner_id)
        if partner is None:
            raise PartnerNotFoundError(partner_id)
        if requesting_role != "admin" and partner.user_id != requesting_user_id:
            raise AccessDeniedError
        return partner

    async def get_own_partner(self, user_id: uuid.UUID) -> Partner:
        partner = await self.repo.get_by_user_id(user_id)
        if partner is None:
            raise PartnerNotFoundError(user_id)
        return partner

    async def list_partners(
        self, search: Optional[str] = None, status: Optional[str] = None
    ) -> list[Partner]:
        stmt = select(Partner).where(Partner.is_synthetic == False)  # noqa: E712
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Partner.name).like(like),
                    func.lower(Partner.email).like(like),
                    func.lower(func.coalesce(Partner.business_name, "")).like(like),
                )
            )
        if status:
            stmt = stmt.where(Partner.status == status)
        result = await self.session.execute(stmt.order_by(Partner.created_at.desc()))
        return list(result.scalars().all())

    async def score_maps(self) -> dict[str, dict[uuid.UUID, Optional[float]]]:
        """Latest partner-level scores, keyed by score name, for list enrichment."""
        return {
            "rank_score": await self.scores.latest_by_entity("ranking"),
            "churn_score": await self.scores.latest_by_entity("churn_risk"),
            "fraud_score": await self.scores.latest_by_entity("fraud_risk"),
            "quality_score": await self.scores.partner_quality_averages(),
        }

    async def get_latest_score_by_partner(self, score_type: str) -> dict[uuid.UUID, Optional[float]]:
        return await self.scores.latest_by_entity(score_type)

    async def tier_names(self) -> dict[uuid.UUID, str]:
        return {t.id: t.name for t in await self.list_tiers()}

    async def update_partner_as_admin(
        self,
        partner_id: uuid.UUID,
        data: AdminPartnerUpdateRequest,
        admin_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
    ) -> Partner:
        partner = await self.repo.get_by_id(partner_id)
        if partner is None:
            raise PartnerNotFoundError(partner_id)
        if data.tier_id is not None and await self.repo.get_tier_by_id(data.tier_id) is None:
            raise TierNotFoundError(data.tier_id)

        changes = data.model_dump(exclude_none=True)
        old = {k: getattr(partner, k) for k in changes}
        for field, value in changes.items():
            setattr(partner, field, value)
        await self.session.flush()

        if changes:
            action = "partner.status_changed" if "status" in changes else "partner.updated"
            await AuditLogService(self.session).log(
                user_id=admin_id,
                action=action,
                entity_type="partner",
                entity_id=partner.id,
                old_value=old,
                new_value=changes,
                ip_address=ip_address,
            )
        await self.session.commit()
        return partner

    async def update_partner_as_self(self, user_id: uuid.UUID, data: PartnerSelfUpdateRequest) -> Partner:
        partner = await self.repo.get_by_user_id(user_id)
        if partner is None:
            raise PartnerNotFoundError(user_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(partner, field, value)
        await self.session.commit()
        return partner

    # ------------------------------------------------------------------ #
    # Tier CRUD (PRT-002)
    # ------------------------------------------------------------------ #
    async def list_tiers(self) -> list[PartnerTier]:
        result = await self.session.execute(select(PartnerTier).order_by(PartnerTier.rank_order))
        return list(result.scalars().all())

    async def _rank_taken(self, rank_order: int, exclude_id: Optional[uuid.UUID] = None) -> bool:
        stmt = select(PartnerTier.id).where(PartnerTier.rank_order == rank_order)
        if exclude_id:
            stmt = stmt.where(PartnerTier.id != exclude_id)
        return (await self.session.execute(stmt)).first() is not None

    async def create_tier(
        self,
        name: str,
        rank_order: int,
        min_referral_count: int,
        min_revenue_contribution,
        commission_type: str,
        commission_value,
        admin_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
    ) -> PartnerTier:
        if await self._rank_taken(rank_order):
            raise TierRankConflictError(rank_order)

        tier = PartnerTier(
            id=uuid.uuid4(),
            name=name,
            rank_order=rank_order,
            min_referral_count=min_referral_count,
            min_revenue_contribution=min_revenue_contribution,
            commission_type=commission_type,
            commission_value=commission_value,
        )
        self.session.add(tier)
        await self.session.flush()
        await AuditLogService(self.session).log(
            user_id=admin_id,
            action="tier.created",
            entity_type="partner_tier",
            entity_id=tier.id,
            new_value={
                "name": name,
                "rank_order": rank_order,
                "commission_type": commission_type,
                "commission_value": commission_value,
            },
            ip_address=ip_address,
        )
        await self.session.commit()
        return tier

    async def update_tier(
        self, tier_id: uuid.UUID, data, admin_id: Optional[uuid.UUID] = None, ip_address: Optional[str] = None
    ) -> PartnerTier:
        tier = await self.repo.get_tier_by_id(tier_id)
        if tier is None:
            raise TierNotFoundError(tier_id)

        updates = data.model_dump(exclude_none=True)
        if "rank_order" in updates and await self._rank_taken(updates["rank_order"], tier_id):
            raise TierRankConflictError(updates["rank_order"])

        new_type = updates.get("commission_type", tier.commission_type)
        new_value = Decimal(str(updates.get("commission_value", tier.commission_value)))
        if new_type in ("percentage", "tier_based") and not (Decimal("0") < new_value <= Decimal("1")):
            raise InvalidTierRateError(
                "commission_value for percentage tiers must be a fraction between 0 and 1 (e.g. 0.10 for 10%)"
            )

        old = {k: getattr(tier, k) for k in updates}
        for field, value in updates.items():
            setattr(tier, field, value)
        await self.session.flush()
        await AuditLogService(self.session).log(
            user_id=admin_id,
            action="tier.updated",
            entity_type="partner_tier",
            entity_id=tier.id,
            old_value=old,
            new_value=updates,
            ip_address=ip_address,
        )
        await self.session.commit()
        return tier

    async def delete_tier(
        self, tier_id: uuid.UUID, admin_id: Optional[uuid.UUID] = None, ip_address: Optional[str] = None
    ) -> None:
        tier = await self.repo.get_tier_by_id(tier_id)
        if tier is None:
            raise TierNotFoundError(tier_id)

        partners = (
            await self.session.execute(select(func.count()).where(Partner.tier_id == tier_id))
        ).scalar_one()
        commissions = (
            await self.session.execute(select(func.count()).where(Commission.tier_id == tier_id))
        ).scalar_one()
        if partners or commissions:
            raise TierInUseError(tier_id, int(partners))

        await AuditLogService(self.session).log(
            user_id=admin_id,
            action="tier.deleted",
            entity_type="partner_tier",
            entity_id=tier.id,
            old_value={"name": tier.name, "rank_order": tier.rank_order},
            ip_address=ip_address,
        )
        await self.session.delete(tier)
        await self.session.commit()

    # ------------------------------------------------------------------ #
    # Automatic tier upgrade (PRT-003)
    # ------------------------------------------------------------------ #
    async def evaluate_tier_upgrade(self, partner: Partner) -> Optional[PartnerTier]:
        """Move the partner to the highest tier they now qualify for, if it is
        above their current tier. Never downgrades. Flushes only."""
        tiers = await self.list_tiers()
        current_rank = 0
        if partner.tier_id:
            current = next((t for t in tiers if t.id == partner.tier_id), None)
            current_rank = current.rank_order if current else 0

        best: Optional[PartnerTier] = None
        for tier in tiers:  # ascending rank_order
            if (
                partner.total_referral_count >= tier.min_referral_count
                and partner.total_revenue_contribution >= tier.min_revenue_contribution
            ):
                best = tier
        if best is None or best.rank_order <= current_rank:
            return None

        old_tier_id = partner.tier_id
        partner.tier_id = best.id
        await self.session.flush()
        await AuditLogService(self.session).log(
            user_id=None,
            action="partner.tier_upgraded",
            entity_type="partner",
            entity_id=partner.id,
            old_value={"tier_id": old_tier_id},
            new_value={"tier_id": best.id, "tier_name": best.name},
        )
        return best
