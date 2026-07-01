# -----------------------------------------------------------------------------
# backend/app/ai/training/train_churn_predictor.py
#
# Standalone training script for the ChurnPredictor (AI-CHURN-001).
# Never imported by FastAPI — run directly from backend/:
#
#   DATABASE_URL=postgresql+asyncpg://... \
#       python -m app.ai.training.train_churn_predictor
#
# or:
#
#   DATABASE_URL=... python app/ai/training/train_churn_predictor.py
#
# === Churn label derivation ===
# SyntheticDataGenerator.generate_churn_labelled() makes NO database writes.
# Churn is expressed behaviourally through data absence: the synthetic data
# service (AI-DATA-002) calls generate_clicks() only for "active" partners,
# leaving churned partners with zero click and conversion rows. This script
# derives the churn label as:
#
#   is_churned = 1  ↔  partner has no referral_conversions at all
#   is_churned = 0  ↔  partner has at least one referral_conversion
#
# === Commission trend ===
# Synthetic conversions are generated without commission rows — the synthetic
# data service explicitly skips CommissionService.calculate_for_conversion().
# commission_trend is therefore derived from referral_conversions.conversion_value
# (recent 90d revenue / prior 90d revenue) rather than the commissions table.
#
# Prerequisites:
#   pip install -r requirements-ml.txt
# -----------------------------------------------------------------------------

import asyncio
import logging
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sklearn.metrics import average_precision_score, classification_report
from sklearn.model_selection import train_test_split
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.ai.scoring.churn import ChurnPredictor
from app.models.partner import Partner, PartnerTier
from app.models.referral import ReferralConversion

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_MIN_PARTNERS = 10
# Sentinel for partners with no conversion history at all. Capped at 365 to
# avoid extreme outliers that would require a wide StandardScaler range.
_DAYS_NO_ACTIVITY = 365.0


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

async def _load_partners(session: AsyncSession) -> list[dict]:
    """Load all synthetic partners with their tier rank."""
    stmt = (
        select(
            Partner.id,
            PartnerTier.rank_order,
        )
        .join(PartnerTier, Partner.tier_id == PartnerTier.id, isouter=True)
        .where(Partner.is_synthetic == True)  # noqa: E712
    )
    result = await session.execute(stmt)
    return [
        {
            "id": row.id,
            "tier_rank": int(row.rank_order) if row.rank_order is not None else 0,
        }
        for row in result.all()
    ]


async def _load_conversions(session: AsyncSession) -> list[dict]:
    """Load all synthetic conversions (partner_id, value, timestamp)."""
    stmt = (
        select(
            ReferralConversion.partner_id,
            ReferralConversion.conversion_value,
            ReferralConversion.converted_at,
        )
        .where(ReferralConversion.is_synthetic == True)  # noqa: E712
    )
    result = await session.execute(stmt)
    return [
        {
            "partner_id": row.partner_id,
            "conversion_value": float(row.conversion_value or Decimal("0")),
            "converted_at": row.converted_at,
        }
        for row in result.all()
    ]


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _build_records(
    partners: list[dict],
    conversions: list[dict],
    now: Optional[datetime] = None,
) -> list[dict]:
    """Compute churn features and derive the churn label for each partner.

    Label derivation:
        is_churned = 1  ↔  zero conversions (partner was excluded from
                            generate_clicks() by generate_churn_labelled())
        is_churned = 0  ↔  at least one conversion

    Feature: commission_trend
        recent_revenue = sum(conversion_value) for conversions in last 90 days
        prior_revenue  = sum(conversion_value) for conversions in days 90–180 ago
        commission_trend = recent_revenue / (prior_revenue + 1.0)

        Note: synthetic conversions all land within the most recent 90 days
        (generate_conversions uses _random_past_datetime(days=90)), so
        prior_revenue is always 0 for synthetic data. The feature still
        discriminates well between churned (0.0) and active partners (>0.0)
        and will carry signal for real data at inference time.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    cutoff_30d = now - timedelta(days=30)
    cutoff_90d = now - timedelta(days=90)
    cutoff_180d = now - timedelta(days=180)

    # Group conversions by partner for O(n) feature computation
    by_partner: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for c in conversions:
        by_partner[c["partner_id"]].append(c)

    records: list[dict] = []
    for p in partners:
        pid = p["id"]
        convs = by_partner[pid]

        # --- Churn label ---
        is_churned = 1 if not convs else 0

        # --- days_since_last_referral ---
        if convs:
            last_at = max(c["converted_at"] for c in convs)
            days_since = (now - last_at).total_seconds() / 86400.0
        else:
            days_since = _DAYS_NO_ACTIVITY

        # --- Referral counts ---
        count_30d = sum(1 for c in convs if c["converted_at"] >= cutoff_30d)
        count_90d = sum(1 for c in convs if c["converted_at"] >= cutoff_90d)

        # --- Commission trend (revenue ratio recent vs prior window) ---
        recent_rev = sum(
            c["conversion_value"] for c in convs if c["converted_at"] >= cutoff_90d
        )
        prior_rev = sum(
            c["conversion_value"]
            for c in convs
            if cutoff_180d <= c["converted_at"] < cutoff_90d
        )
        commission_trend = recent_rev / (prior_rev + 1.0)

        records.append(
            {
                "days_since_last_referral": max(0.0, days_since),
                "referral_count_30d": count_30d,
                "referral_count_90d": count_90d,
                "commission_trend": commission_trend,
                "tier_rank": p["tier_rank"],
                # Label — read by train(), stripped before predict()
                "is_churned": is_churned,
            }
        )

    return records


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _evaluate(predictor: ChurnPredictor, test_records: list[dict]) -> None:
    """Print PR-AUC and a classification report on the held-out test split.

    PR-AUC (area under the precision-recall curve) is preferred over ROC-AUC
    for churn prediction because the positive class (churned partners) is
    typically the minority, and PR-AUC better reflects performance where false
    positives are costly (incorrectly flagging healthy partners for intervention).
    """
    y_true = [r["is_churned"] for r in test_records]

    # Feature-only dicts for predict()
    predict_records = [
        {k: v for k, v in r.items() if k != "is_churned"}
        for r in test_records
    ]
    y_scores = [predictor.predict(r) / 100.0 for r in predict_records]

    if len(set(y_true)) < 2:
        logger.warning(
            "Test set contains only one class — PR-AUC is undefined. "
            "Ensure churn_ratio > 0 when running AI-DATA-002."
        )
        return

    pr_auc = average_precision_score(y_true, y_scores)
    print(f"\nPR-AUC: {pr_auc:.4f}")

    # Threshold at 0.5 (score 50.0) for the classification report
    y_pred = [1 if s >= 0.5 else 0 for s in y_scores]
    print("\nClassification report (threshold = 0.50):")
    print(
        classification_report(
            y_true,
            y_pred,
            target_names=["active", "churned"],
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

    logger.info("Loading synthetic partner and conversion data …")
    async with async_session() as session:
        partners, conversions = await asyncio.gather(
            _load_partners(session),
            _load_conversions(session),
        )

    await engine.dispose()

    logger.info(
        "Loaded %d synthetic partners and %d synthetic conversions",
        len(partners),
        len(conversions),
    )

    if len(partners) < _MIN_PARTNERS:
        logger.error(
            "Too few synthetic partners (%d) — run AI-DATA-002 first "
            "(minimum %d required)",
            len(partners),
            _MIN_PARTNERS,
        )
        sys.exit(1)

    records = _build_records(partners, conversions)

    churned_count = sum(1 for r in records if r["is_churned"])
    logger.info(
        "Feature matrix: %d partners total / %d churned / %d active",
        len(records),
        churned_count,
        len(records) - churned_count,
    )

    if churned_count == 0:
        logger.error(
            "No churned partners found. Re-run AI-DATA-002 with churn_ratio > 0."
        )
        sys.exit(1)

    records_train, records_test = train_test_split(
        records, test_size=0.2, random_state=42, stratify=[r["is_churned"] for r in records]
    )
    logger.info(
        "Split: %d train / %d test (stratified)", len(records_train), len(records_test)
    )

    predictor = ChurnPredictor()
    predictor.train(records_train)

    _evaluate(predictor, records_test)

    logger.info("Feature importances:")
    for name, importance in predictor.get_feature_importances().items():
        logger.info("  %-35s %.4f", name, importance)

    logger.info("Model saved to app/ai/models/churn_predictor.joblib")


if __name__ == "__main__":
    asyncio.run(main())
