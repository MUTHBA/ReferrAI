# -----------------------------------------------------------------------------
# backend/app/services/dashboard_service.py
#
# Aggregate query layer for RPT-001 (admin dashboard), RPT-002 (partner
# dashboard), and RPT-003 (CSV exports). All queries exclude is_synthetic
# records per CLAUDE.md — dashboards must never surface AI training data.
# AI score fields (quality, churn, rank) return None until Phase 4 scoring
# runs have been executed. CSV helpers return plain dicts for easy csv.DictWriter
# consumption — no ORM model serialisation needed there.
# Added rank_position + total_ranked_partners for AI-RANK-003: computes the
# partner's position in the latest ranking run so the UI can show "#X of Y".
# AI-CHURN-004: replaced churn_alert_count=0 placeholder with a real query;
# added _churn_at_risk_partners() and wired the result into AdminDashboardResponse.
# Threshold is read from the settings table (key: churn.alert_threshold,
# default: 70) so it can be tuned at runtime without a redeploy.
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
    ChurnAtRiskPartner,
    PartnerDashboardResponse,
    PartnerKPIs,
    VolumeDataPoint,
)
from app.services.setting_service import SettingService


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    # Admin dashboard (RPT-001)
    # ------------------------------------------------------------------ #

    async def get_admin_dashboard(self, days: int = 30) -> AdminDashboardResponse:
        churn_threshold = float(
            await SettingService(self.session).get("churn.alert_threshold", 70.0)
        )
        kpis = await self._admin_kpis(churn_threshold)
        chart = await self._volume_chart(days)
        at_risk = await self._churn_at_risk_partners(churn_threshold)
        return AdminDashboardResponse(kpis=kpis, volume_chart=chart, churn_at_risk_partners=at_risk)

    def _latest_score_subq(self, score_type: str):
        """Build a (entity_id, score) subquery for the latest score of *score_type*.

        Two-step: first find max(calculated_at) per entity, then join to get the
        score at that timestamp. Excludes synthetic rows.
        """
        ts_subq = (
            select(
                AIScore.entity_id,
                func.max(AIScore.calculated_at).label("max_at"),
            )
            .where(AIScore.score_type == score_type)
            .where(AIScore.is_synthetic.is_(False))
            .group_by(AIScore.entity_id)
            .subquery(f"latest_{score_type}_ts")
        )
        return (
            select(AIScore.entity_id.label("entity_id"), AIScore.score.label("score"))
            .join(
                ts_subq,
                (AIScore.entity_id == ts_subq.c.entity_id)
                & (AIScore.calculated_at == ts_subq.c.max_at),
            )
            .where(AIScore.score_type == score_type)
            .where(AIScore.is_synthetic.is_(False))
            .subquery(f"latest_{score_type}")
        )

    async def _admin_kpis(self, churn_threshold: float) -> AdminKPIs:
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

        churn_subq = self._latest_score_subq("churn_risk")
        churn_alert_count = await self.session.scalar(
            select(func.count())
            .select_from(churn_subq)
            .where(churn_subq.c.score > churn_threshold)
        ) or 0

        return AdminKPIs(
            total_conversions=total_conversions,
            active_partners=active_partners,
            total_commission=Decimal(str(total_commission)),
            pending_payout_count=payout_row.cnt,
            pending_payout_amount=Decimal(str(payout_row.total)),
            fraud_alert_count=fraud_alert_count,
            churn_alert_count=churn_alert_count,
        )

    async def _churn_at_risk_partners(self, threshold: float) -> list[ChurnAtRiskPartner]:
        churn_subq = self._latest_score_subq("churn_risk")
        rows = await self.session.execute(
            select(
                Partner.id.label("partner_id"),
                Partner.name.label("name"),
                churn_subq.c.score.label("churn_score"),
            )
            .join(churn_subq, Partner.id == churn_subq.c.entity_id)
            .where(Partner.is_synthetic.is_(False))
            .where(churn_subq.c.score > threshold)
            .order_by(churn_subq.c.score.desc())
        )
        return [
            ChurnAtRiskPartner(
                partner_id=row.partner_id,
                name=row.name,
                churn_score=float(row.churn_score),
            )
            for row in rows
        ]

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

        # Compute rank position: "#X of Y ranked partners" (AI-RANK-003)
        rank_position: Optional[int] = None
        total_ranked_partners: Optional[int] = None
        if rank_score is not None:
            # Subquery: latest ranking timestamp per partner
            latest_ts_subq = (
                select(
                    AIScore.entity_id,
                    func.max(AIScore.calculated_at).label("max_at"),
                )
                .where(AIScore.score_type == "ranking")
                .where(AIScore.is_synthetic.is_(False))
                .group_by(AIScore.entity_id)
                .subquery("latest_rank_ts")
            )
            # Join back to get the score at that timestamp
            latest_rank_subq = (
                select(AIScore.entity_id, AIScore.score.label("ranking_score"))
                .join(
                    latest_ts_subq,
                    (AIScore.entity_id == latest_ts_subq.c.entity_id)
                    & (AIScore.calculated_at == latest_ts_subq.c.max_at),
                )
                .where(AIScore.score_type == "ranking")
                .subquery("latest_rank")
            )
            total_ranked_partners = await self.session.scalar(
                select(func.count()).select_from(latest_rank_subq)
            ) or 0
            above_count = await self.session.scalar(
                select(func.count())
                .select_from(latest_rank_subq)
                .where(latest_rank_subq.c.ranking_score > rank_score)
            ) or 0
            rank_position = above_count + 1

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
            rank_position=rank_position,
            total_ranked_partners=total_ranked_partners,
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
