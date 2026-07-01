# -----------------------------------------------------------------------------
# backend/app/services/ai_service.py
#
# AI scoring background tasks (AI-QUAL-002). Functions here are designed to
# be registered with FastAPI's BackgroundTasks and therefore must never raise
# — any exception is caught, logged, and swallowed so a scoring failure cannot
# affect the HTTP response or the caller's transaction.
#
# Session ownership: the AsyncSession is passed in from the request that
# recorded the conversion. FastAPI runs background tasks before dependency
# cleanup, so the session remains open and usable. The background task opens
# its own implicit transaction (SQLAlchemy async sessions are non-autocommit
# by default) and commits independently of the parent request's commit.
# -----------------------------------------------------------------------------

import logging
import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.scoring.quality import ReferralQualityScorer
from app.models.ai_score import AIScore
from app.models.partner import Partner, PartnerTier
from app.models.referral import ReferralClick, ReferralConversion

logger = logging.getLogger(__name__)


async def score_referral_quality(
    db: AsyncSession, conversion_id: uuid.UUID
) -> None:
    """Compute and persist a quality score for the given referral conversion.

    Loads the conversion row joined with its attributed click and the partner's
    tier, extracts the five model features, calls ReferralQualityScorer.predict(),
    and appends a new row to ai_scores.

    All exceptions are caught and logged — this function never raises so that a
    model-not-found error or inference failure cannot propagate to the caller.

    Args:
        db:            SQLAlchemy async session (injected from the request scope).
        conversion_id: PK of the ReferralConversion row to score.
    """
    try:
        # --- Load conversion + click (LEFT JOIN) + partner tier (LEFT JOIN) ---
        stmt = (
            select(
                ReferralConversion,
                ReferralClick,
                PartnerTier.rank_order,
            )
            .join(
                ReferralClick,
                ReferralConversion.click_id == ReferralClick.id,
                isouter=True,
            )
            .join(
                Partner,
                ReferralConversion.partner_id == Partner.id,
                isouter=True,
            )
            .join(
                PartnerTier,
                Partner.tier_id == PartnerTier.id,
                isouter=True,
            )
            .where(ReferralConversion.id == conversion_id)
        )
        result = await db.execute(stmt)
        row = result.first()

        if row is None:
            logger.warning(
                "score_referral_quality: conversion %s not found — skipping",
                conversion_id,
            )
            return

        conversion, click, tier_rank = row

        # --- Feature extraction ---
        if (
            click is not None
            and click.clicked_at is not None
            and conversion.converted_at is not None
        ):
            time_to_convert = (
                conversion.converted_at - click.clicked_at
            ).total_seconds() / 60.0
        else:
            time_to_convert = 0.0

        source_type: str = (
            (click.source if click is not None else None) or "unknown"
        )
        device_category: str = (
            ((click.device_info or {}).get("device_type", "unknown") or "unknown")
            if click is not None
            else "unknown"
        )

        features: dict = {
            "time_to_convert_minutes": max(0.0, time_to_convert),
            "source_type": source_type,
            "device_category": device_category,
            "conversion_value_normalized": float(conversion.conversion_value),
            "partner_tier_rank": int(tier_rank) if tier_rank is not None else 1,
        }

        # --- Score ---
        scorer = ReferralQualityScorer()
        score: float = scorer.predict(features)

        # get_feature_importances() raises RuntimeError when the model file is
        # absent (predict() returned the 50.0 fallback without loading the model).
        # An inner guard ensures a missing model file still produces a score row.
        importances: Optional[dict] = None
        try:
            importances = scorer.get_feature_importances()
        except Exception:
            pass  # contributing_factors stays None; score row is still useful

        # --- Persist ---
        ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="referral",
            entity_id=conversion_id,
            score_type="quality",
            score=Decimal(str(round(score, 2))),
            contributing_factors=importances,
            explanation=None,
            model_version="1.0",
            is_synthetic=False,
        )
        db.add(ai_score)
        await db.commit()

        logger.info(
            "Quality score %.2f stored for conversion %s", score, conversion_id
        )

    except Exception:
        logger.exception(
            "score_referral_quality failed for conversion %s — no score stored",
            conversion_id,
        )
