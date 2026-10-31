# -----------------------------------------------------------------------------
# backend/app/services/dashboard_service.py
#
# Read-only reporting for the admin dashboard (RPT-001), the partner
# dashboard (RPT-002) and the CSV exports (RPT-003).
#
# Rules applied everywhere:
#   * synthetic partners / clicks / conversions are excluded;
#   * "latest score" means the newest ai_scores row per entity, partner-level
#     rows only (click-level fraud rows are ignored);
#   * partner quality = average of the latest quality score of each of the
#     partner's conversions (quality is stored per conversion);
#   * daily series are bucketed by UTC date and zero-filled;
#   * thresholds (churn alert) come from the settings table.
# -----------------------------------------------------------------------------

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_score import AIScore
from app.models.commission import Commission
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner, PartnerTier
from app.models.referral import ReferralClick, ReferralCode, ReferralConversion, ReferralLink
from app.models.wallet import Wallet, Withdrawal
from app.repositories.ai_score_repository import AIScoreRepository
from app.repositories.fraud_flag_repository import FraudFlagRepository
from app.repositories.partner_repository import PartnerRepository
from app.schemas.dashboard import (
    AdminDashboardResponse,
    AdminKPIs,
    ChurnAtRiskPartner,
    EarningsDataPoint,
    PartnerDashboardResponse,
    PartnerKPIs,
    PendingWithdrawalSummary,
    RecentFraudFlag,
    TierProgress,
    TopPartner,
    VolumeDataPoint,
)
from app.services.setting_service import SettingService

ZERO = Decimal("0")
EARNED_STATUSES = ("approved", "paid")


def _utc_day(column):
    """Bucket a timestamptz column by its UTC calendar date."""
    return cast(func.timezone("UTC", column), Date)


def _rate_label(tier: PartnerTier) -> str:
    if tier.commission_type == "fixed":
        return f"${Decimal(tier.commission_value):.2f} per sale"
    return f"{(Decimal(tier.commission_value) * 100).normalize():f}%"


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.scores = AIScoreRepository(session)

    # ------------------------------------------------------------------ #
    # Admin dashboard
    # ------------------------------------------------------------------ #
    async def get_admin_dashboard(self, days: int = 30) -> AdminDashboardResponse:
        churn_threshold = float(await SettingService(self.session).get("churn.alert_threshold"))
        chart = await self._volume_chart(days)
        churn_scores = await self.scores.latest_by_entity("churn_risk")
        real_partners = await self._real_partner_names()

        at_risk = sorted(
            (
                ChurnAtRiskPartner(partner_id=pid, name=real_partners[pid], churn_score=score)
                for pid, score in churn_scores.items()
                if pid in real_partners and score is not None and score > churn_threshold
            ),
            key=lambda p: p.churn_score,
            reverse=True,
        )
        kpis = await self._admin_kpis(chart, len(at_risk))
        return AdminDashboardResponse(
            days=days,
            kpis=kpis,
            volume_chart=chart,
            churn_at_risk_partners=at_risk,
            top_partners=await self._top_partners(),
            recent_fraud_flags=await self._recent_fraud_flags(),
            pending_withdrawals=await self._pending_withdrawals(),
        )

    async def _real_partner_names(self) -> dict[uuid.UUID, str]:
        rows = await self.session.execute(
            select(Partner.id, Partner.name).where(Partner.is_synthetic.is_(False))
        )
        return {r.id: r.name for r in rows}

    async def _admin_kpis(self, chart: list[VolumeDataPoint], churn_alert_count: int) -> AdminKPIs:
        real_conv = ReferralConversion.is_synthetic.is_(False)

        totals = (
            await self.session.execute(
                select(
                    func.count(ReferralConversion.id),
                    func.coalesce(func.sum(ReferralConversion.conversion_value), ZERO),
                ).where(real_conv)
            )
        ).one()

        active_partners = await self.session.scalar(
            select(func.count()).select_from(Partner)
            .where(Partner.status == "active", Partner.is_synthetic.is_(False))
        ) or 0

        total_commission = await self.session.scalar(
            select(func.coalesce(func.sum(Commission.amount), ZERO))
            .join(ReferralConversion, Commission.conversion_id == ReferralConversion.id)
            .where(Commission.status.in_(EARNED_STATUSES), real_conv)
        ) or ZERO

        def _withdrawal_totals(status_values):
            return (
                select(func.count(Withdrawal.id), func.coalesce(func.sum(Withdrawal.amount), ZERO))
                .join(Partner, Withdrawal.partner_id == Partner.id)
                .where(Withdrawal.status.in_(status_values), Partner.is_synthetic.is_(False))
            )

        pending = (await self.session.execute(_withdrawal_totals(("pending",)))).one()
        paid = (await self.session.execute(_withdrawal_totals(("approved", "paid")))).one()

        fraud_alert_count = await self.session.scalar(
            select(func.count()).select_from(FraudFlag)
            .join(Partner, FraudFlag.partner_id == Partner.id)
            .where(FraudFlag.status == "pending_review", Partner.is_synthetic.is_(False))
        ) or 0

        period_clicks = sum(p.clicks for p in chart)
        period_conversions = sum(p.conversions for p in chart)
        return AdminKPIs(
            total_conversions=int(totals[0]),
            total_revenue=Decimal(str(totals[1])),
            active_partners=int(active_partners),
            total_commission=Decimal(str(total_commission)),
            pending_payout_count=int(pending[0]),
            pending_payout_amount=Decimal(str(pending[1])),
            total_paid_out=Decimal(str(paid[1])),
            fraud_alert_count=int(fraud_alert_count),
            churn_alert_count=churn_alert_count,
            period_clicks=period_clicks,
            period_conversions=period_conversions,
            period_revenue=sum((p.revenue for p in chart), ZERO),
            period_commission=sum((p.commission for p in chart), ZERO),
            conversion_rate=(period_conversions / period_clicks) if period_clicks else None,
        )

    async def _volume_chart(self, days: int, partner_id: Optional[uuid.UUID] = None) -> list[VolumeDataPoint]:
        today = datetime.now(timezone.utc).date()
        first_day = today - timedelta(days=days - 1)
        cutoff = datetime.combine(first_day, datetime.min.time(), tzinfo=timezone.utc)

        click_day = _utc_day(ReferralClick.clicked_at)
        click_stmt = (
            select(click_day.label("day"), func.count().label("n"))
            .where(ReferralClick.clicked_at >= cutoff, ReferralClick.is_synthetic.is_(False))
            .group_by(click_day)
        )
        conv_day = _utc_day(ReferralConversion.converted_at)
        conv_stmt = (
            select(
                conv_day.label("day"),
                func.count(ReferralConversion.id).label("n"),
                func.coalesce(func.sum(ReferralConversion.conversion_value), ZERO).label("revenue"),
            )
            .where(ReferralConversion.converted_at >= cutoff, ReferralConversion.is_synthetic.is_(False))
            .group_by(conv_day)
        )
        comm_stmt = (
            select(conv_day.label("day"), func.coalesce(func.sum(Commission.amount), ZERO).label("amount"))
            .join(Commission, Commission.conversion_id == ReferralConversion.id)
            .where(
                ReferralConversion.converted_at >= cutoff,
                ReferralConversion.is_synthetic.is_(False),
                Commission.status.in_(EARNED_STATUSES),
            )
            .group_by(conv_day)
        )
        if partner_id is not None:
            click_stmt = click_stmt.where(ReferralClick.partner_id == partner_id)
            conv_stmt = conv_stmt.where(ReferralConversion.partner_id == partner_id)
            comm_stmt = comm_stmt.where(ReferralConversion.partner_id == partner_id)

        clicks = {r.day: r.n for r in await self.session.execute(click_stmt)}
        convs = {r.day: (r.n, r.revenue) for r in await self.session.execute(conv_stmt)}
        comms = {r.day: r.amount for r in await self.session.execute(comm_stmt)}

        points = []
        for i in range(days):
            d = first_day + timedelta(days=i)
            n_conv, revenue = convs.get(d, (0, ZERO))
            points.append(
                VolumeDataPoint(
                    date=d,
                    clicks=int(clicks.get(d, 0)),
                    conversions=int(n_conv),
                    revenue=Decimal(str(revenue)),
                    commission=Decimal(str(comms.get(d, ZERO))),
                )
            )
        return points

    async def _top_partners(self, limit: int = 5) -> list[TopPartner]:
        stats = (
            select(
                ReferralConversion.partner_id.label("pid"),
                func.count(ReferralConversion.id).label("conversions"),
                func.coalesce(func.sum(ReferralConversion.conversion_value), ZERO).label("revenue"),
            )
            .where(ReferralConversion.is_synthetic.is_(False))
            .group_by(ReferralConversion.partner_id)
            .subquery()
        )
        comm = (
            select(
                Commission.partner_id.label("pid"),
                func.coalesce(func.sum(Commission.amount), ZERO).label("commission"),
            )
            .where(Commission.status.in_(EARNED_STATUSES))
            .group_by(Commission.partner_id)
            .subquery()
        )
        rows = await self.session.execute(
            select(Partner, PartnerTier.name, stats.c.conversions, stats.c.revenue, comm.c.commission)
            .join(stats, stats.c.pid == Partner.id)
            .outerjoin(comm, comm.c.pid == Partner.id)
            .outerjoin(PartnerTier, PartnerTier.id == Partner.tier_id)
            .where(Partner.is_synthetic.is_(False))
            .order_by(stats.c.revenue.desc())
            .limit(limit)
        )
        rank = await self.scores.latest_by_entity("ranking")
        return [
            TopPartner(
                partner_id=p.id,
                name=p.name,
                tier_name=tier_name,
                conversions=int(conversions),
                revenue=Decimal(str(revenue)),
                commission=Decimal(str(commission or ZERO)),
                rank_score=rank.get(p.id),
            )
            for p, tier_name, conversions, revenue, commission in rows
        ]

    async def _recent_fraud_flags(self, limit: int = 5) -> list[RecentFraudFlag]:
        rows = await FraudFlagRepository(self.session).list_with_details("pending_review", limit)
        return [
            RecentFraudFlag(
                id=flag.id,
                partner_id=partner.id,
                partner_name=partner.name,
                score=float(score.score) if score.score is not None else None,
                explanation=score.explanation,
                created_at=flag.created_at,
            )
            for flag, partner, score in rows
        ]

    async def _pending_withdrawals(self, limit: int = 5) -> list[PendingWithdrawalSummary]:
        rows = await self.session.execute(
            select(Withdrawal, Partner.name)
            .join(Partner, Withdrawal.partner_id == Partner.id)
            .where(Withdrawal.status == "pending", Partner.is_synthetic.is_(False))
            .order_by(Withdrawal.requested_at.asc())
            .limit(limit)
        )
        return [
            PendingWithdrawalSummary(
                id=w.id, partner_id=w.partner_id, partner_name=name, amount=w.amount, requested_at=w.requested_at
            )
            for w, name in rows
        ]

    # ------------------------------------------------------------------ #
    # Partner dashboard
    # ------------------------------------------------------------------ #
    async def get_partner_dashboard(self, user_id: uuid.UUID, days: int = 30) -> PartnerDashboardResponse:
        partner = await PartnerRepository(self.session).get_by_user_id(user_id)
        return await self.partner_dashboard_for(partner, days)

    async def partner_dashboard_for(self, partner: Optional[Partner], days: int = 30) -> PartnerDashboardResponse:
        if partner is None:
            return PartnerDashboardResponse(
                days=days,
                kpis=PartnerKPIs(referral_count=0, conversion_count=0, total_earnings=ZERO, wallet_balance=ZERO),
            )

        async def _count(model, *conditions) -> int:
            return int(await self.session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0)

        link_count = await _count(ReferralLink, ReferralLink.partner_id == partner.id)
        code_count = await _count(ReferralCode, ReferralCode.partner_id == partner.id)
        click_count = await _count(
            ReferralClick, ReferralClick.partner_id == partner.id, ReferralClick.is_synthetic.is_(False)
        )
        conversion_count = await _count(
            ReferralConversion,
            ReferralConversion.partner_id == partner.id,
            ReferralConversion.is_synthetic.is_(False),
        )

        wallet = (
            await self.session.execute(select(Wallet).where(Wallet.partner_id == partner.id))
        ).scalar_one_or_none()
        pending = await self.session.scalar(
            select(func.coalesce(func.sum(Withdrawal.amount), ZERO))
            .where(Withdrawal.partner_id == partner.id, Withdrawal.status == "pending")
        ) or ZERO

        quality = (await self.scores.partner_quality_averages([partner.id])).get(partner.id)
        churn = await self.scores.get_latest(partner.id, "churn_risk", "partner")
        rank_map = await self.scores.latest_by_entity("ranking")
        real_ids = set((await self._real_partner_names()).keys())
        ranked = {pid: s for pid, s in rank_map.items() if pid in real_ids and s is not None}
        rank_score = ranked.get(partner.id)
        rank_position = (
            1 + sum(1 for s in ranked.values() if s > rank_score) if rank_score is not None else None
        )

        chart = await self._volume_chart(days, partner.id)
        return PartnerDashboardResponse(
            days=days,
            kpis=PartnerKPIs(
                referral_count=conversion_count,
                conversion_count=conversion_count,
                total_earnings=wallet.total_earned if wallet else ZERO,
                wallet_balance=wallet.balance if wallet else ZERO,
                total_withdrawn=wallet.total_withdrawn if wallet else ZERO,
                pending_withdrawals=Decimal(str(pending)),
                link_count=link_count,
                code_count=code_count,
                click_count=click_count,
                conversion_rate=(conversion_count / click_count) if click_count else None,
            ),
            quality_score=Decimal(str(quality)) if quality is not None else None,
            churn_score=churn.score if churn is not None else None,
            churn_status=churn.status if churn is not None else None,
            rank_score=Decimal(str(rank_score)) if rank_score is not None else None,
            rank_position=rank_position,
            total_ranked_partners=len(ranked) if rank_score is not None else None,
            earnings_chart=[
                EarningsDataPoint(date=p.date, clicks=p.clicks, conversions=p.conversions, earnings=p.commission)
                for p in chart
            ],
            tier=await self._tier_progress(partner),
        )

    async def _tier_progress(self, partner: Partner) -> TierProgress:
        tiers = list((await self.session.execute(select(PartnerTier).order_by(PartnerTier.rank_order))).scalars())
        if not tiers:
            return TierProgress()
        current = next((t for t in tiers if t.id == partner.tier_id), None)
        current_rank = current.rank_order if current else 0
        nxt = next((t for t in tiers if t.rank_order > current_rank), None)
        progress = TierProgress(
            current_tier=current.name if current else None,
            current_rate_label=_rate_label(current) if current else None,
        )
        if nxt is None:
            progress.progress = 1.0
            return progress

        need_refs = max(0, nxt.min_referral_count - partner.total_referral_count)
        need_rev = max(ZERO, Decimal(nxt.min_revenue_contribution) - partner.total_revenue_contribution)
        parts = []
        if nxt.min_referral_count > 0:
            parts.append(min(1.0, partner.total_referral_count / nxt.min_referral_count))
        if nxt.min_revenue_contribution > 0:
            parts.append(min(1.0, float(partner.total_revenue_contribution / Decimal(nxt.min_revenue_contribution))))
        progress.next_tier = nxt.name
        progress.next_rate_label = _rate_label(nxt)
        progress.referrals_needed = need_refs
        progress.revenue_needed = need_rev
        progress.progress = min(parts) if parts else 1.0
        return progress

    # ------------------------------------------------------------------ #
    # CSV exports (non-synthetic only)
    # ------------------------------------------------------------------ #
    async def get_referrals_csv_data(self) -> list[dict]:
        rows = await self.session.execute(
            select(ReferralConversion, Partner.name)
            .join(Partner, Partner.id == ReferralConversion.partner_id)
            .where(ReferralConversion.is_synthetic.is_(False))
            .order_by(ReferralConversion.converted_at.desc())
        )
        return [
            {
                "id": str(r.id),
                "partner_id": str(r.partner_id),
                "partner_name": name,
                "external_reference": r.external_reference,
                "click_id": str(r.click_id) if r.click_id else "",
                "referral_code_id": str(r.referral_code_id) if r.referral_code_id else "",
                "conversion_value": str(r.conversion_value),
                "attribution_model": r.attribution_model,
                "converted_at": r.converted_at.isoformat(),
            }
            for r, name in rows
        ]

    async def get_commissions_csv_data(self) -> list[dict]:
        rows = await self.session.execute(
            select(Commission, Partner.name)
            .join(ReferralConversion, Commission.conversion_id == ReferralConversion.id)
            .join(Partner, Partner.id == Commission.partner_id)
            .where(ReferralConversion.is_synthetic.is_(False))
            .order_by(Commission.calculated_at.desc())
        )
        return [
            {
                "id": str(c.id),
                "partner_id": str(c.partner_id),
                "partner_name": name,
                "conversion_id": str(c.conversion_id),
                "amount": str(c.amount),
                "commission_type": c.commission_type,
                "tier_id": str(c.tier_id) if c.tier_id else "",
                "status": c.status,
                "calculated_at": c.calculated_at.isoformat(),
            }
            for c, name in rows
        ]

    async def get_partners_csv_data(self) -> list[dict]:
        rows = await self.session.execute(
            select(Partner, PartnerTier.name)
            .outerjoin(PartnerTier, PartnerTier.id == Partner.tier_id)
            .where(Partner.is_synthetic.is_(False))
            .order_by(Partner.created_at.desc())
        )
        return [
            {
                "id": str(p.id),
                "name": p.name,
                "email": p.email,
                "status": p.status,
                "tier": tier_name or "",
                "total_referral_count": str(p.total_referral_count),
                "total_revenue_contribution": str(p.total_revenue_contribution),
                "created_at": p.created_at.isoformat(),
            }
            for p, tier_name in rows
        ]
