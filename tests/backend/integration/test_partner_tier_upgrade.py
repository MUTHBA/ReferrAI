# -----------------------------------------------------------------------------
# tests/backend/integration/test_partner_tier_upgrade.py
#
# PRT-003 — automatic tier upgrades, and commission amounts at each tier.
#
# Tiers (Bronze is pre-seeded by conftest, like the seed migration):
#   Bronze (rank 1): min 0 conversions, 10%
#   Silver (rank 2): min 3 conversions,  15%
#
# Checks that the partner moves Bronze -> Silver when the 3rd conversion is
# recorded, that the upgrade is NOT retroactive (the 3rd conversion is still
# paid at Bronze), that later conversions are paid at Silver, that the
# upgrade is audited, and that partners never move down.
# Change: conversions post referral_code instead of partner_id (partner is derived server-side).
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.audit_log import AuditLog
from app.models.commission import Commission
from app.models.partner import Partner, PartnerTier


async def test_tier_upgrades_after_crossing_threshold(client: AsyncClient, seed: dict, engine) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    silver_id = uuid.uuid4()
    async with factory() as session:
        session.add(
            PartnerTier(
                id=silver_id,
                name="Silver",
                rank_order=2,
                min_referral_count=3,
                min_revenue_contribution=Decimal("0.00"),
                commission_type="percentage",
                commission_value=Decimal("0.15"),
            )
        )
        await session.commit()

    counter = {"n": 0}

    async def record_conversion() -> str:
        counter["n"] += 1
        resp = await client.post(
            "/api/v1/referrals/conversions",
            json={
                "referral_code": seed["referral_code"],
                "external_reference": f"tier-test-{counter['n']}",
                "conversion_value": "100.00",
            },
            headers=seed["admin_headers"],
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    async def tier_id() -> uuid.UUID | None:
        async with factory() as session:
            return (await session.get(Partner, seed["partner_id"])).tier_id

    async def commission_for(conversion_id: str) -> Decimal:
        async with factory() as session:
            return (
                await session.execute(
                    select(Commission.amount).where(Commission.conversion_id == uuid.UUID(conversion_id))
                )
            ).scalar_one()

    assert await tier_id() == seed["bronze_tier_id"]

    c1 = await record_conversion()
    c2 = await record_conversion()
    assert await tier_id() == seed["bronze_tier_id"], "Tier must not change before the threshold"
    assert await commission_for(c1) == Decimal("10.00")
    assert await commission_for(c2) == Decimal("10.00")

    c3 = await record_conversion()
    assert await tier_id() == silver_id, "Expected Silver after the 3rd conversion"
    assert await commission_for(c3) == Decimal("10.00"), "Upgrade must not be retroactive"

    c4 = await record_conversion()
    assert await commission_for(c4) == Decimal("15.00"), "Next conversion is paid at the Silver rate"
    assert await tier_id() == silver_id

    async with factory() as session:
        logs = (
            await session.execute(select(AuditLog).where(AuditLog.action == "partner.tier_upgraded"))
        ).scalars().all()
    assert len(logs) == 1
    assert logs[0].new_value["tier_name"] == "Silver"


async def test_percentage_tier_rate_must_be_a_fraction(client: AsyncClient, seed: dict) -> None:
    resp = await client.post(
        "/api/v1/tiers",
        json={"name": "Gold", "rank_order": 3, "commission_type": "percentage", "commission_value": "8"},
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 422


async def test_deleting_a_tier_in_use_is_rejected(client: AsyncClient, seed: dict) -> None:
    resp = await client.delete(f"/api/v1/tiers/{seed['bronze_tier_id']}", headers=seed["admin_headers"])
    assert resp.status_code == 409
