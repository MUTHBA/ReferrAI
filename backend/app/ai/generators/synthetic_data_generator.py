# -----------------------------------------------------------------------------
# backend/app/ai/generators/synthetic_data_generator.py
#
# Generates synthetic training data for the AI scoring models. Every method
# commits its own transaction so the caller can use the returned objects
# immediately without re-querying. A single bcrypt hash is computed once at
# module load (not per user) so generate_partners(n=1000) stays fast. All
# Partner rows, their clicks, and their conversions carry is_synthetic=True so
# analytical queries and dashboards can exclude them with a simple filter.
# -----------------------------------------------------------------------------

import math
import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from faker import Faker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.partner import Partner
from app.models.referral import ReferralClick, ReferralConversion, ReferralLink
from app.models.user import User
from app.models.wallet import Wallet

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_faker = Faker()

# Computed once at module import (~100 ms). All synthetic users share this
# hash — they are never meant to be logged into interactively.
_SYNTHETIC_PASSWORD_HASH: str = hash_password("synthetic-data-placeholder")

_PARTNER_CATEGORIES = [
    "e-commerce",
    "saas",
    "fintech",
    "health & wellness",
    "education",
    "travel",
    "food & beverage",
    "retail",
    "professional services",
    "media & content",
]

# Realistic but fixed pool of user-agent strings used for clean clicks.
# A fixed pool (rather than purely random) means feature engineering for
# the fraud model can count distinct UAs per IP without noise.
_CLEAN_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

_DEVICE_TYPES = ["desktop", "mobile", "tablet"]
_BROWSERS = ["Chrome", "Firefox", "Safari", "Edge"]
_OS_TYPES = ["Windows", "macOS", "iOS", "Android", "Linux"]

# None weighted higher to simulate organic/direct traffic
_UTM_SOURCES = [
    None, None, None,
    "google", "facebook", "email", "twitter", "linkedin", "instagram",
]

# Burst window for fraud velocity simulation: all clicks in a burst land
# within this many seconds of each other.
_FRAUD_BURST_WINDOW_SECONDS = 300  # 5 minutes
_FRAUD_BURST_SIZE = 5              # clicks per shared IP/device fingerprint


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _synthetic_email() -> str:
    """Unique email that is obviously synthetic and will never collide."""
    first = _faker.first_name().lower()
    last = _faker.last_name().lower()
    return f"{first}.{last}.{uuid.uuid4().hex[:8]}@synth.example.com"


def _random_past_datetime(days: int = 90) -> datetime:
    offset = timedelta(
        days=random.randint(0, days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return datetime.now(timezone.utc) - offset


def _clean_device_info() -> dict[str, Any]:
    return {
        "user_agent": random.choice(_CLEAN_USER_AGENTS),
        "device_type": random.choice(_DEVICE_TYPES),
        "browser": random.choice(_BROWSERS),
        "os": random.choice(_OS_TYPES),
    }


# ---------------------------------------------------------------------------
# Generator class
# ---------------------------------------------------------------------------

class SyntheticDataGenerator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # REF-001 equivalent: generate_partners
    # ------------------------------------------------------------------

    async def generate_partners(self, n: int) -> list[Partner]:
        """Create n User + Partner + Wallet triplets with realistic fake data.

        SQLAlchemy's unit-of-work flush resolves FK order automatically
        (users → partners → wallets) so we can add all rows before committing.
        """
        partners: list[Partner] = []

        for _ in range(n):
            user_id = uuid.uuid4()
            partner_id = uuid.uuid4()

            user = User(
                id=user_id,
                email=_synthetic_email(),
                password_hash=_SYNTHETIC_PASSWORD_HASH,
                role="partner",
                is_active=True,
            )

            partner = Partner(
                id=partner_id,
                user_id=user_id,
                name=_faker.name(),
                business_name=_faker.company(),
                category=random.choice(_PARTNER_CATEGORIES),
                email=user.email,
                # Faker phone numbers can exceed VARCHAR(50) — truncate safely
                phone=_faker.phone_number()[:50],
                status=random.choices(
                    ["active", "pending"], weights=[85, 15], k=1
                )[0],
                is_synthetic=True,
            )

            wallet = Wallet(
                id=uuid.uuid4(),
                partner_id=partner_id,
            )

            self.session.add(user)
            self.session.add(partner)
            self.session.add(wallet)
            partners.append(partner)

        await self.session.commit()
        return partners

    # ------------------------------------------------------------------
    # generate_clicks
    # ------------------------------------------------------------------

    async def generate_clicks(
        self, partner_ids: list[uuid.UUID], n: int
    ) -> list[ReferralClick]:
        """Create n ReferralClick rows spread across the given partners.

        ReferralClick's CHECK constraint requires referral_link_id IS NOT NULL
        OR referral_code_id IS NOT NULL — partner_id alone is insufficient.
        We therefore create one synthetic ReferralLink per unique partner_id
        before inserting clicks, satisfying the constraint without touching the
        schema.
        """
        unique_pids = list(set(partner_ids))

        # Build one synthetic link per unique partner for this batch
        link_map: dict[uuid.UUID, uuid.UUID] = {}
        for pid in unique_pids:
            link_id = uuid.uuid4()
            slug = f"syn-{secrets.token_urlsafe(6)}"
            link = ReferralLink(
                id=link_id,
                partner_id=pid,
                slug=slug,
                destination_url=f"https://synth.example.com/ref/{pid}",
                is_active=True,
            )
            self.session.add(link)
            link_map[pid] = link_id

        clicks: list[ReferralClick] = []
        for _ in range(n):
            pid = random.choice(partner_ids)
            click = ReferralClick(
                id=uuid.uuid4(),
                referral_link_id=link_map[pid],
                referral_code_id=None,
                partner_id=pid,
                ip_address=_faker.ipv4(),
                device_info=_clean_device_info(),
                source=random.choice(_UTM_SOURCES),
                clicked_at=_random_past_datetime(days=90),
                is_synthetic=True,
            )
            self.session.add(click)
            clicks.append(click)

        await self.session.commit()
        return clicks

    # ------------------------------------------------------------------
    # generate_conversions
    # ------------------------------------------------------------------

    async def generate_conversions(
        self, click_ids: list[uuid.UUID], n: int
    ) -> list[ReferralConversion]:
        """Create n ReferralConversion rows referencing the supplied clicks.

        Loads all referenced clicks in one query to avoid n+1 lookups when
        resolving partner_id and referral_link_id for each conversion row.
        """
        result = await self.session.execute(
            select(ReferralClick).where(ReferralClick.id.in_(click_ids))
        )
        click_map: dict[uuid.UUID, ReferralClick] = {
            c.id: c for c in result.scalars().all()
        }

        conversions: list[ReferralConversion] = []
        for _ in range(n):
            cid = random.choice(click_ids)
            click = click_map[cid]
            conv = ReferralConversion(
                id=uuid.uuid4(),
                partner_id=click.partner_id,
                click_id=cid,
                referral_link_id=click.referral_link_id,
                referral_code_id=click.referral_code_id,
                conversion_value=Decimal(str(round(random.uniform(10.0, 500.0), 2))),
                # Hardcoding 'last_click' for synthetic data is acceptable —
                # the attribution model is a property of a real conversion event,
                # not of the training data generator.
                attribution_model="last_click",
                is_synthetic=True,
            )
            self.session.add(conv)
            conversions.append(conv)

        await self.session.commit()
        return conversions

    # ------------------------------------------------------------------
    # generate_fraud_labelled
    # ------------------------------------------------------------------

    async def generate_fraud_labelled(
        self, click_ids: list[uuid.UUID], fraud_ratio: float
    ) -> dict[str, list[uuid.UUID]]:
        """Rewrite a fraction of existing clicks to exhibit a fraud velocity pattern.

        The fraud PATTERN (not just the label) is what the Isolation Forest
        (AI-FRD-002) will learn to detect: a small pool of IP addresses each
        associated with many clicks sharing an identical device fingerprint,
        all landing within a tight time window (_FRAUD_BURST_WINDOW_SECONDS).
        Clean clicks retain diverse IPs, varied user-agents, and natural
        temporal spacing.

        Ground-truth labels are stored as "_synthetic_fraud_label": true/false
        in device_info (JSONB) rather than a new column because:
          - device_info is the only existing flexible-data field on
            referral_clicks, matching DATABASE_DESIGN.md's stated use of JSONB
            for "variable data";
          - adding a boolean column would require a new migration, which is
            out of scope for AI-DATA-001;
          - JSONB metadata doesn't affect any production query that filters on
            real columns (ip_address, partner_id, clicked_at), so there is no
            risk of contaminating operational data.
        """
        if not 0.0 <= fraud_ratio <= 1.0:
            raise ValueError("fraud_ratio must be between 0.0 and 1.0")

        shuffled = list(click_ids)
        random.shuffle(shuffled)
        n_fraud = int(len(shuffled) * fraud_ratio)
        fraud_ids = shuffled[:n_fraud]
        clean_ids = shuffled[n_fraud:]

        result = await self.session.execute(
            select(ReferralClick).where(ReferralClick.id.in_(click_ids))
        )
        click_map: dict[uuid.UUID, ReferralClick] = {
            c.id: c for c in result.scalars().all()
        }

        # --- Label clean clicks (device_info update only, no IP/time change) ---
        for cid in clean_ids:
            click = click_map[cid]
            info: dict[str, Any] = dict(click.device_info or {})
            info["_synthetic_fraud_label"] = False
            click.device_info = info

        # --- Rewrite fraud clicks with burst velocity patterns ---
        # Clicks are grouped into bursts of _FRAUD_BURST_SIZE. Every click
        # within a burst shares an IP address and device fingerprint, and
        # their clicked_at values are compressed into a _FRAUD_BURST_WINDOW_SECONDS
        # window starting from a random anchor in the past. This mimics
        # automated referral-farming bots that fire many clicks rapidly from
        # a single device/IP combination.
        fraud_clicks = [click_map[cid] for cid in fraud_ids]
        n_bursts = max(1, math.ceil(len(fraud_clicks) / _FRAUD_BURST_SIZE))

        burst_params: list[tuple[str, str, datetime]] = [
            (
                # RFC-1918 private IP range makes fraud IPs visually distinct
                # from the faker.ipv4() public IPs on clean clicks.
                f"10.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}",
                f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) FraudBot/{random.randint(1, 99)}.0",
                datetime.now(timezone.utc) - timedelta(days=random.randint(1, 60)),
            )
            for _ in range(n_bursts)
        ]

        for i, click in enumerate(fraud_clicks):
            burst_idx = i // _FRAUD_BURST_SIZE
            fraud_ip, fraud_ua, burst_anchor = burst_params[burst_idx]
            click.ip_address = fraud_ip
            click.clicked_at = burst_anchor + timedelta(
                seconds=random.randint(0, _FRAUD_BURST_WINDOW_SECONDS)
            )
            click.device_info = {
                "user_agent": fraud_ua,
                "device_type": "desktop",
                "browser": "Chrome",
                "os": "Windows",
                "_synthetic_fraud_label": True,
            }

        await self.session.commit()
        return {
            "fraud_click_ids": fraud_ids,
            "clean_click_ids": clean_ids,
        }

    # ------------------------------------------------------------------
    # generate_churn_labelled
    # ------------------------------------------------------------------

    async def generate_churn_labelled(
        self, partner_ids: list[uuid.UUID], churn_ratio: float
    ) -> dict[str, list[uuid.UUID]]:
        """Partition partner_ids into churned and active subsets.

        No DB writes are performed here. Churn is expressed behaviourally
        through data absence: the caller should invoke generate_clicks() only
        for the active_partner_ids, leaving churned partners with no recent
        activity. Features like "days_since_last_referral" will then reflect
        churn organically from the data itself.

        An explicit churn label column on the partners table was deliberately
        not added here because:
          - it would require a new Alembic migration (out of scope for
            AI-DATA-001);
          - unlike fraud (which needs ground truth persisted for later recall
            evaluation), churn ground truth is already derivable from the
            absence of click/conversion rows for a given partner;
          - the caller (AI-CHURN-001's evaluation harness) can track which
            partner_ids were generated as churned using the returned dict,
            without persisting that fact on the partner row.
        """
        if not 0.0 <= churn_ratio <= 1.0:
            raise ValueError("churn_ratio must be between 0.0 and 1.0")

        shuffled = list(partner_ids)
        random.shuffle(shuffled)
        n_churned = int(len(shuffled) * churn_ratio)

        return {
            "churned_partner_ids": shuffled[:n_churned],
            "active_partner_ids": shuffled[n_churned:],
        }
