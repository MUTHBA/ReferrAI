# -----------------------------------------------------------------------------
# tests/backend/unit/test_ai_units.py
#
# Pure unit tests for the AI package: device/source bucketing, fraud feature
# windows, churn feature windows, synthetic world determinism, and both
# discovery similarity back-ends (TF-IDF and a stand-in embedding model).
# -----------------------------------------------------------------------------

import uuid
from datetime import datetime, timedelta, timezone

import numpy as np

from app.ai import candidate_scoring
from app.ai.candidate_scoring import ReferencePartner, score_candidates
from app.ai.features import (
    ClickEvent,
    ConversionEvent,
    PartnerSnapshot,
    churn_features,
    fraud_features,
    source_type,
)
from app.ai.synthetic import generate_world
from app.services.referral_click_service import device_type_from_user_agent

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
P = uuid.uuid4()


def test_device_and_source_buckets() -> None:
    assert device_type_from_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5) Mobile/15E148") == "mobile"
    assert device_type_from_user_agent("Mozilla/5.0 (iPad; CPU OS 17_5)") == "tablet"
    assert device_type_from_user_agent("python-requests/2.32") == "bot"
    assert device_type_from_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64)") == "desktop"
    assert device_type_from_user_agent(None) == "unknown"
    assert [source_type(s) for s in ("google", "Newsletter-Oct", "instagram", None, "coupon")] == [
        "search", "email", "social", "direct", "other"
    ]


def _click(minutes_ago: float, ip="1.1.1.1", partner=P, fp="fp") -> ClickEvent:
    return ClickEvent(uuid.uuid4(), partner, NOW - timedelta(minutes=minutes_ago), ip, "ua", "desktop", None, fp)


def test_fraud_features_respect_windows() -> None:
    target = _click(0)
    history = [target, _click(10), _click(50), _click(90), _click(60 * 30), _click(5, ip="2.2.2.2"), _click(5, partner=uuid.uuid4())]
    f = fraud_features(target, history)
    assert f["ip_clicks_1h"] == 4  # target, 10m, 50m, other-partner same IP; 90m and 30h excluded
    assert f["partner_clicks_1h"] == 4  # target, 10m, 50m, 2.2.2.2
    assert f["partner_distinct_ips_24h"] == 2
    assert f["fingerprint_partner_spread_24h"] == 2
    assert round(np.expm1(f["seconds_since_prev_ip_click_log"])) == 300  # previous same-IP click 5 min ago
    assert fraud_features(target, []) == fraud_features(target, [target])


def test_churn_features_windows() -> None:
    partner = PartnerSnapshot(P, NOW - timedelta(days=400), 2)
    convs = [ConversionEvent(uuid.uuid4(), P, NOW - timedelta(days=d), 100.0) for d in (5, 20, 40, 100)]
    f = churn_features(partner, NOW, convs + [ConversionEvent(uuid.uuid4(), P, NOW + timedelta(days=1), 1.0)], [])
    assert f["conversions_30d"] == 2 and f["conversions_prev_30d"] == 1
    assert round(f["days_since_last_conversion"]) == 5
    assert f["days_since_last_click"] == 120  # capped, no clicks
    assert round(np.expm1(f["revenue_90d_log"])) == 300


def test_synthetic_world_is_deterministic() -> None:
    a = generate_world(n_partners=20, days=30, seed=5, end=NOW)
    b = generate_world(n_partners=20, days=30, seed=5, end=NOW)
    assert [c.event.id for c in a.clicks] == [c.event.id for c in b.clicks]
    assert any(c.fraud for c in a.clicks) and any(not c.fraud for c in a.clicks)
    assert all(not c.event.ts > a.end for c in a.conversions)


REFS = [
    ReferencePartner("Peak Fitness Coaching fitness", "fitness", 900),
    ReferencePartner("City Bike Shop sports", "sports", 100),
]
CANDS = [
    {"business_name": "Summit Fitness Coaching", "category": "fitness", "description": ""},
    {"business_name": "Luxury Cruise Deals", "category": "travel", "description": ""},
]


def test_discovery_tfidf_fallback(monkeypatch) -> None:
    monkeypatch.setattr(candidate_scoring, "_model", None)
    monkeypatch.setattr(candidate_scoring, "_model_failed", True)
    (s1, f1), (s2, f2) = score_candidates(CANDS, REFS)
    assert f1["method"] == "tfidf" and s1 > s2
    assert f1["category_fit"] == 0.9 and f2["category_fit"] == 0.0


def test_discovery_embedding_path(monkeypatch) -> None:
    class FakeModel:
        def encode(self, texts, normalize_embeddings=True, batch_size=64):
            vecs = np.array([[1.0 if "fitness" in t.lower() else 0.0, 1.0 if "cruise" in t.lower() else 0.0, 0.1] for t in texts])
            return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

    monkeypatch.setattr(candidate_scoring, "_model", FakeModel())
    (s1, f1), (s2, _) = score_candidates(CANDS, REFS)
    assert f1["method"] == "embeddings" and s1 > s2
    assert score_candidates(CANDS, [])[0][0] is None
