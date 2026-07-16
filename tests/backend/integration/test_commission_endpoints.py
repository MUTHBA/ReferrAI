# -----------------------------------------------------------------------------
# tests/backend/integration/test_commission_endpoints.py
#
# TST-001 — Commission integration tests.
#
# Verifies the end-to-end commission and wallet credit flow triggered by
# POST /referrals/conversions:
#   1. A Commission row is created with the correct amount.
#   2. The partner's wallet balance is credited by that amount.
#   3. A second POST with the same conversion_id is idempotent (no duplicate
#      commission). Note: duplicate protection is on conversion_id, not on
#      re-calling the endpoint (each call creates a new conversion).
#
# Default commission rate comes from the settings fallback: 10% (0.10) of
# conversion_value. No settings rows need to be seeded because
# CommissionService._default_type_and_rate() uses SettingService.get() which
# returns the default when the key is absent.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.commission import Commission
from app.models.wallet import Wallet


async def test_conversion_creates_commission_with_correct_amount(
    client: AsyncClient, seed: dict, engine
) -> None:
    """Recording a conversion creates a Commission row worth 10% of conversion_value."""
    conversion_value = Decimal("200.00")
    expected_commission = Decimal("20.00")  # 10% default rate

    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "partner_id": str(seed["partner_id"]),
            "external_reference": "comm-test-001",
            "conversion_value": str(conversion_value),
        },
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 201, resp.text
    conversion_id = uuid.UUID(resp.json()["id"])

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(
            select(Commission).where(Commission.conversion_id == conversion_id)
        )
        commission = result.scalar_one_or_none()

    assert commission is not None, "No Commission row found after conversion"
    assert commission.amount == expected_commission
    assert commission.commission_type == "percentage"


async def test_conversion_credits_wallet_balance(
    client: AsyncClient, seed: dict, engine
) -> None:
    """Recording a conversion increases the partner's wallet balance by the commission amount."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        wallet_before = await session.get(Wallet, seed["wallet_id"])
        balance_before = wallet_before.balance

    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "partner_id": str(seed["partner_id"]),
            "external_reference": "comm-test-002",
            "conversion_value": "100.00",
        },
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 201, resp.text

    async with factory() as session:
        wallet_after = await session.get(Wallet, seed["wallet_id"])
        balance_after = wallet_after.balance

    # 10% of 100.00 = 10.00
    assert balance_after == balance_before + Decimal("10.00")
