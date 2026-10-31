# -----------------------------------------------------------------------------
# backend/app/ai/train.py
#
# Trains the three models and saves them to settings.AI_MODEL_DIR.
#
#   python -m app.ai.train                 # all models, default synthetic world
#   python -m app.ai.train --models fraud --partners 500 --seed 11
#   python -m app.ai.train --if-missing     # container start: train only if absent
#   docker compose exec backend python -m app.ai.train
#
# Data: a deterministic synthetic world (app/ai/synthetic.py). Features are
# computed with the SAME functions live scoring uses (app/ai/features.py).
# Evaluation holds out 25% of PARTNERS (not rows), so a partner's behaviour
# never leaks from training into the test score. Admin fraud reviews in the
# database (confirmed/dismissed flags) are added as an extra real-world
# evaluation set when --with-reviews is used / when triggered from the API.
#
# Models
#   quality : GradientBoostingClassifier -> P(good referral) x 100
#   churn   : GradientBoostingClassifier -> P(no conversion in next 30 days) x 100
#   fraud   : IsolationForest (unsupervised) + logistic calibration of its
#             anomaly score on labelled clicks -> P(fraud) x 100
# -----------------------------------------------------------------------------

from __future__ import annotations

import argparse
import asyncio
import bisect
import hashlib
import logging
import platform
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.ai import registry
from app.ai.features import (
    CHURN_FEATURES,
    CHURN_HORIZON,
    CHURN_LOOKBACK,
    FRAUD_FEATURES,
    FRAUD_HISTORY_WINDOW,
    QUALITY_CATEGORICAL,
    QUALITY_FEATURES,
    QUALITY_NUMERIC,
    churn_features,
    fraud_features,
    quality_features,
)
from app.ai.synthetic import SyntheticWorld, generate_world

logger = logging.getLogger(__name__)
ALERT_THRESHOLD = 70.0  # used only to report precision/recall in metrics


def _is_test_partner(partner_id, test_share: float = 0.25) -> bool:
    return int(hashlib.md5(partner_id.bytes).hexdigest(), 16) % 1000 < test_share * 1000


def _baseline(df: pd.DataFrame, categorical: list[str]) -> dict:
    out = {}
    for c in df.columns:
        out[c] = df[c].mode().iloc[0] if c in categorical else float(df[c].median())
    return out


def _binary_metrics(y_true, scores) -> dict:
    y_true = np.asarray(y_true)
    scores = np.asarray(scores)
    m = {"rows": int(len(y_true)), "positive_rate": round(float(y_true.mean()), 4)}
    if len(set(y_true)) == 2:
        m["roc_auc"] = round(float(roc_auc_score(y_true, scores)), 4)
        m["average_precision"] = round(float(average_precision_score(y_true, scores)), 4)
    pred = scores >= ALERT_THRESHOLD
    m[f"precision_at_{int(ALERT_THRESHOLD)}"] = round(float(precision_score(y_true, pred, zero_division=0)), 4)
    m[f"recall_at_{int(ALERT_THRESHOLD)}"] = round(float(recall_score(y_true, pred, zero_division=0)), 4)
    return m


def _meta(name: str, algorithm: str, features: list[str], baseline: dict, metrics: dict, rows: int, extra=None) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "name": name,
        "version": f"{name}-{now:%Y%m%d%H%M%S}",
        "trained_at": now.isoformat(),
        "algorithm": algorithm,
        "features": features,
        "baseline": baseline,
        "metrics": metrics,
        "training_rows": rows,
        "library_versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "numpy": np.__version__},
        **(extra or {}),
    }


# ---------------------------------------------------------------------------
# Datasets (pure: world -> DataFrame + labels + group)
# ---------------------------------------------------------------------------


def quality_dataset(world: SyntheticWorld):
    clicks = {c.event.id: c.event for c in world.clicks}
    partners = {p.snapshot.id: p.snapshot for p in world.partners}
    prior: dict = defaultdict(int)
    rows, labels, test = [], [], []
    for conv in world.conversions:  # sorted by time
        e = conv.event
        rows.append(quality_features(e, clicks.get(e.click_id), partners[e.partner_id], prior[e.partner_id]))
        prior[e.partner_id] += 1
        labels.append(conv.good)
        test.append(_is_test_partner(e.partner_id))
    return pd.DataFrame(rows, columns=QUALITY_FEATURES), np.array(labels), np.array(test)


def fraud_dataset(world: SyntheticWorld):
    events = [c.event for c in world.clicks]  # sorted by ts
    index: dict[tuple, list[int]] = defaultdict(list)
    for i, e in enumerate(events):
        index[("ip", e.ip)].append(i)
        index[("p", e.partner_id)].append(i)
        index[("fp", e.fingerprint)].append(i)
    ts = [e.ts for e in events]
    rows, labels, test = [], [], []
    for i, e in enumerate(events):
        lo_ts = e.ts - FRAUD_HISTORY_WINDOW
        related: set[int] = set()
        for key in (("ip", e.ip), ("p", e.partner_id), ("fp", e.fingerprint)):
            lst = index[key]
            lo = bisect.bisect_left(lst, lo_ts, key=lambda j: ts[j])
            hi = bisect.bisect_right(lst, e.ts, key=lambda j: ts[j])
            related.update(lst[lo:hi])
        rows.append(fraud_features(e, [events[j] for j in related]))
        labels.append(world.clicks[i].fraud)
        test.append(_is_test_partner(e.partner_id))
    return pd.DataFrame(rows, columns=FRAUD_FEATURES), np.array(labels), np.array(test)


def churn_dataset(world: SyntheticWorld):
    convs: dict = defaultdict(list)
    clicks: dict = defaultdict(list)
    for c in world.conversions:
        convs[c.event.partner_id].append(c.event)
    for c in world.clicks:
        clicks[c.event.partner_id].append(c.event)
    rows, labels, test = [], [], []
    for offset_days in (90, 75, 60, 45, 30):
        as_of = world.end - timedelta(days=offset_days)
        horizon_end = as_of + CHURN_HORIZON
        for p in world.partners:
            snap = p.snapshot
            if snap.created_at > as_of - timedelta(days=30):
                continue
            past_clicks = [c for c in clicks[snap.id] if as_of - timedelta(days=60) <= c.ts < as_of]
            if not past_clicks:
                continue  # already inactive: nothing left to predict
            lookback = as_of - CHURN_LOOKBACK
            rows.append(
                churn_features(
                    snap,
                    as_of,
                    [c for c in convs[snap.id] if lookback <= c.ts < as_of],
                    [c for c in clicks[snap.id] if lookback <= c.ts < as_of],
                )
            )
            future = any(as_of <= c.ts < horizon_end for c in convs[snap.id])
            labels.append(0 if future else 1)
            test.append(_is_test_partner(snap.id))
    return pd.DataFrame(rows, columns=CHURN_FEATURES), np.array(labels), np.array(test)


# ---------------------------------------------------------------------------
# Trainers
# ---------------------------------------------------------------------------


def _gbc_pipeline(numeric: list[str], categorical: list[str]) -> Pipeline:
    transformers = [("num", "passthrough", numeric)]
    if categorical:
        transformers.append(("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical))
    return Pipeline(
        [
            ("pre", ColumnTransformer(transformers)),
            ("model", GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=0)),
        ]
    )


def train_quality(world: SyntheticWorld) -> dict:
    X, y, test = quality_dataset(world)
    pipe = _gbc_pipeline(QUALITY_NUMERIC, QUALITY_CATEGORICAL)
    pipe.fit(X[~test], y[~test])
    metrics = {"holdout": _binary_metrics(y[test], pipe.predict_proba(X[test])[:, 1] * 100)}
    pipe.fit(X, y)  # final model on all data
    meta = _meta("quality", "GradientBoostingClassifier", QUALITY_FEATURES, _baseline(X, QUALITY_CATEGORICAL), metrics, len(X))
    registry.save("quality", pipe, meta)
    return meta


def train_churn(world: SyntheticWorld) -> dict:
    X, y, test = churn_dataset(world)
    pipe = _gbc_pipeline(CHURN_FEATURES, [])
    pipe.fit(X[~test], y[~test])
    metrics = {"holdout": _binary_metrics(y[test], pipe.predict_proba(X[test])[:, 1] * 100)}
    pipe.fit(X, y)
    meta = _meta("churn", "GradientBoostingClassifier", CHURN_FEATURES, _baseline(X, []), metrics, len(X))
    registry.save("churn", pipe, meta)
    return meta


def _fit_fraud(X: pd.DataFrame, y: np.ndarray, contamination: float):
    pipe = Pipeline(
        [
            ("pre", ColumnTransformer([("num", "passthrough", FRAUD_FEATURES)])),
            ("model", IsolationForest(n_estimators=200, contamination=contamination, random_state=0)),
        ]
    )
    pipe.fit(X)
    raw = -pipe.decision_function(X)
    cal = LogisticRegression(solver="liblinear").fit(raw.reshape(-1, 1), y)
    return pipe, {"coef": float(cal.coef_[0, 0]), "intercept": float(cal.intercept_[0])}


def _fraud_scores(pipe, calibration, X) -> np.ndarray:
    raw = -pipe.decision_function(X)
    return 100.0 / (1.0 + np.exp(-(calibration["coef"] * raw + calibration["intercept"])))


def train_fraud(world: SyntheticWorld, reviews: Optional[tuple[pd.DataFrame, np.ndarray]] = None) -> dict:
    X, y, test = fraud_dataset(world)
    contamination = float(np.clip(y.mean(), 0.01, 0.3))
    pipe, cal = _fit_fraud(X[~test], y[~test], contamination)
    metrics = {"holdout": _binary_metrics(y[test], _fraud_scores(pipe, cal, X[test]))}
    pipe, cal = _fit_fraud(X, y, contamination)
    if reviews is not None and len(reviews[0]):
        metrics["admin_reviews"] = _binary_metrics(reviews[1], _fraud_scores(pipe, cal, reviews[0]))
    meta = _meta(
        "fraud", "IsolationForest + logistic calibration", FRAUD_FEATURES, _baseline(X, []), metrics, len(X),
        extra={"calibration": cal, "contamination": contamination},
    )
    registry.save("fraud", pipe, meta)
    return meta


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def load_review_labels(session) -> tuple[pd.DataFrame, np.ndarray]:
    """Features + labels for clicks an admin has reviewed (confirmed=1, dismissed=0)."""
    from sqlalchemy import select

    from app.ai.features import load_fraud_inputs
    from app.models.fraud_flag import FraudFlag

    rows, labels = [], []
    flags = (
        await session.execute(
            select(FraudFlag.referral_click_id, FraudFlag.status).where(
                FraudFlag.status.in_(("confirmed", "dismissed")), FraudFlag.referral_click_id.is_not(None)
            )
        )
    ).all()
    for click_id, status in flags:
        loaded = await load_fraud_inputs(session, click_id)
        if loaded:
            rows.append(fraud_features(*loaded))
            labels.append(1 if status == "confirmed" else 0)
    return pd.DataFrame(rows, columns=FRAUD_FEATURES), np.array(labels)


def train_models(
    models: tuple[str, ...] = registry.MODEL_NAMES,
    n_partners: int = 300,
    seed: int = 7,
    reviews: Optional[tuple[pd.DataFrame, np.ndarray]] = None,
) -> dict:
    """Synchronous (CPU-bound). Returns {model: metadata}."""
    t0 = time.time()
    world = generate_world(n_partners=n_partners, seed=seed)
    logger.info("Synthetic world: %d partners, %d clicks, %d conversions", len(world.partners), len(world.clicks), len(world.conversions))
    results = {}
    trainers = {"quality": lambda: train_quality(world), "churn": lambda: train_churn(world), "fraud": lambda: train_fraud(world, reviews)}
    for name in models:
        t = time.time()
        results[name] = trainers[name]()
        logger.info("Trained %s in %.1fs: %s", name, time.time() - t, results[name]["metrics"])
    logger.info("Training finished in %.1fs", time.time() - t0)
    return results


async def _cli(args) -> None:
    reviews = None
    if args.with_reviews:
        from app.core.database import AsyncSessionLocal, engine

        async with AsyncSessionLocal() as session:
            reviews = await load_review_labels(session)
        await engine.dispose()
    models = registry.MODEL_NAMES if args.models == "all" else tuple(args.models.split(","))
    if args.if_missing:
        models = tuple(m for m in models if registry.get(m) is None)
        if not models:
            print(f"All models already trained in {registry.model_dir()} — skipping")
            return
    results = await asyncio.to_thread(train_models, models, args.partners, args.seed, reviews)
    print(f"Models saved to {registry.model_dir()}")
    for name, meta in results.items():
        print(f"  {name:8s} {meta['version']}  {meta['metrics']}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Train ReferrAI models")
    parser.add_argument("--models", default="all", help="all or a comma list of quality,fraud,churn")
    parser.add_argument("--partners", type=int, default=300, help="synthetic partners to simulate")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--with-reviews", action="store_true", help="also evaluate on admin fraud reviews (needs DB)")
    parser.add_argument("--if-missing", action="store_true", help="only train models that have no saved artifact")
    asyncio.run(_cli(parser.parse_args()))


if __name__ == "__main__":
    main()
