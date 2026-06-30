# -----------------------------------------------------------------------------
# backend/app/services/dashboard_service.py
#
# Aggregate query layer for RPT-001 (admin dashboard), RPT-002 (partner
# dashboard), and RPT-003 (CSV exports). All queries exclude is_synthetic
# records per CLAUDE.md — dashboards must never surface AI training data.
# AI score fields (quality, churn, rank) return None until Phase 4 scoring
# runs have been executed. CSV helpers return plain dicts for easy csv.DictWriter
# consumption — no ORM model serialisation needed there.
# -----------------------------------------------------------------------------

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_score import AIScore
from app.models.commission import Commission
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner
from app.models.referral import ReferralClick, ReferralCode, ReferralConversion, ReferralLink
from app.models.wallet import Wallet, Withdrawal
from app.repositories.partner_repository import PartnerRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.dashboard import (
    AdminDashboardResponse,
    AdminKPIs,
    PartnerDashboardResponse,
    PartnerKPIs,
    VolumeDataPoint,
)


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    # Admin dashboard (RPT-001)
    # ------------------------------------------------------------------ #

    async def get_admin_dashboard(self, days: int = 30) -> AdminDashboardResponse:
        kpis = await self._admin_kpis()
        chart = await self._volume_chart(days)
        return AdminDashboardResponse(kpis=kpis, volume_chart=chart)

    async def _admin_kpis(self) -> AdminKPIs:
        total_conversions = await self.session.scalar(
            select(func.count()).select_from(ReferralConversion)
            .where(ReferralConversion.is_synthetic.is_(False))
        ) or 0

        active_partners = await self.session.scalar(
            select(func.count()).select_from(Partner)
            .where(Partner.status == "active", Partner.is_synthetic.is_(False))
        ) or 0

        total_commission = await self.session.scalar(
            select(func.coalesce(func.sum(Commission.amount), Decimal("0")))
            .where(Commission.status == "approved")
        ) or Decimal("0")

        pending_payout_row = await self.session.execute(
            select(
                func.count().label("cnt"),
                func.coalesce(func.sum(Withdrawal.amount), Decimal("0")).label("total"),
            ).where(Withdrawal.status == "pending")
        )
        payout_row = pending_payout_row.one()

        fraud_alert_count = await self.session.scalar(
            select(func.count()).select_from(FraudFlag)
            .where(FraudFlag.status == "pending_review")
        ) or 0

        return AdminKPIs(
            total_conversions=total_conversions,
            active_partners=active_partners,
            total_commission=Decimal(str(total_commission)),
            pending_payout_count=payout_row.cnt,
            pending_payout_amount=Decimal(str(payout_row.total)),
            fraud_alert_count=fraud_alert_count,
            churn_alert_count=0,  # placeholder until AI-CHURN-002
        )

    async def _volume_chart(self, days: int) -> list[VolumeDataPoint]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        click_rows = await self.session.execute(
            select(
                cast(ReferralClick.clicked_at, Date).label("day"),
                func.count().label("clicks"),
            )
            .where(
                ReferralClick.clicked_at >= cutoff,
                ReferralClick.is_synthetic.is_(False),
            )
            .group_by(cast(ReferralClick.clicked_at, Date))
        )
        click_by_day = {row.day: row.clicks for row in click_rows}

        conv_rows = await self.session.execute(
            select(
                cast(ReferralConversion.converted_at, Date).label("day"),
                func.count().label("conversions"),
            )
            .where(
                ReferralConversion.converted_at >= cutoff,
                ReferralConversion.is_synthetic.is_(False),
            )
            .group_by(cast(ReferralConversion.converted_at, Date))
        )
        conv_by_day = {row.day: row.conversions for row in conv_rows}

        today = date.today()
        result = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            result.append(VolumeDataPoint(
                date=d,
                clicks=click_by_day.get(d, 0),
                conversions=conv_by_day.get(d, 0),
            ))
        return result

    # ------------------------------------------------------------------ #
    # Partner dashboard (RPT-002)
    # ------------------------------------------------------------------ #

    async def get_partner_dashboard(self, user_id: uuid.UUID) -> PartnerDashboardResponse:
        partner = await PartnerRepository(self.session).get_by_user_id(user_id)
        if partner is None:
            return PartnerDashboardResponse(
                kpis=PartnerKPIs(
                    referral_count=0, conversion_count=0,
                    total_earnings=Decimal("0"), wallet_balance=Decimal("0"),
                )
            )

        link_count = await self.session.scalar(
            select(func.count()).select_from(ReferralLink)
            .where(ReferralLink.partner_id == partner.id)
        ) or 0

        code_count = await self.session.scalar(
            select(func.count()).select_from(ReferralCode)
            .where(ReferralCode.partner_id == partner.id)
        ) or 0

        conversion_count = await self.session.scalar(
            select(func.count()).select_from(ReferralConversion)
            .where(
                ReferralConversion.partner_id == partner.id,
                ReferralConversion.is_synthetic.is_(False),
            )
        ) or 0

        wallet = await WalletRepository(self.session).get_by_partner_id(partner.id)
        balance = wallet.balance if wallet else Decimal("0")
        total_earned = wallet.total_earned if wallet else Decimal("0")

        quality_score = await self._latest_score(partner.id, "quality")
        churn_score = await self._latest_score(partner.id, "churn_risk")
        rank_score = await self._latest_score(partner.id, "ranking")

        return PartnerDashboardResponse(
            kpis=PartnerKPIs(
                referral_count=link_count + code_count,
                conversion_count=conversion_count,
                total_earnings=total_earned,
                wallet_balance=balance,
            ),
            quality_score=quality_score,
            churn_score=churn_score,
            rank_score=rank_score,
        )

    async def _latest_score(
        self, partner_id: uuid.UUID, score_type: str
    ) -> Optional[Decimal]:
        result = await self.session.scalar(
            select(AIScore.score)
            .where(
                AIScore.entity_type == "partner",
                AIScore.entity_id == partner_id,
                AIScore.score_type == score_type,
                AIScore.is_synthetic.is_(False),
            )
            .order_by(AIScore.calculated_at.desc())
            .limit(1)
        )
        return Decimal(str(result)) if result is not None else None

    # ------------------------------------------------------------------ #
    # CSV export helpers (RPT-003)
    # ------------------------------------------------------------------ #

    async def get_referrals_csv_data(self) -> list[dict]:
        rows = await self.session.execute(
            select(ReferralConversion).where(ReferralConversion.is_synthetic.is_(False))
            .order_by(ReferralConversion.converted_at.desc())
        )
        return [
            {
                "id": str(r.id),
                "partner_id": str(r.partner_id),
                "click_id": str(r.click_id) if r.click_id else "",
                "referral_code_id": str(r.referral_code_id) if r.referral_code_id else "",
                "conversion_value": str(r.conversion_value),
                "attribution_model": r.attribution_model,
                "converted_at": r.converted_at.isoformat(),
            }
            for r in rows.scalars().all()
        ]

    async def get_commissions_csv_data(self) -> list[dict]:
        rows = await self.session.execute(
            select(Commission).order_by(Commission.calculated_at.desc())
        )
        return [
            {
                "id": str(c.id),
                "partner_id": str(c.partner_id),
                "conversion_id": str(c.conversion_id),
                "amount": str(c.amount),
                "commission_type": c.commission_type,
                "tier_id": str(c.tier_id) if c.tier_id else "",
                "status": c.status,
                "calculated_at": c.calculated_at.isoformat(),
            }
            for c in rows.scalars().all()
        ]

    async def get_partners_csv_data(self) -> list[dict]:
        rows = await self.session.execute(
            select(Partner).where(Partner.is_synthetic.is_(False))
            .order_by(Partner.created_at.desc())
        )
        return [
            {
                "id": str(p.id),
                "name": p.name,
                "email": p.email,
                "status": p.status,
                "tier_id": str(p.tier_id) if p.tier_id else "",
                "total_referral_count": str(p.total_referral_count),
                "total_revenue_contribution": str(p.total_revenue_contribution),
                "created_at": p.created_at.isoformat(),
            }
            for p in rows.scalars().all()
        ]
