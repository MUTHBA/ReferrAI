# -----------------------------------------------------------------------------
# tests/backend/integration/test_fraud_endpoints.py
#
# AI-FRD-005 — Fraud flag review queue endpoint integration tests.
#
# Covers:
#   - GET /fraud-flags?status=pending_review returns only pending flags
#   - PATCH /fraud-flags/{id} with status=confirmed transitions the flag
#   - PATCH /fraud-flags/{id} with status=dismissed transitions the flag
#   - Non-admin (partner JWT) receives 403 on both endpoints
#
# Fraud flags are seeded directly via SQLAlchemy (same approach as
# test_wallet_endpoints.py) because triggering the full AI scoring pipeline
# is out of scope for endpoint integration tests.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.ai_score import AIScore
from app.models.fraud_flag import FraudFlag


async def _admin_headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.referrai", "password": "x"},
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _partner_headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "partner@test.referrai", "password": "x"},
    )
    assert resp.status_code == 200, f"Partner login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _seed_flag(engine, partner_id: uuid.UUID, status: str = "pending_review") -> uuid.UUID:
    """Insert AIScore + FraudFlag rows directly; return flag id."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="partner",
            entity_id=partner_id,
            score_type="fraud_risk",
            score=Decimal("78.00"),
            explanation="Fraud risk flagged due to rules: clicks_per_hour_exceeded.",
            contributing_factors={
                "triggered_rules": ["clicks_per_hour_exceeded"],
                "ml_score": 48.0,
            },
            model_version="1.0",
            is_synthetic=False,
        )
        session.add(ai_score)
        await session.flush()

        flag = FraudFlag(
            id=uuid.uuid4(),
            partner_id=partner_id,
            ai_score_id=ai_score.id,
            status=status,
        )
        session.add(flag)
        await session.commit()
        return flag.id


async def test_list_pending_fraud_flags(
    client: AsyncClient, seed: dict, engine
) -> None:
    """GET /fraud-flags?status=pending_review returns the seeded pending flag."""
    flag_id = await _seed_flag(engine, seed["partner_id"])
    headers = await _admin_headers(client)

    resp = await client.get("/api/v1/fraud-flags", params={"status": "pending_review"}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) >= 1

    ids = [f["id"] for f in body]
    assert str(flag_id) in ids

    flag = next(f for f in body if f["id"] == str(flag_id))
    assert flag["status"] == "pending_review"
    assert flag["partner_name"] == "Test Partner"
    assert flag["score"] == 78.0
    assert "clicks_per_hour_exceeded" in flag["explanation"]
    assert "clicks_per_hour_exceeded" in flag["contributing_factors"]["triggered_rules"]


async def test_confirm_fraud_flag(
    client: AsyncClient, seed: dict, engine
) -> None:
    """PATCH /fraud-flags/{id} with status=confirmed transitions the flag."""
    flag_id = await _seed_flag(engine, seed["partner_id"])
    headers = await _admin_headers(client)

    resp = await client.patch(
        f"/api/v1/fraud-flags/{flag_id}",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "confirmed"
    assert body["reviewed_by"] is not None
    assert body["reviewed_at"] is not None


async def test_dismiss_fraud_flag(
    client: AsyncClient, seed: dict, engine
) -> None:
    """PATCH /fraud-flags/{id} with status=dismissed transitions the flag."""
    flag_id = await _seed_flag(engine, seed["partner_id"])
    headers = await _admin_headers(client)

    resp = await client.patch(
        f"/api/v1/fraud-flags/{flag_id}",
        json={"status": "dismissed"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "dismissed"


async def test_fraud_flag_already_reviewed_returns_409(
    client: AsyncClient, seed: dict, engine
) -> None:
    """PATCH on an already-reviewed flag returns 409 Conflict."""
    flag_id = await _seed_flag(engine, seed["partner_id"], status="confirmed")
    headers = await _admin_headers(client)

    resp = await client.patch(
        f"/api/v1/fraud-flags/{flag_id}",
        json={"status": "dismissed"},
        headers=headers,
    )
    assert resp.status_code == 409, resp.text


async def test_fraud_flags_rbac_partner_gets_403(
    client: AsyncClient, seed: dict, engine
) -> None:
    """Non-admin (partner role) receives 403 on GET /fraud-flags."""
    await _seed_flag(engine, seed["partner_id"])
    headers = await _partner_headers(client)

    resp = await client.get("/api/v1/fraud-flags", headers=headers)
    assert resp.status_code == 403, resp.text


async def test_fraud_flag_patch_rbac_partner_gets_403(
    client: AsyncClient, seed: dict, engine
) -> None:
    """Non-admin (partner role) receives 403 on PATCH /fraud-flags/{id}."""
    flag_id = await _seed_flag(engine, seed["partner_id"])
    headers = await _partner_headers(client)

    resp = await client.patch(
        f"/api/v1/fraud-flags/{flag_id}",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert resp.status_code == 403, resp.text
