# -----------------------------------------------------------------------------
# tests/backend/integration/test_ai_pipeline.py
#
# End-to-end checks of the ML pipeline:
#   * feature parity: the DB loaders + feature functions used in live scoring
#     produce exactly what the pure functions used in training produce
#   * training: models train, are saved with metadata and beat a sanity floor
#   * live scoring: a conversion gets a real quality score + SHAP explanation;
#     a click burst raises exactly ONE pending fraud flag and never suspends
#   * churn/ranking batches, the admin training endpoint, synthetic data
#     insertion, and discovery scoring
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import func, select

from app.ai import registry
from app.ai.features import (
    ClickEvent,
    ConversionEvent,
    churn_features,
    fingerprint_for,
    fraud_features,
    load_churn_inputs,
    load_fraud_inputs,
    load_quality_inputs,
    quality_features,
)
from app.models.ai_score import AIScore
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner
from app.models.referral import ReferralClick, ReferralConversion
from app.services import ai_service, model_training_service

API = "/api/v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _clicks(session_factory, seed, specs, base=None) -> list[uuid.UUID]:
    """specs: list of (ip, user_agent, device_type, source, age) tuples."""
    base = base or _now()
    ids = []
    async with session_factory() as s:
        for ip, ua, device, source, age in specs:
            cid = uuid.uuid4()
            s.add(
                ReferralClick(
                    id=cid, referral_link_id=seed["link_id"], partner_id=seed["partner_id"], ip_address=ip,
                    device_info={"user_agent": ua, "device_type": device, "fingerprint": fingerprint_for(ip, ua)},
                    source=source, clicked_at=base - age, is_synthetic=False,
                )
            )
            ids.append(cid)
        await s.commit()
    return ids


# ---------------------------------------------------------------------------
# Feature parity
# ---------------------------------------------------------------------------
async def test_db_feature_loaders_match_pure_functions(seed: dict, session_factory) -> None:
    specs = [("10.0.0.1", "Mozilla/5.0", "desktop", "google", timedelta(minutes=m)) for m in (50, 30, 5)]
    specs += [("10.0.0.2", "python-requests/2", "bot", None, timedelta(hours=3))]
    specs += [("10.0.0.1", "Mozilla/5.0", "desktop", "google", timedelta(days=3))]  # outside 24h window
    base = _now()
    ids = await _clicks(session_factory, seed, specs, base)
    events = [
        ClickEvent(id=i, partner_id=seed["partner_id"], ts=base - age, ip=ip, user_agent=ua, device_type=d, source=src,
                   fingerprint=fingerprint_for(ip, ua))
        for i, (ip, ua, d, src, age) in zip(ids, specs)
    ]

    async with session_factory() as s:
        click, history = await load_fraud_inputs(s, ids[2])
    db_f = fraud_features(click, history)
    pure_f = fraud_features(events[2], events)
    assert db_f == pure_f
    assert db_f["ip_clicks_1h"] == 3 and db_f["partner_distinct_ips_24h"] == 2

    conv_id = uuid.uuid4()
    async with session_factory() as s:
        s.add(ReferralConversion(id=conv_id, partner_id=seed["partner_id"], click_id=ids[2], referral_link_id=seed["link_id"],
                                 external_reference="parity", conversion_value=Decimal("80.00"), attribution_model="last_click",
                                 converted_at=_now(), is_synthetic=False))
        await s.commit()
    async with session_factory() as s:
        conv, qclick, partner, prior = await load_quality_inputs(s, conv_id)
        churn_partner, convs, clicks = await load_churn_inputs(s, seed["partner_id"], _now())
    qf = quality_features(conv, qclick, partner, prior)
    assert qf["source_type"] == "search" and qf["device_type"] == "desktop" and qf["has_click"] == 1.0
    assert qf == quality_features(ConversionEvent(conv_id, seed["partner_id"], conv.ts, 80.0, ids[2]), events[2], partner, 0)
    cf = churn_features(churn_partner, _now(), convs, clicks)
    assert cf["conversions_30d"] == 1 and cf["clicks_30d"] == 5


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
async def test_trained_models_have_metadata_and_signal(trained_models) -> None:
    info = {m["name"]: m for m in registry.describe()}
    assert all(info[n]["trained"] for n in ("quality", "fraud", "churn"))
    assert info["fraud"]["metrics"]["holdout"]["roc_auc"] > 0.9
    assert info["churn"]["metrics"]["holdout"]["roc_auc"] > 0.7
    assert info["quality"]["metrics"]["holdout"]["roc_auc"] > 0.6
    assert info["quality"]["features"][-2:] == ["source_type", "device_type"]


# ---------------------------------------------------------------------------
# Live scoring
# ---------------------------------------------------------------------------
async def test_conversion_gets_quality_score_with_explanation(client: AsyncClient, seed: dict, session_factory, trained_models) -> None:
    await _clicks(session_factory, seed, [("203.0.113.9", "Mozilla/5.0 (Windows NT 10.0)", "desktop", "newsletter", timedelta(hours=4))])
    resp = await client.post(
        f"{API}/referrals/conversions",
        json={"partner_id": str(seed["partner_id"]), "external_reference": "q-1", "conversion_value": "150.00"},
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 201
    async with session_factory() as s:
        row = (await s.execute(select(AIScore).where(AIScore.entity_id == uuid.UUID(resp.json()["id"])))).scalar_one()
    assert row.status == "ok" and row.score is not None and 0 <= row.score <= 100
    assert row.model_version.startswith("quality-")
    assert row.contributing_factors["method"] == "shap"
    assert row.contributing_factors["inputs"]["source_type"] == "email"
    assert "Referral quality" in row.explanation

    partner_view = (await client.get(f"{API}/ai-scores/{resp.json()['id']}?score_type=quality", headers=seed["partner_headers"])).json()
    assert partner_view["score"] == float(row.score)


async def test_click_burst_raises_one_flag_and_never_suspends(client: AsyncClient, seed: dict, session_factory, trained_models) -> None:
    for _ in range(30):
        r = await client.get(f"/r/{seed['link_slug']}", headers={"user-agent": "python-requests/2.32"}, follow_redirects=False)
        assert r.status_code == 302
    async with session_factory() as s:
        flags = (await s.execute(select(FraudFlag))).scalars().all()
        partner = await s.get(Partner, seed["partner_id"])
        top = (
            await s.execute(select(func.max(AIScore.score)).where(AIScore.score_type == "fraud_risk", AIScore.entity_type == "partner"))
        ).scalar_one()
    assert len(flags) == 1, "one open flag per partner per 24h"
    assert flags[0].status == "pending_review" and flags[0].referral_click_id is not None
    assert partner.status == "active", "AI must never suspend a partner"
    assert top > 70

    queue = (await client.get(f"{API}/fraud-flags", headers=seed["admin_headers"])).json()
    assert len(queue) == 1 and queue[0]["score"] > 70
    assert "ml_score" in queue[0]["contributing_factors"]
    async with session_factory() as s:
        rules_hit = (
            await s.execute(select(AIScore).where(AIScore.score_type == "fraud_risk", AIScore.entity_type == "partner"))
        ).scalars().all()
    assert any("clicks_per_hour_exceeded" in r.contributing_factors["triggered_rules"] for r in rules_hit)


async def _age_partner(session_factory, seed, days: int) -> None:
    async with session_factory() as s:
        (await s.get(Partner, seed["partner_id"])).created_at = _now() - timedelta(days=days)
        await s.commit()


async def test_new_partner_churn_is_insufficient_data(client: AsyncClient, seed: dict, session_factory, trained_models) -> None:
    await client.post(f"{API}/admin/run-churn-scoring", headers=seed["admin_headers"])
    async with session_factory() as s:
        row = (await s.execute(select(AIScore).where(AIScore.score_type == "churn_risk"))).scalar_one()
    assert row.score is None and row.status == "insufficient_data"


async def test_churn_and_ranking_batches(client: AsyncClient, seed: dict, session_factory, trained_models) -> None:
    await _age_partner(session_factory, seed, 200)
    await _clicks(session_factory, seed, [("192.0.2.1", "Mozilla/5.0", "desktop", None, timedelta(days=40))])
    h = seed["admin_headers"]
    assert (await client.post(f"{API}/admin/run-churn-scoring", headers=h)).json()["partners_scored"] == 1
    assert (await client.post(f"{API}/admin/run-ranking", headers=h)).json()["partners_scored"] == 1
    async with session_factory() as s:
        churn = (await s.execute(select(AIScore).where(AIScore.score_type == "churn_risk"))).scalar_one()
        rank = (await s.execute(select(AIScore).where(AIScore.score_type == "ranking"))).scalar_one()
    assert churn.status == "ok" and churn.score > 50, "inactive for 40 days -> high churn risk"
    assert rank.score is not None and "quality" in rank.contributing_factors["neutral_defaults"]
    partners = (await client.get(f"{API}/partners?sort=rank", headers=h)).json()
    assert partners[0]["churn_score"] == float(churn.score)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------
async def test_training_endpoint(client: AsyncClient, seed: dict, tmp_path, monkeypatch) -> None:
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "AI_MODEL_DIR", str(tmp_path))
    h = seed["admin_headers"]
    before = (await client.get(f"{API}/admin/ai/models", headers=h)).json()
    assert not any(m["trained"] for m in before["available_models"])

    resp = await client.post(f"{API}/admin/ai/train", json={"models": ["churn"], "n_partners": 60}, headers=h)
    assert resp.status_code == 202 and resp.json()["state"] == "running"
    await model_training_service.wait()
    after = (await client.get(f"{API}/admin/ai/models", headers=h)).json()
    assert after["state"] == "succeeded", after
    assert {m["name"]: m["trained"] for m in after["available_models"]}["churn"] is True
    assert (await client.post(f"{API}/admin/ai/train", headers=seed["partner_headers"])).status_code == 403


async def test_synthetic_data_is_inserted_and_hidden(client: AsyncClient, seed: dict, session_factory) -> None:
    h = seed["admin_headers"]
    resp = await client.post(
        f"{API}/admin/synthetic-data",
        json={"num_partners": 12, "num_clicks_per_partner": 30, "num_conversions": 50, "fraud_ratio": 0.2, "churn_ratio": 0.3},
        headers=h,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["partners_created"] == 12 and body["clicks_created"] > 0
    async with session_factory() as s:
        n = (await s.execute(select(func.count()).select_from(Partner).where(Partner.is_synthetic == True))).scalar_one()  # noqa: E712
        assert n == 12
    partners = (await client.get(f"{API}/partners", headers=h)).json()
    assert len(partners) == 1
    dash = (await client.get(f"{API}/dashboard/admin", headers=h)).json()
    assert dash["kpis"]["total_conversions"] == 0


async def test_discovery_scores_against_best_partners(client: AsyncClient, seed: dict, session_factory) -> None:
    async with session_factory() as s:
        p = await s.get(Partner, seed["partner_id"])
        p.business_name, p.category, p.total_revenue_contribution = "Peak Fitness Coaching", "fitness", Decimal("5000")
        await s.commit()
    h = seed["admin_headers"]
    resp = await client.post(
        f"{API}/admin/discovery/candidates",
        json={"candidates": [
            {"business_name": "Summit Fitness Studio", "category": "fitness", "description": "personal training and coaching"},
            {"business_name": "Ocean Cruise Deals", "category": "travel", "description": "discount cruises"},
        ]},
        headers=h,
    )
    assert resp.status_code == 201
    rows = resp.json()
    assert rows[0]["candidate_name"] == "Summit Fitness Studio"
    assert rows[0]["potential_score"] > rows[1]["potential_score"]
    assert rows[0]["score_factors"]["category_fit"] == 1.0
    listed = (await client.get(f"{API}/admin/discovery/candidates", headers=h)).json()
    assert [r["candidate_name"] for r in listed] == [r["candidate_name"] for r in rows]
