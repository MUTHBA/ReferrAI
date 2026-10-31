#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# backend/scripts/demo_history.py
#
# Fills an EMPTY database with ~6 months of realistic demo activity so every
# dashboard has something to show: 12 partners with different stories
# (growing, steady, slowing down, brand new, one click-fraud burst, one
# suspended), links and codes, daily clicks, sales, commissions, tier
# upgrades, withdrawals in every state, AI scores (quality, fraud, churn,
# ranking) and a few discovery candidates.
#
# Everything goes through the real services (attribution, commission, wallet,
# tier upgrade, fraud rules, AI scoring), then timestamps are moved back to
# the day each event "happened". Rows are normal (is_synthetic = false) demo
# records — they show up in dashboards like real data.
#
# Usage (from backend/, after `alembic upgrade head`):
#   python -m scripts.demo_history                 # admin@referrai.io / Admin123!
#   python -m scripts.demo_history --admin-email you@example.com --admin-password '...'
# Partner logins: <first name>@demo.referrai.io / Partner123!   (e.g. priya@demo.referrai.io)
# Refuses to run if demo partners already exist. Deterministic (fixed seed).
# -----------------------------------------------------------------------------

from __future__ import annotations

import argparse
import asyncio
import math
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, update

from app.ai import registry
from app.ai.features import fingerprint_for
from app.core.database import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.commission import Commission
from app.models.partner import Partner, PartnerTier
from app.models.referral import ReferralClick, ReferralCode, ReferralConversion, ReferralLink
from app.models.user import User
from app.models.wallet import Transaction, Wallet, Withdrawal
from app.schemas.auth import RegisterRequest
from app.schemas.referral_conversion import ConversionCreate
from app.services import ai_service
from app.services.auth_service import AuthService
from app.services.discovery_service import DiscoveryService
from app.services.referral_conversion_service import ReferralConversionService
from app.services.wallet_service import WalletService

NOW = datetime.now(timezone.utc).replace(microsecond=0)
DOMAIN = "demo.referrai.io"
PARTNER_PASSWORD = "Partner123!"

UA_DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1"
UA_BOT = "python-requests/2.31.0"
SOURCES = ["instagram", "newsletter", "google", "youtube", None, "tiktok", "blog"]


@dataclass
class Story:
    name: str
    business: str
    category: str
    joined_days_ago: int
    clicks_per_day: float  # at the start
    growth: float  # multiplier on clicks/day by today (1 = flat)
    conversion_rate: float
    avg_order: float
    stop_days_ago: int = 0  # activity stops this many days ago (churn story)
    final_status: str = "active"
    bot_burst: bool = False


STORIES = [
    Story("Priya Nair", "Peak Fitness Coaching", "Fitness", 200, 6, 2.2, 0.075, 140),
    Story("Marcus Vance", "UrbanThreads", "Fashion & apparel", 185, 12, 1.2, 0.07, 95),
    Story("Elena Rostova", "Nordic Gear", "Travel", 170, 8, 0.8, 0.06, 160, stop_days_ago=38),
    Story("David Kim", "Horizon Media", "Tech & productivity", 150, 5, 0.6, 0.05, 210, stop_days_ago=24),
    Story("Sarah Jenkins", "Apex Collective", "Beauty", 140, 4, 1.0, 0.07, 60),
    Story("Devon Lane", "TechPulse", "Tech & productivity", 120, 5, 1.1, 0.055, 180),
    Story("Kiran Patel", "Apex Labs", "Wellness & nutrition", 95, 3, 2.5, 0.08, 75),
    Story("Rahul Verma", "QuickDeals Hub", "Other", 80, 4, 1.0, 0.04, 55, bot_burst=True),
    Story("Tom Miller", "Miller Crafts", "Other", 110, 2, 0.9, 0.05, 70, final_status="suspended"),
    Story("Chloe Bennett", "Glow Collective", "Beauty", 14, 3, 1.3, 0.08, 65),
    Story("Lucas Meyer", "ByteCraft", "Tech & productivity", 8, 2, 1.0, 0.06, 120),
    Story("Nina Patel", "Artisan Foods", "Food & drink", 3, 1, 1.0, 0.0, 40),
]

CANDIDATES = [
    ("Kura Athletics", "Fitness", "Strength and conditioning gym selling memberships and online training plans to busy professionals."),
    ("Nordic Woolens", "Fashion & apparel", "Merino wool clothing and outdoor layers sold online to hikers and commuters."),
    ("Verve Supplement Co.", "Wellness & nutrition", "Plant-based protein and vitamins for gym-goers, sold direct to consumers."),
    ("Lumina Workspace", "Tech & productivity", "Desk accessories and focus apps for remote workers and small teams."),
    ("Saffron Table", "Food & drink", "Meal kits with regional Indian recipes delivered weekly to families."),
]


def ip_for(rng: random.Random) -> str:
    return f"{rng.choice([73, 98, 174, 203, 66, 24])}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"


async def backdate_since(session, marker: datetime, when: datetime) -> None:
    """Move audit rows written since `marker` to `when` (they were written 'now')."""
    await session.execute(update(AuditLog).where(AuditLog.created_at >= marker).values(created_at=when))


async def ensure_tiers(session) -> None:
    """Add Silver and Gold above the existing tiers if they're missing (an older
    database may already use some rank numbers, so take the next free ones)."""
    tiers = list((await session.execute(select(PartnerTier))).scalars())
    names = {t.name for t in tiers}
    next_rank = max((t.rank_order for t in tiers), default=0) + 1
    for name, sales, revenue, rate in (("Silver", 20, "2500", "0.12"), ("Gold", 100, "10000", "0.15")):
        if name in names:
            continue
        session.add(PartnerTier(id=uuid.uuid4(), name=name, rank_order=next_rank, min_referral_count=sales,
                                min_revenue_contribution=Decimal(revenue), commission_type="percentage",
                                commission_value=Decimal(rate)))
        next_rank += 1
    await session.commit()


async def ensure_admin(session, email: str, password: str) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = await AuthService(session).create_admin(email, password)
        print(f"  created admin {email}")
    return user


async def create_partner(session, story: Story, rng: random.Random) -> tuple[Partner, list[ReferralLink], ReferralCode]:
    first = story.name.split()[0].lower()
    email = f"{first}@{DOMAIN}"
    await AuthService(session).register(RegisterRequest(email=email, password=PARTNER_PASSWORD, role="partner", name=story.name))
    partner = (await session.execute(select(Partner).where(Partner.email == email))).scalar_one()
    joined = NOW - timedelta(days=story.joined_days_ago, hours=rng.randint(1, 10))
    partner.business_name = story.business
    partner.category = story.category
    partner.phone = f"+1 555 {rng.randint(100, 999)} {rng.randint(1000, 9999)}"
    partner.created_at = joined
    await session.execute(update(User).where(User.id == partner.user_id).values(created_at=joined))

    slug_base = "".join(ch for ch in story.business.lower() if ch.isalnum())[:6]
    links = []
    for i, path in enumerate(["", "/sale"] if story.joined_days_ago > 60 else [""]):
        link = ReferralLink(
            id=uuid.uuid4(), partner_id=partner.id, slug=f"{slug_base}{rng.randint(1000, 9999)}{i}",
            destination_url=f"https://shop.example.com{path or '/'}", is_active=True,
            created_at=joined + timedelta(hours=2 + i * 24 * 20),
        )
        session.add(link)
        links.append(link)
    code = ReferralCode(
        id=uuid.uuid4(), partner_id=partner.id,
        code="".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8)),
        is_active=True, created_at=joined + timedelta(days=1),
    )
    session.add(code)
    await session.commit()
    return partner, links, code


def daily_clicks(story: Story, day_index: int, days: int, rng: random.Random) -> int:
    progress = day_index / max(1, days)
    rate = story.clicks_per_day * (1 + (story.growth - 1) * progress)
    rate *= 0.75 + 0.5 * rng.random()  # day-to-day noise
    if rng.random() < 0.08:
        rate *= 0.3  # quiet days
    return max(0, int(rng.gauss(rate, math.sqrt(max(rate, 0.1)))))


async def build_history(session, story: Story, partner: Partner, links: list[ReferralLink], code: ReferralCode, rng: random.Random) -> int:
    """Clicks and sales day by day, oldest first. Returns sales recorded."""
    sales = 0
    start = NOW - timedelta(days=story.joined_days_ago)
    order_no = 1000 + rng.randint(0, 800)
    for day in range(story.joined_days_ago + 1):
        day_start = start + timedelta(days=day)
        if story.stop_days_ago and day_start > NOW - timedelta(days=story.stop_days_ago):
            # Slowing down: only a trickle of clicks, no sales.
            n_clicks = 1 if rng.random() < 0.15 else 0
            convert = 0.0
        else:
            n_clicks = daily_clicks(story, day, story.joined_days_ago, rng)
            convert = story.conversion_rate
        for _ in range(n_clicks):
            clicked_at = day_start + timedelta(minutes=rng.randint(0, 1439))
            if clicked_at > NOW - timedelta(minutes=30):
                continue
            mobile = rng.random() < 0.62
            ip = ip_for(rng)
            ua = UA_MOBILE if mobile else UA_DESKTOP
            link = rng.choice(links)
            click = ReferralClick(
                id=uuid.uuid4(), referral_link_id=link.id, partner_id=partner.id, ip_address=ip,
                device_info={"user_agent": ua, "device_type": "mobile" if mobile else "desktop",
                             "fingerprint": fingerprint_for(ip, ua)},
                source=rng.choice(SOURCES), clicked_at=clicked_at, is_synthetic=False,
            )
            session.add(click)
            await session.flush()
            if convert and rng.random() < convert:
                converted_at = clicked_at + timedelta(hours=rng.lognormvariate(1.3, 1.1))
                if converted_at >= NOW:
                    continue
                order_no += rng.randint(1, 4)
                value = Decimal(str(round(max(12.0, rng.lognormvariate(math.log(story.avg_order), 0.45)), 2)))
                via_code = rng.random() < 0.12
                await session.commit()
                marker = datetime.now(timezone.utc)
                conv = await ReferralConversionService(session)._record(
                    ConversionCreate(
                        partner_id=partner.id,
                        external_reference=f"order-{order_no}",
                        conversion_value=value,
                        referral_code=code.code if via_code else None,
                        click_id=None if via_code else click.id,
                    )
                )
                # Move the sale and everything it wrote back to when it happened.
                values = {"converted_at": converted_at}
                if not via_code and conv.click_id is None:
                    # Attribution checks the window against the real clock, so a
                    # historical click is "too old" today; link it as it was then.
                    values.update(click_id=click.id, referral_link_id=link.id, attribution_model="last_click")
                await session.execute(update(ReferralConversion).where(ReferralConversion.id == conv.id).values(**values))
                commission = (await session.execute(select(Commission).where(Commission.conversion_id == conv.id))).scalar_one()
                await session.execute(update(Commission).where(Commission.id == commission.id).values(calculated_at=converted_at))
                await session.execute(update(Transaction).where(Transaction.reference_id == commission.id).values(created_at=converted_at))
                await backdate_since(session, marker, converted_at)
                await session.commit()
                sales += 1
        await session.commit()
    return sales


async def withdrawals_for(session, story: Story, partner: Partner, admin: User, rng: random.Random) -> None:
    """A realistic payout history: monthly withdrawals, mostly paid."""
    svc = WalletService(session)
    wallet = (await session.execute(select(Wallet).where(Wallet.partner_id == partner.id))).scalar_one()
    if wallet.balance < Decimal("40"):
        return
    months = max(1, min(4, story.joined_days_ago // 35))
    for m in range(months, 0, -1):
        await session.refresh(wallet)
        amount = (wallet.balance * Decimal(str(rng.uniform(0.2, 0.32)))).quantize(Decimal("0.01"))
        if amount < Decimal("15"):
            continue
        when = NOW - timedelta(days=m * 30 - rng.randint(0, 5), hours=rng.randint(1, 8))
        marker = datetime.now(timezone.utc)
        w = await svc.request_withdrawal(partner, amount)
        if w.status == "pending":
            await svc.review_withdrawal(w.id, "approved", admin.id, None, "198.51.100.24")
        await svc.mark_paid(w.id, admin.id, f"Payment ref {rng.randint(100000, 999999)}", "198.51.100.24")
        await session.execute(update(Withdrawal).where(Withdrawal.id == w.id).values(requested_at=when, reviewed_at=when + timedelta(hours=20)))
        await session.execute(update(Transaction).where(Transaction.reference_id == w.id).values(created_at=when))
        await backdate_since(session, marker, when + timedelta(hours=20))
        await session.commit()


async def open_withdrawals(session, partners: dict[str, Partner], admin: User) -> None:
    """Leave one request in each open state for the Payouts page."""
    svc = WalletService(session)

    async def request(name, amount, hours_ago):
        p = partners[name]
        await session.refresh(p)
        wallet = (await session.execute(select(Wallet).where(Wallet.partner_id == p.id))).scalar_one()
        await session.refresh(wallet)
        amount = min(Decimal(amount), (wallet.balance * Decimal("0.9")).quantize(Decimal("0.01")))
        if amount < Decimal("10"):
            return None
        marker = datetime.now(timezone.utc)
        w = await svc.request_withdrawal(p, amount)
        when = NOW - timedelta(hours=hours_ago)
        await session.execute(update(Withdrawal).where(Withdrawal.id == w.id).values(requested_at=when))
        await session.execute(update(Transaction).where(Transaction.reference_id == w.id).values(created_at=when))
        await backdate_since(session, marker, when)
        await session.commit()
        return w

    await request("Marcus Vance", "420.00", 5)          # big -> pending review
    await request("Devon Lane", "260.00", 9)            # pending review
    w = await request("Kiran Patel", "180.00", 30)      # approved, awaiting payment
    if w is not None and w.status == "pending":
        await svc.review_withdrawal(w.id, "approved", admin.id, "Checked recent sales", "198.51.100.24")
    w = await request("Elena Rostova", "180.00", 52)    # rejected -> money back
    if w is not None and w.status == "pending":
        await svc.review_withdrawal(w.id, "rejected", admin.id, "Please wait until the refunded order clears", "198.51.100.24")
    await request("Priya Nair", "60.00", 2)             # small -> auto-approved


async def bot_burst(session, partner: Partner, link: ReferralLink) -> list[uuid.UUID]:
    """25 automated clicks from one IP within minutes (trips the fraud rules)."""
    ids = []
    ip = "185.220.101.47"
    for i in range(25):
        cid = uuid.uuid4()
        session.add(ReferralClick(
            id=cid, referral_link_id=link.id, partner_id=partner.id, ip_address=ip,
            device_info={"user_agent": UA_BOT, "device_type": "bot", "fingerprint": fingerprint_for(ip, UA_BOT)},
            source=None, clicked_at=NOW - timedelta(hours=3, minutes=25 - i), is_synthetic=False,
        ))
        ids.append(cid)
    await session.commit()
    return ids


async def main(admin_email: str, admin_password: str, seed: int) -> None:
    rng = random.Random(seed)
    async with AsyncSessionLocal() as session:
        existing = (await session.execute(select(Partner).where(Partner.email.like(f"%@{DOMAIN}")))).first()
        if existing:
            raise SystemExit("Demo partners already exist. Use a fresh database (alembic downgrade base && alembic upgrade head).")
        print("Setting up tiers and admin…")
        await ensure_tiers(session)
        admin = await ensure_admin(session, admin_email, admin_password)

        partners: dict[str, Partner] = {}
        links: dict[str, list[ReferralLink]] = {}
        print("Creating partners and their history (this takes a minute)…")
        for story in STORIES:
            p, ls, code = await create_partner(session, story, rng)
            partners[story.name] = p
            links[story.name] = ls
            n = await build_history(session, story, p, ls, code, rng)
            await withdrawals_for(session, story, p, admin, rng)
            print(f"  {story.name:<14} {n:>4} sales")
        await open_withdrawals(session, partners, admin)

    print("Training / loading AI models…")
    from app.ai.train import train_models

    registry.load_all()
    missing = tuple(m for m in registry.MODEL_NAMES if registry.get(m) is None)
    if missing:
        await asyncio.to_thread(train_models, missing, 300, 7, None)
        registry.load_all()

    print("Scoring sales for referral quality…")
    async with AsyncSessionLocal() as session:
        conv_ids = list((await session.execute(select(ReferralConversion.id).where(ReferralConversion.is_synthetic == False))).scalars())  # noqa: E712
    for cid in conv_ids:
        await ai_service.run_in_new_session(ai_service.score_referral_quality, cid)

    print("Scoring recent clicks for fraud…")
    async with AsyncSessionLocal() as session:
        recent = {}
        for click in (await session.execute(select(ReferralClick).order_by(ReferralClick.clicked_at))).scalars():
            recent[click.partner_id] = click.id  # latest click per partner
        rahul = partners["Rahul Verma"]
        burst = await bot_burst(session, rahul, links["Rahul Verma"][0])
    for cid in list(recent.values()) + burst:
        await ai_service.run_in_new_session(ai_service.score_fraud, cid)

    async with AsyncSessionLocal() as session:
        # Suspend the partner whose story ends that way (after their history).
        for story in STORIES:
            if story.final_status != "active":
                await session.execute(update(Partner).where(Partner.id == partners[story.name].id).values(status=story.final_status))
        await session.commit()

    print("Scoring churn and ranking…")
    await ai_service.score_all_active_partners(ai_service.score_churn)
    await ai_service.score_all_active_partners(ai_service.score_ranking)

    print("Scoring discovery candidates…")
    async with AsyncSessionLocal() as session:
        rows = await DiscoveryService(session).score_and_insert_candidates(
            [{"business_name": n, "category": c, "description": d} for n, c, d in CANDIDATES]
        )
        rows[-1].status = "dismissed"
        rows[1].status = "invited"
        rows[2].status = "reviewed"
        await session.commit()

    print("\nDone.")
    print(f"  Admin:    {admin_email} / {admin_password}")
    print(f"  Partners: priya@{DOMAIN} (and marcus@, elena@, …) / {PARTNER_PASSWORD}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-email", default="admin@referrai.io")
    parser.add_argument("--admin-password", default="Admin123!")
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    asyncio.run(main(args.admin_email, args.admin_password, args.seed))
