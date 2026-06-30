# -----------------------------------------------------------------------------
# backend/app/services/partner_service.py
#
# Business logic for partner and tier management (PRT-001 through PRT-003).
# get_partner() enforces the access rule: admins can fetch any partner,
# partners can only fetch their own. get_own_partner() resolves a partner
# by the caller's user_id — needed because a partner's JWT only carries
# user_id (sub), not their partner_id, so the frontend can't call
# get_partner(partner_id) for "my own profile" without already knowing it.
# update_partner() splits allowed fields by role the same way.
# evaluate_tier_upgrade() is called after a commission is earned — it only
# upgrades, never downgrades, and assigns the highest qualifying tier by
# rank_order descending.
# -----------------------------------------------------------------------------

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner, PartnerTier
from app.repositories.partner_repository import PartnerRepository
from app.schemas.partner import AdminPartnerUpdateRequest, PartnerSelfUpdateRequest


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


class PartnerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PartnerRepository(session)

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

    async def list_partners(self) -> list[Partner]:
        result = await self.session.execute(
            select(Partner).order_by(Partner.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_partner_as_admin(
        self, partner_id: uuid.UUID, data: AdminPartnerUpdateRequest
    ) -> Partner:
        partner = await self.repo.get_by_id(partner_id)
        if partner is None:
            raise PartnerNotFoundError(partner_id)

        if data.tier_id is not None:
            tier = await self.repo.get_tier_by_id(data.tier_id)
            if tier is None:
                raise TierNotFoundError(data.tier_id)

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(partner, field, value)

        await self.session.flush()
        await self.session.commit()
        return partner

    async def update_partner_as_self(
        self, user_id: uuid.UUID, data: PartnerSelfUpdateRequest
    ) -> Partner:
        partner = await self.repo.get_by_user_id(user_id)
        if partner is None:
            raise PartnerNotFoundError(user_id)

        for field, value in data.model_dump(exclude_none=True).items():
            setattr(partner, field, value)

        await self.session.flush()
        await self.session.commit()
        return partner

    # ------------------------------------------------------------------ #
    # Tier CRUD (PRT-002)
    # ------------------------------------------------------------------ #

    async def list_tiers(self) -> list[PartnerTier]:
        result = await self.session.execute(
            select(PartnerTier).order_by(PartnerTier.rank_order)
        )
        return list(result.scalars().all())

    async def create_tier(
        self,
        name: str,
        rank_order: int,
        min_referral_count: int,
        min_revenue_contribution,
        commission_type: str,
        commission_value,
    ) -> PartnerTier:
        existing = await self.session.execute(
            select(PartnerTier).where(PartnerTier.rank_order == rank_order)
        )
        if existing.scalar_one_or_none() is not None:
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
        await self.session.commit()
        return tier

    async def update_tier(self, tier_id: uuid.UUID, data) -> PartnerTier:
        tier = await self.repo.get_tier_by_id(tier_id)
        if tier is None:
            raise TierNotFoundError(tier_id)

        updates = data.model_dump(exclude_none=True)
        if "rank_order" in updates:
            conflict = await self.session.execute(
                select(PartnerTier).where(
                    PartnerTier.rank_order == updates["rank_order"],
                    PartnerTier.id != tier_id,
                )
            )
            if conflict.scalar_one_or_none() is not None:
                raise TierRankConflictError(updates["rank_order"])

        for field, value in updates.items():
            setattr(tier, field, value)

        await self.session.flush()
        await self.session.commit()
        return tier

    async def delete_tier(self, tier_id: uuid.UUID) -> None:
        tier = await self.repo.get_tier_by_id(tier_id)
        if tier is None:
            raise TierNotFoundError(tier_id)
        await self.session.delete(tier)
        await self.session.commit()

    # ------------------------------------------------------------------ #
    # Automatic tier upgrade (PRT-003)
    # ------------------------------------------------------------------ #

    async def evaluate_tier_upgrade(self, partner_id: uuid.UUID) -> Optional[PartnerTier]:
        partner = await self.repo.get_by_id(partner_id)
        if partner is None:
            return None

        tiers_result = await self.session.execute(
            select(PartnerTier).order_by(PartnerTier.rank_order.desc())
        )
        tiers = list(tiers_result.scalars().all())

        for tier in tiers:
            qualifies = (
                partner.total_referral_count >= tier.min_referral_count
                and partner.total_revenue_contribution >= tier.min_revenue_contribution
            )
            if not qualifies:
                continue

            current_rank = 0
            if partner.tier_id:
                current_tier = await self.repo.get_tier_by_id(partner.tier_id)
                if current_tier:
                    current_rank = current_tier.rank_order

            if tier.rank_order > current_rank:
                partner.tier_id = tier.id
                await self.session.flush()
                await self.session.commit()
                return tier

            break

        return None
