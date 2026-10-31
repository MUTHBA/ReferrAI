# -----------------------------------------------------------------------------
# backend/app/ai/features.py
#
# Single source of truth for model inputs. Each model has ONE pure feature
# function that is called both by training (over in-memory synthetic events)
# and by live scoring (over rows loaded from the database), so the two can
# never compute a feature differently. The async load_* helpers fetch exactly
# the rows the pure functions need.
#
#   quality_features(conversion, click, partner, prior_conversions) -> dict
#   fraud_features(click, history)                                  -> dict
#   churn_features(partner, as_of, conversions, clicks)             -> dict
#
# Feature lists (QUALITY_FEATURES, FRAUD_FEATURES, CHURN_FEATURES) define the
# column order stored with each trained model.
# -----------------------------------------------------------------------------

from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Event records shared by training and inference
# ---------------------------------------------------------------------------


@dataclass
class ClickEvent:
    id: uuid.UUID
    partner_id: uuid.UUID
    ts: datetime
    ip: str = "unknown"
    user_agent: str = ""
    device_type: str = "unknown"
    source: Optional[str] = None
    fingerprint: str = "unknown"


@dataclass
class ConversionEvent:
    id: uuid.UUID
    partner_id: uuid.UUID
    ts: datetime
    value: float
    click_id: Optional[uuid.UUID] = None


@dataclass
class PartnerSnapshot:
    id: uuid.UUID
    created_at: datetime
    tier_rank: int = 1
    extra: dict = field(default_factory=dict)


def fingerprint_for(ip: Optional[str], user_agent: Optional[str]) -> str:
    """Device fingerprint = IP + user agent. A user agent alone is shared by
    millions of visitors, so it is useless for spotting one device."""
    raw = f"{ip or 'unknown'}|{user_agent or ''}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

QUALITY_NUMERIC = [
    "has_click",
    "hours_to_convert_log",
    "order_value_log",
    "partner_tenure_days",
    "partner_tier_rank",
    "partner_prior_conversions_log",
]
QUALITY_CATEGORICAL = ["source_type", "device_type"]
QUALITY_FEATURES = QUALITY_NUMERIC + QUALITY_CATEGORICAL

_SEARCH = ("google", "bing", "duckduckgo", "yahoo", "search", "baidu")
_SOCIAL = ("facebook", "instagram", "twitter", "x.com", "tiktok", "linkedin", "youtube", "reddit", "social", "pinterest")
_EMAIL = ("mail", "newsletter", "email")


def source_type(source: Optional[str]) -> str:
    """Bucket a free-text utm_source into a small, stable vocabulary."""
    if not source:
        return "direct"
    s = source.lower()
    if any(k in s for k in _SEARCH):
        return "search"
    if any(k in s for k in _SOCIAL):
        return "social"
    if any(k in s for k in _EMAIL):
        return "email"
    return "other"


def quality_features(
    conversion: ConversionEvent,
    click: Optional[ClickEvent],
    partner: PartnerSnapshot,
    prior_conversions: int,
) -> dict:
    hours = 0.0
    if click is not None:
        hours = max(0.0, (conversion.ts - click.ts).total_seconds() / 3600.0)
    return {
        "has_click": 1.0 if click is not None else 0.0,
        "hours_to_convert_log": math.log1p(hours),
        "order_value_log": math.log1p(max(0.0, float(conversion.value))),
        "partner_tenure_days": float(min(730, max(0, (conversion.ts - partner.created_at).days))),
        "partner_tier_rank": float(partner.tier_rank),
        "partner_prior_conversions_log": math.log1p(max(0, prior_conversions)),
        "source_type": source_type(click.source) if click else "direct",
        "device_type": click.device_type if click else "unknown",
    }


# ---------------------------------------------------------------------------
# Fraud (per click)
# ---------------------------------------------------------------------------

FRAUD_FEATURES = [
    "ip_clicks_1h",
    "partner_clicks_1h",
    "partner_distinct_ips_24h",
    "fingerprint_partner_spread_24h",
    "seconds_since_prev_ip_click_log",
    "is_bot",
    "is_mobile",
]
FRAUD_HISTORY_WINDOW = timedelta(hours=24)


def fraud_features(click: ClickEvent, history: Iterable[ClickEvent]) -> dict:
    """Features for one click given the clicks in the 24h up to and including it.

    `history` may contain unrelated clicks; only those sharing the click's IP,
    partner or fingerprint inside the window are counted. The click itself is
    counted in the 1h/24h totals.
    """
    t = click.ts
    h1 = t - timedelta(hours=1)
    h24 = t - FRAUD_HISTORY_WINDOW
    ip_1h = 0
    partner_1h = 0
    partner_ips: set[str] = set()
    fp_partners: set[uuid.UUID] = set()
    prev_ip_ts: Optional[datetime] = None
    seen_self = False
    for c in history:
        if c.ts > t or c.ts < h24:
            continue
        if c.id == click.id:
            seen_self = True
        if c.ip == click.ip:
            if c.ts >= h1:
                ip_1h += 1
            if c.id != click.id and (prev_ip_ts is None or c.ts > prev_ip_ts):
                prev_ip_ts = c.ts
        if c.partner_id == click.partner_id:
            partner_ips.add(c.ip)
            if c.ts >= h1:
                partner_1h += 1
        if c.fingerprint == click.fingerprint:
            fp_partners.add(c.partner_id)
    if not seen_self:  # make the function robust to callers that omit the click
        ip_1h += 1
        partner_1h += 1
        partner_ips.add(click.ip)
        fp_partners.add(click.partner_id)
    gap = (t - prev_ip_ts).total_seconds() if prev_ip_ts else FRAUD_HISTORY_WINDOW.total_seconds()
    return {
        "ip_clicks_1h": float(ip_1h),
        "partner_clicks_1h": float(partner_1h),
        "partner_distinct_ips_24h": float(len(partner_ips)),
        "fingerprint_partner_spread_24h": float(len(fp_partners)),
        "seconds_since_prev_ip_click_log": math.log1p(max(0.0, gap)),
        "is_bot": 1.0 if click.device_type == "bot" else 0.0,
        "is_mobile": 1.0 if click.device_type in ("mobile", "tablet") else 0.0,
    }


# ---------------------------------------------------------------------------
# Churn (per partner, as of a point in time)
# ---------------------------------------------------------------------------

CHURN_FEATURES = [
    "conversions_30d",
    "conversions_prev_30d",
    "conversion_trend",
    "clicks_30d",
    "clicks_prev_30d",
    "click_trend",
    "days_since_last_conversion",
    "days_since_last_click",
    "tenure_days",
    "tier_rank",
    "revenue_90d_log",
]
CHURN_LOOKBACK = timedelta(days=120)
CHURN_HORIZON = timedelta(days=30)


def churn_features(
    partner: PartnerSnapshot,
    as_of: datetime,
    conversions: Iterable[ConversionEvent],
    clicks: Iterable[ClickEvent],
) -> dict:
    """Activity features from the partner's events BEFORE `as_of`."""
    d30 = as_of - timedelta(days=30)
    d60 = as_of - timedelta(days=60)
    d90 = as_of - timedelta(days=90)
    tenure = max(0, (as_of - partner.created_at).days)
    cap = float(min(tenure, 120))

    conv_30 = conv_prev = 0
    revenue_90 = 0.0
    last_conv: Optional[datetime] = None
    for c in conversions:
        if c.ts >= as_of:
            continue
        if c.ts >= d30:
            conv_30 += 1
        elif c.ts >= d60:
            conv_prev += 1
        if c.ts >= d90:
            revenue_90 += float(c.value)
        if last_conv is None or c.ts > last_conv:
            last_conv = c.ts

    clk_30 = clk_prev = 0
    last_click: Optional[datetime] = None
    for c in clicks:
        if c.ts >= as_of:
            continue
        if c.ts >= d30:
            clk_30 += 1
        elif c.ts >= d60:
            clk_prev += 1
        if last_click is None or c.ts > last_click:
            last_click = c.ts

    def days_since(ts: Optional[datetime]) -> float:
        return cap if ts is None else float(min(cap, (as_of - ts).total_seconds() / 86400.0))

    return {
        "conversions_30d": float(conv_30),
        "conversions_prev_30d": float(conv_prev),
        "conversion_trend": (conv_30 - conv_prev) / (conv_prev + 1.0),
        "clicks_30d": float(clk_30),
        "clicks_prev_30d": float(clk_prev),
        "click_trend": (clk_30 - clk_prev) / (clk_prev + 1.0),
        "days_since_last_conversion": days_since(last_conv),
        "days_since_last_click": days_since(last_click),
        "tenure_days": float(min(tenure, 730)),
        "tier_rank": float(partner.tier_rank),
        "revenue_90d_log": math.log1p(revenue_90),
    }


# ---------------------------------------------------------------------------
# Database loaders (inference side)
# ---------------------------------------------------------------------------


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def click_event(row) -> ClickEvent:
    info = row.device_info or {}
    ua = info.get("user_agent") or ""
    return ClickEvent(
        id=row.id,
        partner_id=row.partner_id,
        ts=_aware(row.clicked_at),
        ip=row.ip_address or "unknown",
        user_agent=ua,
        device_type=info.get("device_type") or _device_type(ua),
        source=row.source,
        fingerprint=info.get("fingerprint") or fingerprint_for(row.ip_address, ua),
    )


def _device_type(user_agent: str) -> str:
    # Imported lazily to avoid a services -> ai import cycle at module load.
    from app.services.referral_click_service import device_type_from_user_agent

    return device_type_from_user_agent(user_agent)


def conversion_event(row) -> ConversionEvent:
    return ConversionEvent(
        id=row.id,
        partner_id=row.partner_id,
        ts=_aware(row.converted_at),
        value=float(row.conversion_value),
        click_id=row.click_id,
    )


async def partner_snapshot(session: AsyncSession, partner_id: uuid.UUID) -> Optional[PartnerSnapshot]:
    from app.models.partner import Partner, PartnerTier

    row = (
        await session.execute(
            select(Partner.id, Partner.created_at, PartnerTier.rank_order)
            .outerjoin(PartnerTier, PartnerTier.id == Partner.tier_id)
            .where(Partner.id == partner_id)
        )
    ).first()
    if row is None:
        return None
    return PartnerSnapshot(id=row.id, created_at=_aware(row.created_at), tier_rank=int(row.rank_order or 1))


async def load_quality_inputs(session: AsyncSession, conversion_id: uuid.UUID):
    """Return (conversion, click|None, partner, prior_conversions) or None."""
    from sqlalchemy import func

    from app.models.referral import ReferralClick, ReferralConversion

    conv_row = (
        await session.execute(select(ReferralConversion).where(ReferralConversion.id == conversion_id))
    ).scalar_one_or_none()
    if conv_row is None:
        return None
    conversion = conversion_event(conv_row)
    click = None
    if conv_row.click_id:
        click_row = (
            await session.execute(select(ReferralClick).where(ReferralClick.id == conv_row.click_id))
        ).scalar_one_or_none()
        click = click_event(click_row) if click_row else None
    partner = await partner_snapshot(session, conv_row.partner_id)
    prior = (
        await session.execute(
            select(func.count())
            .select_from(ReferralConversion)
            .where(
                ReferralConversion.partner_id == conv_row.partner_id,
                ReferralConversion.converted_at < conv_row.converted_at,
                ReferralConversion.is_synthetic == False,  # noqa: E712
            )
        )
    ).scalar_one()
    return conversion, click, partner, int(prior)


async def load_fraud_inputs(session: AsyncSession, click_id: uuid.UUID):
    """Return (click, history) or None. History = real clicks in the 24h window
    that share the click's IP, partner or fingerprint."""
    from app.models.referral import ReferralClick

    row = (await session.execute(select(ReferralClick).where(ReferralClick.id == click_id))).scalar_one_or_none()
    if row is None:
        return None
    click = click_event(row)
    fp_expr = ReferralClick.device_info["fingerprint"].astext
    rows = (
        await session.execute(
            select(ReferralClick).where(
                ReferralClick.clicked_at >= click.ts - FRAUD_HISTORY_WINDOW,
                ReferralClick.clicked_at <= click.ts,
                ReferralClick.is_synthetic == False,  # noqa: E712
                or_(
                    ReferralClick.ip_address == row.ip_address,
                    ReferralClick.partner_id == row.partner_id,
                    fp_expr == click.fingerprint,
                ),
            )
        )
    ).scalars()
    return click, [click_event(r) for r in rows]


async def load_churn_inputs(session: AsyncSession, partner_id: uuid.UUID, as_of: datetime):
    """Return (partner, conversions, clicks) for the lookback window, or None."""
    from app.models.referral import ReferralClick, ReferralConversion

    partner = await partner_snapshot(session, partner_id)
    if partner is None:
        return None
    since = as_of - CHURN_LOOKBACK
    convs = (
        await session.execute(
            select(ReferralConversion).where(
                ReferralConversion.partner_id == partner_id,
                ReferralConversion.converted_at >= since,
                ReferralConversion.is_synthetic == False,  # noqa: E712
            )
        )
    ).scalars()
    clicks = (
        await session.execute(
            select(ReferralClick).where(
                ReferralClick.partner_id == partner_id,
                ReferralClick.clicked_at >= since,
                ReferralClick.is_synthetic == False,  # noqa: E712
            )
        )
    ).scalars()
    return partner, [conversion_event(c) for c in convs], [click_event(c) for c in clicks]


# Human-readable names for explanations and the admin UI.
FEATURE_LABELS = {
    "has_click": "came through a tracked click",
    "hours_to_convert_log": "time from click to purchase",
    "order_value_log": "order value",
    "partner_tenure_days": "partner tenure",
    "partner_tier_rank": "partner tier",
    "partner_prior_conversions_log": "partner's past conversions",
    "source_type": "traffic source",
    "device_type": "device type",
    "ip_clicks_1h": "clicks from the same IP in the last hour",
    "partner_clicks_1h": "partner's clicks in the last hour",
    "partner_distinct_ips_24h": "distinct IPs on this partner in 24h",
    "fingerprint_partner_spread_24h": "partners this device clicked in 24h",
    "seconds_since_prev_ip_click_log": "time since this IP's previous click",
    "is_bot": "automated (bot) user agent",
    "is_mobile": "mobile device",
    "conversions_30d": "conversions in the last 30 days",
    "conversions_prev_30d": "conversions in the 30 days before that",
    "conversion_trend": "conversion trend",
    "clicks_30d": "clicks in the last 30 days",
    "clicks_prev_30d": "clicks in the 30 days before that",
    "click_trend": "click trend",
    "days_since_last_conversion": "days since last conversion",
    "days_since_last_click": "days since last click",
    "tenure_days": "time as a partner",
    "tier_rank": "tier",
    "revenue_90d_log": "revenue in the last 90 days",
}
