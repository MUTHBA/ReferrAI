# -----------------------------------------------------------------------------
# tests/backend/integration/test_wallet_endpoints.py
#
# TST-001 — Wallet and withdrawal integration tests.
#
# Covers: GET /wallet (balance), POST /withdrawals auto-approved when amount
# is below the threshold and no fraud flag exists, and POST /withdrawals
# remaining pending when the partner has an active FraudFlag.
#
# Setup: each test first records a conversion (via admin API) to credit the
# wallet so there is sufficient balance for withdrawal requests. The fraud flag
# test additionally inserts an AIScore and FraudFlag row directly into the DB
# (mimicking what the fraud scoring background task would produce) because
# triggering the full AI scoring pipeline is out of scope for TST-001.
#
# auto_approval_threshold default: $100 (wallet_service fallback).
# min_withdrawal_amount default: $10 (wallet_service fallback).
# Commission default: 10% → $200 conversion → $20 credited to wallet.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.ai_score import AIScore
from app.models.fraud_flag import FraudFlag


async def _partner_headers(client: AsyncClient) -> dict:
    """Log in as the seeded partner and return Authorization headers."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "partner@test.referrai", "password": "x"},
    )
    assert resp.status_code == 200, f"Partner login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


_wallet_credit_counter = {"n": 0}


async def _credit_wallet(
    client: AsyncClient, seed: dict, click_id: uuid.UUID, amount: str = "200.00"
) -> None:
    """Record a conversion so the partner's wallet has funds available."""
    _wallet_credit_counter["n"] += 1
    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "click_id": str(click_id),
            "external_reference": f"wallet-test-{_wallet_credit_counter['n']}",
            "conversion_value": amount,
        },
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 201, f"Conversion failed: {resp.text}"


async def test_get_wallet_returns_balance(client: AsyncClient, seed: dict) -> None:
    """GET /wallet returns the partner's current balance."""
    headers = await _partner_headers(client)
    resp = await client.get("/api/v1/wallet", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "balance" in body
    assert float(body["balance"]) >= 0


async def test_withdrawal_auto_approved_below_threshold(
    client: AsyncClient, seed: dict, seed_click: uuid.UUID
) -> None:
    """Withdrawal below auto-approval threshold ($100) with no fraud flag is auto-approved."""
    await _credit_wallet(client, seed, seed_click, "200.00")  # credits $20 (10%)
    headers = await _partner_headers(client)

    resp = await client.post(
        "/api/v1/withdrawals",
        json={"amount": "15.00"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "approved", (
        f"Expected auto-approval but got status='{body['status']}'"
    )
    assert float(body["amount"]) == 15.00


async def test_withdrawal_blocked_by_active_fraud_flag(
    client: AsyncClient, seed: dict, seed_click: uuid.UUID, engine
) -> None:
    """Withdrawal stays 'pending' when the partner has an active fraud flag."""
    await _credit_wallet(client, seed, seed_click, "200.00")  # credits $20

    # Insert an AIScore and FraudFlag directly (mimics what score_fraud produces)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="partner",
            entity_id=seed["partner_id"],
            score_type="fraud_risk",
            score=Decimal("85.00"),
            model_version="1.0",
            is_synthetic=False,
        )
        session.add(ai_score)
        await session.flush()

        fraud_flag = FraudFlag(
            id=uuid.uuid4(),
            partner_id=seed["partner_id"],
            ai_score_id=ai_score.id,
            status="pending_review",
        )
        session.add(fraud_flag)
        await session.commit()

    headers = await _partner_headers(client)
    resp = await client.post(
        "/api/v1/withdrawals",
        json={"amount": "15.00"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending", (
        f"Expected withdrawal to be blocked (pending) due to fraud flag, "
        f"but got status='{body['status']}'"
    )


async def test_withdrawal_rejected_when_insufficient_balance(
    client: AsyncClient, seed: dict
) -> None:
    """Requesting more than the available balance returns 422."""
    # Wallet starts at $0; no conversion credited
    headers = await _partner_headers(client)
    resp = await client.post(
        "/api/v1/withdrawals",
        json={"amount": "500.00"},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert "Insufficient" in resp.json()["detail"]
