# -----------------------------------------------------------------------------
# backend/app/ai/training/train_quality_scorer.py
#
# Standalone training script for the ReferralQualityScorer (AI-QUAL-001).
# Never imported by FastAPI — run directly with:
#
#   DATABASE_URL=postgresql+asyncpg://... python -m app.ai.training.train_quality_scorer
#
# or from backend/:
#
#   DATABASE_URL=... python app/ai/training/train_quality_scorer.py
#
# The script queries synthetic referral_conversions joined with their clicks
# and partners, builds feature dicts, trains the scorer, and prints the
# ROC-AUC on a held-out 20 % test split.
#
# Prerequisites:
#   pip install -r requirements-ml.txt
# -----------------------------------------------------------------------------

import asyncio
import logging
import os
import statistics
import sys
from decimal import Decimal
from typing import Optional

from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Allow running as `python app/ai/training/train_quality_scorer.py` from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.ai.scoring.quality import ReferralQualityScorer
from app.models.partner import Partner, PartnerTier
from app.models.referral import ReferralClick, ReferralConversion

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_MIN_RECORDS = 10  # refuse to train on trivially small datasets


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

async def _load_records(session: AsyncSession) -> list[dict]:
    """Query synthetic conversions and assemble feature dicts.

    Joins:
      referral_conversions (is_synthetic=TRUE)
        LEFT JOIN referral_clicks     ON conversions.click_id   = clicks.id
        LEFT JOIN partners            ON conversions.partner_id = partners.id
        LEFT JOIN partner_tiers       ON partners.tier_id       = tiers.id

    A LEFT JOIN is used for clicks because click_id is nullable on conversions
    (attribution may have found no click). time_to_convert_minutes defaults to
    0.0 when the click timestamp is unavailable.
    """
    stmt = (
        select(
            ReferralConversion.conversion_value,
            ReferralConversion.converted_at,
            ReferralClick.clicked_at,
            ReferralClick.source,
            ReferralClick.device_info,
            PartnerTier.rank_order,
        )
        .join(ReferralClick, ReferralConversion.click_id == ReferralClick.id, isouter=True)
        .join(Partner, ReferralConversion.partner_id == Partner.id, isouter=True)
        .join(PartnerTier, Partner.tier_id == PartnerTier.id, isouter=True)
        .where(ReferralConversion.is_synthetic == True)  # noqa: E712  — SQLAlchemy requires ==
    )

    result = await session.execute(stmt)
    rows = result.all()

    records: list[dict] = []
    for row in rows:
        conversion_value, converted_at, clicked_at, source, device_info, rank_order = row

        if clicked_at is not None and converted_at is not None:
            time_to_convert = (converted_at - clicked_at).total_seconds() / 60.0
        else:
            time_to_convert = 0.0

        device_type: Optional[str] = (device_info or {}).get("device_type")

        records.append(
            {
                "time_to_convert_minutes": max(0.0, time_to_convert),
                "source_type": source,
                "device_category": device_type,
                # Raw value; StandardScaler inside the Pipeline normalises it.
                "conversion_value_normalized": float(conversion_value or Decimal("0")),
                "partner_tier_rank": int(rank_order) if rank_order is not None else 0,
            }
        )

    return records


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------

def _compute_labels(records: list[dict], median_val: float) -> list[int]:
    """Reproduce the scorer's binary label using the training-set median."""
    return [1 if r["conversion_value_normalized"] > median_val else 0 for r in records]


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

    logger.info("Querying synthetic training records …")
    async with async_session() as session:
        records = await _load_records(session)

    await engine.dispose()

    logger.info("Loaded %d synthetic conversion records", len(records))
    if len(records) < _MIN_RECORDS:
        logger.error(
            "Too few records (%d) — run AI-DATA-002 to generate synthetic data first "
            "(minimum %d required)",
            len(records),
            _MIN_RECORDS,
        )
        sys.exit(1)

    # Train / test split (stratification not needed for continuous label proxy)
    records_train, records_test = train_test_split(
        records, test_size=0.2, random_state=42
    )

    logger.info(
        "Training on %d records, evaluating on %d …",
        len(records_train),
        len(records_test),
    )

    scorer = ReferralQualityScorer()
    scorer.train(records_train)

    # Use the training-set median stored by train() so test labels are consistent
    y_test = _compute_labels(records_test, scorer._label_median)
    y_scores = [scorer.predict(r) / 100.0 for r in records_test]

    if len(set(y_test)) < 2:
        logger.warning(
            "Test set contains only one class — ROC-AUC is undefined. "
            "Generate more synthetic data with a wider conversion_value spread."
        )
    else:
        auc = roc_auc_score(y_test, y_scores)
        print(f"ROC-AUC: {auc:.4f}")

    logger.info("Feature importances:")
    for name, importance in scorer.get_feature_importances().items():
        logger.info("  %-35s %.4f", name, importance)

    logger.info("Model saved to app/ai/models/quality_scorer.joblib")


if __name__ == "__main__":
    asyncio.run(main())
