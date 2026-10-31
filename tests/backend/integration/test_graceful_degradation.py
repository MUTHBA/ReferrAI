# -----------------------------------------------------------------------------
# tests/backend/integration/test_graceful_degradation.py
#
# The core platform must keep working when AI is unavailable (CLAUDE.md):
#   * no trained model  -> conversion/commission/click still succeed and the
#     AI row is stored with score NULL + status 'model_unavailable'
#   * model crashes     -> same, with status 'error'
#   * fraud without a model still runs the deterministic rules
# These tests run with the default EMPTY model directory.
# Change: conversions post referral_code instead of partner_id (partner is derived server-side).
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select

from app.models.ai_score import AIScore
from app.models.commission import Commission
from app.models.referral import ReferralClick
from app.models.wallet import Wallet

API = "/api/v1"


async def _convert(client, seed, ref="deg-1"):
    return await client.post(
        f"{API}/referrals/conversions",
        json={"referral_code": seed["referral_code"], "external_reference": ref, "conversion_value": "100.00"},
        headers=seed["admin_headers"],
    )


async def test_conversion_and_commission_succeed_without_models(client: AsyncClient, seed: dict, session_factory) -> None:
    resp = await _convert(client, seed)
    assert resp.status_code == 201, resp.text
    conv_id = uuid.UUID(resp.json()["id"])
    async with session_factory() as s:
        commission = (await s.execute(select(Commission).where(Commission.conversion_id == conv_id))).scalar_one()
        assert commission.amount == Decimal("10.00")
        wallet = (await s.execute(select(Wallet).where(Wallet.partner_id == seed["partner_id"]))).scalar_one()
        assert wallet.balance == Decimal("10.00")
        score = (await s.execute(select(AIScore).where(AIScore.entity_id == conv_id))).scalar_one()
        assert score.score is None
        assert score.status == "model_unavailable"

    listed = (await client.get(f"{API}/referrals/conversions", headers=seed["partner_headers"])).json()
    assert listed[0]["quality_score"] is None and listed[0]["quality_status"] == "model_unavailable"


async def test_conversion_succeeds_when_model_crashes(client: AsyncClient, seed: dict, session_factory, trained_models) -> None:
    with patch("app.ai.registry.predict_proba", side_effect=RuntimeError("boom")):
        resp = await _convert(client, seed, "deg-2")
    assert resp.status_code == 201
    async with session_factory() as s:
        score = (await s.execute(select(AIScore).where(AIScore.entity_id == uuid.UUID(resp.json()["id"])))).scalar_one()
        assert score.score is None and score.status == "error"


async def test_click_tracking_survives_fraud_scoring_failure(client: AsyncClient, seed: dict, session_factory) -> None:
    with patch("app.services.ai_service.load_fraud_inputs", side_effect=RuntimeError("boom")):
        resp = await client.get(f"/r/{seed['link_slug']}", follow_redirects=False)
    assert resp.status_code == 302
    async with session_factory() as s:
        assert (await s.execute(select(ReferralClick))).scalar_one() is not None


async def test_fraud_rules_still_score_without_model(client: AsyncClient, seed: dict, session_factory) -> None:
    resp = await client.get(f"/r/{seed['link_slug']}", follow_redirects=False)
    assert resp.status_code == 302
    async with session_factory() as s:
        row = (
            await s.execute(select(AIScore).where(AIScore.score_type == "fraud_risk", AIScore.entity_type == "partner"))
        ).scalar_one()
        assert row.status == "ok" and row.model_version == "rules-only"
        assert row.score == Decimal("0.00")


async def test_churn_batch_without_model_stores_null(client: AsyncClient, seed: dict, session_factory) -> None:
    from datetime import datetime, timedelta, timezone

    from app.models.partner import Partner

    async with session_factory() as s:
        (await s.get(Partner, seed["partner_id"])).created_at = datetime.now(timezone.utc) - timedelta(days=200)
        await s.commit()
    resp = await client.post(f"{API}/admin/run-churn-scoring", headers=seed["admin_headers"])
    assert resp.status_code == 200 and resp.json()["partners_scored"] == 1
    async with session_factory() as s:
        row = (await s.execute(select(AIScore).where(AIScore.score_type == "churn_risk"))).scalar_one()
        assert row.score is None and row.status == "model_unavailable"
