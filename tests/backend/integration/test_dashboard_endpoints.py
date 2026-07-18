# -----------------------------------------------------------------------------
# tests/backend/integration/test_dashboard_endpoints.py
#
# RPT-001 / AI-CHURN-004 — Admin dashboard endpoint integration tests.
#
# Covers:
#   - GET /dashboard/admin returns 200 with expected KPI shape
#   - churn_alert_count reflects real churn_risk scores above the threshold
#   - churn_at_risk_partners list contains partners above threshold only
#   - Partners below the threshold are excluded from both count and list
#   - Non-admin (partner role) receives 403
#
# churn.alert_threshold is not seeded into the settings table in the test
# fixture, so the service falls back to the hardcoded default of 70.0.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.ai_score import AIScore


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


async def _seed_churn_score(engine, partner_id: uuid.UUID, score: float) -> None:
    """Insert a single non-synthetic churn_risk AIScore for the given partner."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        row = AIScore(
            id=uuid.uuid4(),
            entity_type="partner",
            entity_id=partner_id,
            score_type="churn_risk",
            score=Decimal(str(score)),
            explanation="Churn risk calculated by IsolationForest.",
            contributing_factors={},
            model_version="1.0",
            is_synthetic=False,
        )
        session.add(row)
        await session.commit()


# ---------------------------------------------------------------------------
# GET /dashboard/admin — shape and access control
# ---------------------------------------------------------------------------

async def test_admin_dashboard_returns_200(
    client: AsyncClient, seed: dict
) -> None:
    """GET /dashboard/admin returns 200 with expected top-level keys."""
    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/dashboard/admin", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "kpis" in body
    assert "volume_chart" in body
    assert "churn_at_risk_partners" in body


async def test_admin_dashboard_partner_gets_403(
    client: AsyncClient, seed: dict
) -> None:
    """Non-admin (partner role) receives 403 on GET /dashboard/admin."""
    headers = await _partner_headers(client)
    resp = await client.get("/api/v1/dashboard/admin", headers=headers)
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# churn_alert_count
# ---------------------------------------------------------------------------

async def test_churn_alert_count_zero_with_no_scores(
    client: AsyncClient, seed: dict
) -> None:
    """When no churn_risk scores exist, churn_alert_count is 0."""
    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/dashboard/admin", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["kpis"]["churn_alert_count"] == 0


async def test_churn_alert_count_reflects_above_threshold_partners(
    client: AsyncClient, seed: dict, engine
) -> None:
    """churn_alert_count = number of partners with latest churn_risk > 70 (default threshold)."""
    await _seed_churn_score(engine, seed["partner_id"], score=85.0)  # above threshold
    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/dashboard/admin", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["kpis"]["churn_alert_count"] == 1


async def test_churn_alert_count_excludes_below_threshold_partners(
    client: AsyncClient, seed: dict, engine
) -> None:
    """Partners with churn_risk <= 70 are not counted in churn_alert_count."""
    await _seed_churn_score(engine, seed["partner_id"], score=50.0)  # below threshold
    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/dashboard/admin", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["kpis"]["churn_alert_count"] == 0


# ---------------------------------------------------------------------------
# churn_at_risk_partners list
# ---------------------------------------------------------------------------

async def test_churn_at_risk_partners_contains_above_threshold_partner(
    client: AsyncClient, seed: dict, engine
) -> None:
    """churn_at_risk_partners includes the partner whose score > 70."""
    await _seed_churn_score(engine, seed["partner_id"], score=92.5)
    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/dashboard/admin", headers=headers)
    assert resp.status_code == 200, resp.text
    at_risk = resp.json()["churn_at_risk_partners"]
    assert len(at_risk) == 1
    assert at_risk[0]["partner_id"] == str(seed["partner_id"])
    assert at_risk[0]["churn_score"] == 92.5
    assert at_risk[0]["name"] == "Test Partner"


async def test_churn_at_risk_partners_empty_when_all_below_threshold(
    client: AsyncClient, seed: dict, engine
) -> None:
    """churn_at_risk_partners is empty when no partner exceeds the threshold."""
    await _seed_churn_score(engine, seed["partner_id"], score=40.0)
    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/dashboard/admin", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["churn_at_risk_partners"] == []
