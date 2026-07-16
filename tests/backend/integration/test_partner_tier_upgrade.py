# -----------------------------------------------------------------------------
# tests/backend/integration/test_partner_tier_upgrade.py
#
# PRT-003 — automatic tier upgrade integration test.
#
# Verifies that evaluate_tier_upgrade() is called by record_conversion() and
# actually mutates the partner's tier_id when the cumulative conversion count
# crosses a tier threshold.
#
# Tier setup in this test:
#   Bronze (rank 1): min 0 conversions  — assigned on the very first conversion
#   Silver (rank 2): min 3 conversions  — assigned once count reaches 3
#
# Confirms upgrade-only behaviour: after reaching Silver no further change
# occurs (rank_order guard in evaluate_tier_upgrade prevents downgrade).
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.partner import Partner, PartnerTier


async def test_tier_upgrades_after_crossing_threshold(
    client: AsyncClient, seed: dict, engine
) -> None:
    """Partner tier advances from None → Bronze → Silver as conversions accumulate."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Seed Bronze and Silver tiers directly into the test DB.
    bronze_id = uuid.uuid4()
    silver_id = uuid.uuid4()
    async with factory() as session:
        session.add(PartnerTier(
            id=bronze_id,
            name="Bronze",
            rank_order=1,
            min_referral_count=0,
            min_revenue_contribution=Decimal("0.00"),
            commission_type="percentage",
            commission_value=Decimal("5.00"),
        ))
        session.add(PartnerTier(
            id=silver_id,
            name="Silver",
            rank_order=2,
            min_referral_count=3,
            min_revenue_contribution=Decimal("0.00"),
            commission_type="percentage",
            commission_value=Decimal("8.00"),
        ))
        await session.commit()

    _conv_counter = {"n": 0}

    async def record_conversion() -> None:
        _conv_counter["n"] += 1
        resp = await client.post(
            "/api/v1/referrals/conversions",
            json={
                "partner_id": str(seed["partner_id"]),
                "external_reference": f"tier-test-{_conv_counter['n']}",
                "conversion_value": "100.00",
            },
            headers=seed["admin_headers"],
        )
        assert resp.status_code == 201, resp.text

    async def get_partner_tier_id() -> uuid.UUID | None:
        async with factory() as session:
            p = await session.get(Partner, seed["partner_id"])
            return p.tier_id

    # Before any conversion: partner has no tier.
    assert await get_partner_tier_id() is None

    # Conversion 1: total_referral_count=1 → qualifies for Bronze (min 0),
    # rank 1 > current rank 0 → upgrades to Bronze.
    await record_conversion()
    assert str(await get_partner_tier_id()) == str(bronze_id), "Expected Bronze after 1st conversion"

    # Conversion 2: total_referral_count=2 → Bronze still qualifies but rank
    # unchanged (1 not > 1); Silver needs 3 → no change.
    await record_conversion()
    assert str(await get_partner_tier_id()) == str(bronze_id), "Tier must not change at count=2"

    # Conversion 3: total_referral_count=3 → Silver now qualifies, rank 2 > 1
    # → upgrades to Silver.
    await record_conversion()
    assert str(await get_partner_tier_id()) == str(silver_id), "Expected Silver after 3rd conversion"

    # Additional conversion: already at Silver (rank 2), no higher tier exists
    # → tier stays Silver (no downgrade).
    await record_conversion()
    assert str(await get_partner_tier_id()) == str(silver_id), "Tier must not change beyond Silver"
