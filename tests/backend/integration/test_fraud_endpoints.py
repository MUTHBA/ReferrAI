# -----------------------------------------------------------------------------
# tests/backend/integration/test_fraud_endpoints.py
#
# AI-FRD-005 — Fraud flag review queue endpoint integration tests.
#
# Covers:
#   - GET /fraud-flags (no ?status) returns only pending_review flags (default)
#   - GET /fraud-flags?status=confirmed returns only confirmed flags
#   - PATCH confirmed: transitions status, stamps reviewer/reviewed_at, and
#     writes an audit_logs row with action="fraud_flag.confirmed"
#   - PATCH dismissed: transitions status correctly
#   - PATCH on an already-reviewed flag returns 409 Conflict
#   - PATCH on a nonexistent flag id returns 404
#   - Non-admin (partner JWT) receives 403 on GET /fraud-flags
#   - Non-admin (partner JWT) receives 403 on PATCH /fraud-flags/{id}
#
# Fraud flags are seeded directly via SQLAlchemy (same pattern as
# test_wallet_endpoints.py) because the full AI scoring pipeline is out of
# scope for endpoint integration tests.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.ai_score import AIScore
from app.models.audit_log import AuditLog
from app.models.fraud_flag import FraudFlag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


async def _seed_flag(
    engine,
    partner_id: uuid.UUID,
    status: str = "pending_review",
    score: float = 78.0,
) -> uuid.UUID:
    """Insert AIScore + FraudFlag rows directly; return the flag's UUID."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="partner",
            entity_id=partner_id,
            score_type="fraud_risk",
            score=Decimal(str(score)),
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


# ---------------------------------------------------------------------------
# GET /fraud-flags
# ---------------------------------------------------------------------------

async def test_get_defaults_to_pending_review(
    client: AsyncClient, seed: dict, engine
) -> None:
    """GET /fraud-flags with no ?status param returns only pending_review flags."""
    pending_id = await _seed_flag(engine, seed["partner_id"], status="pending_review")
    _confirmed_id = await _seed_flag(engine, seed["partner_id"], status="confirmed")
    headers = await _admin_headers(client)

    # No status param — should apply the pending_review default
    resp = await client.get("/api/v1/fraud-flags", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    returned_ids = {f["id"] for f in body}
    assert str(pending_id) in returned_ids, "Pending flag should be in the default response"
    for f in body:
        assert f["status"] == "pending_review", (
            f"Default listing returned a non-pending flag: {f['status']}"
        )


async def test_get_filters_by_confirmed_status(
    client: AsyncClient, seed: dict, engine
) -> None:
    """GET /fraud-flags?status=confirmed returns only confirmed flags."""
    _pending_id = await _seed_flag(engine, seed["partner_id"], status="pending_review")
    confirmed_id = await _seed_flag(engine, seed["partner_id"], status="confirmed")
    headers = await _admin_headers(client)

    resp = await client.get(
        "/api/v1/fraud-flags", params={"status": "confirmed"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    returned_ids = {f["id"] for f in body}
    assert str(confirmed_id) in returned_ids, "Confirmed flag should appear with status=confirmed"
    for f in body:
        assert f["status"] == "confirmed", (
            f"status=confirmed filter returned a non-confirmed flag: {f['status']}"
        )


async def test_get_all_returns_every_status(
    client: AsyncClient, seed: dict, engine
) -> None:
    """GET /fraud-flags?status=all returns flags of every status."""
    pending_id = await _seed_flag(engine, seed["partner_id"], status="pending_review")
    confirmed_id = await _seed_flag(engine, seed["partner_id"], status="confirmed")
    headers = await _admin_headers(client)

    resp = await client.get(
        "/api/v1/fraud-flags", params={"status": "all"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    returned_ids = {f["id"] for f in resp.json()}
    assert str(pending_id) in returned_ids
    assert str(confirmed_id) in returned_ids


# ---------------------------------------------------------------------------
# PATCH /fraud-flags/{id}
# ---------------------------------------------------------------------------

async def test_confirm_flag_updates_status_and_writes_audit_log(
    client: AsyncClient, seed: dict, engine
) -> None:
    """PATCH confirmed: status transitions and an audit_logs row is written."""
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

    # Verify audit_logs row
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "fraud_flag",
                AuditLog.entity_id == flag_id,
                AuditLog.action == "fraud_flag.confirmed",
            )
        )
        log = result.scalar_one_or_none()
    assert log is not None, "audit_logs row for fraud_flag.confirmed was not written"
    assert log.old_value == "pending_review"
    assert log.new_value == "confirmed"


async def test_dismiss_flag_updates_status(
    client: AsyncClient, seed: dict, engine
) -> None:
    """PATCH dismissed: status transitions to dismissed."""
    flag_id = await _seed_flag(engine, seed["partner_id"])
    headers = await _admin_headers(client)

    resp = await client.patch(
        f"/api/v1/fraud-flags/{flag_id}",
        json={"status": "dismissed"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "dismissed"


async def test_patch_already_reviewed_flag_returns_409(
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


async def test_patch_nonexistent_flag_returns_404(
    client: AsyncClient, seed: dict
) -> None:
    """PATCH on an ID that does not exist returns 404."""
    headers = await _admin_headers(client)

    resp = await client.patch(
        f"/api/v1/fraud-flags/{uuid.uuid4()}",
        json={"status": "confirmed"},
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# RBAC — partner role must be rejected on both endpoints
# ---------------------------------------------------------------------------

async def test_get_fraud_flags_partner_gets_403(
    client: AsyncClient, seed: dict, engine
) -> None:
    """Non-admin (partner role) receives 403 on GET /fraud-flags."""
    await _seed_flag(engine, seed["partner_id"])
    headers = await _partner_headers(client)

    resp = await client.get("/api/v1/fraud-flags", headers=headers)
    assert resp.status_code == 403, resp.text


async def test_patch_fraud_flag_partner_gets_403(
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
