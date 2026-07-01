# -----------------------------------------------------------------------------
# backend/app/ai/training/train_fraud_detector.py
#
# Standalone training script for the FraudDetector (AI-FRD-002).
# Never imported by FastAPI — run directly from backend/:
#
#   DATABASE_URL=postgresql+asyncpg://... \
#       python -m app.ai.training.train_fraud_detector
#
# or:
#
#   DATABASE_URL=... python app/ai/training/train_fraud_detector.py
#
# The script queries synthetic referral_clicks that carry a ground-truth fraud
# label in their device_info JSONB (written by SyntheticDataGenerator.
# generate_fraud_labelled, stored as "_synthetic_fraud_label": true/false).
# Features are computed in-process from the raw click rows using plain Python
# (no pandas dependency).  The trained model is evaluated on a 20 % test
# split: because IsolationForest is unsupervised, evaluation is done by
# thresholding its binary predictions against the ground-truth labels.
#
# Prerequisites:
#   pip install -r requirements-ml.txt
# -----------------------------------------------------------------------------

import asyncio
import bisect
import logging
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.ai.scoring.fraud import FraudDetector
from app.models.referral import ReferralClick

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_MIN_RECORDS = 20
_NO_PREVIOUS_CLICK_DEFAULT_SECONDS = 3600.0  # used for first click from a given IP


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

async def _load_labelled_clicks(session: AsyncSession) -> list[dict]:
    """Load synthetic clicks that carry a ground-truth fraud label.

    Only clicks where device_info contains the key '_synthetic_fraud_label'
    are selected — these are the rows written by generate_fraud_labelled().
    Un-labelled synthetic clicks (before fraud labelling was applied) are
    excluded so the training set has clean ground truth.
    """
    stmt = (
        select(
            ReferralClick.id,
            ReferralClick.ip_address,
            ReferralClick.device_info,
            ReferralClick.clicked_at,
            ReferralClick.partner_id,
        )
        .where(ReferralClick.is_synthetic == True)  # noqa: E712
        # JSONB '?' operator — true when the key exists regardless of value
        .where(ReferralClick.device_info.has_key("_synthetic_fraud_label"))
        .order_by(ReferralClick.partner_id, ReferralClick.clicked_at)
    )
    result = await session.execute(stmt)
    return [
        {
            "id": row.id,
            "ip_address": row.ip_address or "unknown",
            "device_info": row.device_info or {},
            "clicked_at": row.clicked_at,
            "partner_id": row.partner_id,
        }
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _build_feature_records(raw_clicks: list[dict]) -> list[dict]:
    """Compute behavioural features for each click from the full click corpus.

    All four features are derived from aggregations over the corpus:

    clicks_per_hour
        How many clicks from the same IP address landed within the 60 minutes
        before (and including) this click.  Fraud bots fire many clicks from
        the same IP in a short burst; organic visitors rarely trigger this.

    unique_ips_per_partner
        Total distinct IP addresses seen across all clicks for this partner.
        High counts are normal (many organic visitors); very low counts on a
        partner with many clicks suggest a single-device farming operation.

    device_reuse_count
        Number of other clicks in the corpus that share the same user-agent
        string.  The fraud generator reuses a single bot UA per burst so this
        count spikes for fraud clicks.

    time_between_clicks_seconds
        Seconds elapsed since the immediately preceding click from the same IP.
        A burst click lands within seconds or minutes; organic first-clicks
        from a given IP have no predecessor (assigned a neutral 3600 s default).
    """
    # ---- Pre-aggregate: sorted timestamps per IP (for 1-hour window count) ----
    ip_times: dict[str, list[datetime]] = defaultdict(list)
    for c in raw_clicks:
        ip_times[c["ip_address"]].append(c["clicked_at"])
    for times in ip_times.values():
        times.sort()

    # ---- Pre-aggregate: unique IP count per partner ----
    partner_ips: dict[uuid.UUID, set] = defaultdict(set)
    for c in raw_clicks:
        partner_ips[c["partner_id"]].add(c["ip_address"])
    unique_ips_by_partner: dict[uuid.UUID, int] = {
        pid: len(ips) for pid, ips in partner_ips.items()
    }

    # ---- Pre-aggregate: user-agent reuse counts ----
    ua_counts: dict[str, int] = defaultdict(int)
    for c in raw_clicks:
        ua = c["device_info"].get("user_agent", "unknown")
        ua_counts[ua] += 1

    # ---- Per-click feature computation ----
    # Track the timestamp of the most recent click seen from each IP so far.
    # Clicks are delivered ordered by (partner_id, clicked_at) from the query,
    # but time_between is relative to the previous click from the *same IP*
    # regardless of partner.  We iterate globally and maintain ip_prev.
    # Re-sort by clicked_at globally so the ordering is correct.
    clicks_sorted = sorted(raw_clicks, key=lambda c: c["clicked_at"])
    ip_prev: dict[str, Optional[datetime]] = {}

    records: list[dict] = []
    for c in clicks_sorted:
        ip = c["ip_address"]
        ua = c["device_info"].get("user_agent", "unknown")
        ts = c["clicked_at"]
        pid = c["partner_id"]

        # clicks_per_hour: binary-search the sorted timestamp list for this IP
        sorted_times = ip_times[ip]
        window_start = ts - timedelta(hours=1)
        lo = bisect.bisect_left(sorted_times, window_start)
        hi = bisect.bisect_right(sorted_times, ts)
        clicks_in_hour = float(hi - lo)

        # time_between_clicks_seconds
        prev_ts = ip_prev.get(ip)
        time_between = (
            (ts - prev_ts).total_seconds()
            if prev_ts is not None
            else _NO_PREVIOUS_CLICK_DEFAULT_SECONDS
        )
        ip_prev[ip] = ts

        records.append(
            {
                "clicks_per_hour": clicks_in_hour,
                "unique_ips_per_partner": unique_ips_by_partner.get(pid, 1),
                "device_reuse_count": ua_counts[ua],
                "time_between_clicks_seconds": max(0.0, time_between),
                # Ground-truth label (not passed to the model, only used for evaluation)
                "_fraud_label": bool(c["device_info"].get("_synthetic_fraud_label", False)),
            }
        )

    return records


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _evaluate(detector: FraudDetector, test_records: list[dict]) -> None:
    """Print precision and recall on the held-out test split.

    IsolationForest's contamination parameter implicitly sets the decision
    threshold, so we use the model's own binary predict() (-1/1) rather than
    an arbitrary score threshold.  Predicted -1 → fraud (1), 1 → clean (0).
    """
    X_test = np.array(
        [FraudDetector._build_row(r) for r in test_records], dtype=float
    )
    X_test_scaled = detector._scaler.transform(X_test)  # type: ignore[union-attr]

    iso_pred = detector._model.predict(X_test_scaled)  # type: ignore[union-attr]
    y_pred = [1 if p == -1 else 0 for p in iso_pred]
    y_true = [1 if r["_fraud_label"] else 0 for r in test_records]

    if len(set(y_true)) < 2:
        logger.warning(
            "Test set contains only one class — precision/recall undefined. "
            "Adjust fraud_ratio when calling AI-DATA-002 to produce both classes."
        )
        return

    print("\nClassification report (contamination threshold = 0.2):")
    print(
        classification_report(
            y_true,
            y_pred,
            target_names=["clean", "fraud"],
            zero_division=0,
        )
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    logger.info("Querying labelled synthetic click records …")
    async with async_session() as session:
        raw_clicks = await _load_labelled_clicks(session)

    await engine.dispose()

    logger.info("Loaded %d labelled click rows", len(raw_clicks))
    if len(raw_clicks) < _MIN_RECORDS:
        logger.error(
            "Too few records (%d) — run AI-DATA-002 first (minimum %d required). "
            "Ensure fraud_ratio > 0 so generate_fraud_labelled() is called.",
            len(raw_clicks),
            _MIN_RECORDS,
        )
        sys.exit(1)

    logger.info("Computing behavioural features …")
    records = _build_feature_records(raw_clicks)

    fraud_count = sum(1 for r in records if r["_fraud_label"])
    logger.info(
        "Feature matrix ready: %d total / %d fraud / %d clean",
        len(records),
        fraud_count,
        len(records) - fraud_count,
    )

    records_train, records_test = train_test_split(
        records, test_size=0.2, random_state=42
    )
    logger.info(
        "Split: %d train / %d test", len(records_train), len(records_test)
    )

    # Labels are NOT passed to train() — IsolationForest is unsupervised
    train_features = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in records_train
    ]

    detector = FraudDetector()
    detector.train(train_features)

    _evaluate(detector, records_test)

    logger.info("Model saved to app/ai/models/fraud_detector.joblib")


if __name__ == "__main__":
    asyncio.run(main())
