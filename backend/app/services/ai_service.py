# -----------------------------------------------------------------------------
# backend/app/services/ai_service.py
#
# AI scoring background tasks (AI-QUAL-002, AI-FRD-003, AI-CHURN-002,
# AI-RANK-001). Functions are designed to be called from BackgroundTasks or
# admin batch endpoints and must never raise — any exception is caught, logged,
# and swallowed so a scoring failure cannot affect the HTTP response.
# Added score_ranking() for AI-RANK-001: composite partner ranking using
# quality, inverted churn risk, normalised volume, and normalised revenue.
# score_fraud() updated for AI-FRD-001: FraudRuleEngine deterministic rules are
# run alongside the Isolation Forest model; the composite score is
# min(100, ml_score + len(triggered_rules) * 30). triggered_rules are stored
# in contributing_factors and included in the explanation text.
#
# Session ownership: the AsyncSession is passed in from the request scope.
# FastAPI runs background tasks before dependency cleanup, so the session
# remains open and usable. Each function opens its own implicit transaction
# and commits independently of the parent request's commit.
# -----------------------------------------------------------------------------

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.explainability.explainer import Explainer
from app.ai.scoring.churn import FEATURE_NAMES as CHURN_FEATURE_NAMES
from app.ai.scoring.churn import ChurnPredictor
from app.ai.scoring.fraud import FraudDetector
from app.ai.scoring.fraud_rules import FraudRuleEngine
from app.ai.scoring.quality import ReferralQualityScorer
from app.models.ai_score import AIScore
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner, PartnerTier
from app.models.referral import ReferralClick, ReferralConversion
from app.services.setting_service import SettingService

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

        # SHAP explanation — wrapped in try/except so a missing model file or
        # SHAP failure never blocks the score row from being written.
        quality_top_factors: dict = {}
        quality_explanation: Optional[str] = None
        try:
            quality_top_factors = Explainer().explain_tree(
                scorer._pipeline, features, ReferralQualityScorer.FEATURE_NAMES
            )
            quality_explanation = Explainer().to_plain_language(
                "quality", quality_top_factors
            )
        except Exception:
            pass  # contributing_factors stays {}; score row is still useful

        # --- Persist ---
        ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="referral",
            entity_id=conversion_id,
            score_type="quality",
            score=Decimal(str(round(score, 2))),
            contributing_factors=quality_top_factors or None,
            explanation=quality_explanation,
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


async def score_fraud(db: AsyncSession, click_id: uuid.UUID) -> None:
    """Compute and persist a fraud risk score for the given referral click (AI-FRD-003).

    Runs five SQLAlchemy queries to extract behavioural velocity features, calls
    FraudDetector.predict(), appends an ai_scores row, and conditionally creates a
    fraud_flags row when the score exceeds the configured alert threshold.

    All exceptions are caught and logged — this function never raises.

    Args:
        db:       SQLAlchemy async session (injected from the request scope).
        click_id: PK of the ReferralClick row to score.
    """
    try:
        now = datetime.now(timezone.utc)
        cutoff_1h = now - timedelta(hours=1)
        cutoff_24h = now - timedelta(hours=24)

        # --- 1. Load the click row ---
        click_row = await db.execute(
            select(ReferralClick).where(ReferralClick.id == click_id)
        )
        click = click_row.scalar_one_or_none()
        if click is None:
            logger.warning("score_fraud: click %s not found — skipping", click_id)
            return

        ip = click.ip_address or "unknown"
        partner_id = click.partner_id
        device_info = click.device_info or {}
        # Use 'fingerprint' key when present (future-proofing); fall back to
        # 'user_agent' which is what ReferralClickService.track() stores today.
        fingerprint = (
            device_info.get("fingerprint")
            or device_info.get("user_agent")
            or "unknown"
        )

        # --- 2. clicks_per_hour: count from same IP in the last hour ---
        cph_scalar = await db.execute(
            select(func.count())
            .select_from(ReferralClick)
            .where(ReferralClick.ip_address == ip)
            .where(ReferralClick.clicked_at >= cutoff_1h)
        )
        clicks_per_hour = float(cph_scalar.scalar() or 0)

        # --- 3. device_reuse_count: distinct partners sharing this device fingerprint ---
        # JSONB ->> operator via .astext extracts the field as text for comparison.
        fp_expr = func.coalesce(
            ReferralClick.device_info["fingerprint"].astext,
            ReferralClick.device_info["user_agent"].astext,
        )
        drc_scalar = await db.execute(
            select(func.count(func.distinct(ReferralClick.partner_id)))
            .select_from(ReferralClick)
            .where(fp_expr == fingerprint)
            .where(ReferralClick.clicked_at >= cutoff_24h)
        )
        device_reuse_count = int(drc_scalar.scalar() or 1)

        # --- 4. unique_ips_per_partner: distinct IPs for this partner in 24 h ---
        uip_scalar = await db.execute(
            select(func.count(func.distinct(ReferralClick.ip_address)))
            .select_from(ReferralClick)
            .where(ReferralClick.partner_id == partner_id)
            .where(ReferralClick.clicked_at >= cutoff_24h)
        )
        unique_ips_per_partner = int(uip_scalar.scalar() or 1)

        # --- 5. time_between_clicks_seconds: avg gap between last 10 clicks ---
        ts_rows = await db.execute(
            select(ReferralClick.clicked_at)
            .where(ReferralClick.partner_id == partner_id)
            .order_by(ReferralClick.clicked_at.desc())
            .limit(10)
        )
        timestamps = [row[0] for row in ts_rows.all()]
        if len(timestamps) >= 2:
            gaps = [
                (timestamps[i] - timestamps[i + 1]).total_seconds()
                for i in range(len(timestamps) - 1)
            ]
            time_between_clicks_seconds = sum(gaps) / len(gaps)
        else:
            # Single click from this partner — treat as no burst activity
            time_between_clicks_seconds = 3600.0

        features: dict = {
            "clicks_per_hour": clicks_per_hour,
            "unique_ips_per_partner": unique_ips_per_partner,
            "device_reuse_count": device_reuse_count,
            "time_between_clicks_seconds": time_between_clicks_seconds,
        }

        # --- ML score (Isolation Forest) ---
        detector = FraudDetector()
        ml_score: float = detector.predict(features)

        # --- Deterministic rule checks (AI-FRD-001) ---
        # FraudRuleEngine.check() never raises; returns [] on any failure.
        triggered_rules: list[str] = await FraudRuleEngine(db).check(click_id)

        # --- Composite score ---
        # Rules provide an additive boost of 30 points each (capped at 100) so
        # that a deterministic rule violation alone can reach the alert threshold
        # when combined with a modest ML score, while the ML score still has
        # influence when no rules fire.
        rule_boost = len(triggered_rules) * 30.0
        score: float = min(100.0, ml_score + rule_boost)

        # --- Explanation ---
        # Include triggered rule names in the explanation when present; fall back
        # to the generic Explainer summary when no rules fired.
        fraud_explanation: Optional[str] = None
        if triggered_rules:
            rules_str = ", ".join(triggered_rules)
            fraud_explanation = f"Fraud risk flagged due to rules: {rules_str}."
        else:
            try:
                fraud_explanation = Explainer().to_plain_language(
                    "fraud_risk", {"features": features}
                )
            except Exception:
                pass

        contributing_factors = {
            "features": features,
            "triggered_rules": triggered_rules,
            "ml_score": round(ml_score, 2),
        }

        # --- Persist ai_scores rows ---
        # Click-level row (entity_type='referral') — for per-click audit trail.
        ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="referral",
            entity_id=click_id,
            score_type="fraud_risk",
            score=Decimal(str(round(score, 2))),
            contributing_factors=contributing_factors,
            explanation=fraud_explanation,
            model_version="1.0",
            is_synthetic=False,
        )
        db.add(ai_score)

        # Partner-level row (entity_type='partner') — lets admin pages query
        # the latest fraud risk for a partner without joining through clicks.
        partner_ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="partner",
            entity_id=partner_id,
            score_type="fraud_risk",
            score=Decimal(str(round(score, 2))),
            contributing_factors=contributing_factors,
            explanation=fraud_explanation,
            model_version="1.0",
            is_synthetic=False,
        )
        db.add(partner_ai_score)

        # --- Optionally create a fraud_flags row ---
        # Read the alert threshold from settings (default 70). SettingService
        # always returns the default on miss, so this never raises.
        raw_threshold = await SettingService(db).get("fraud.alert_threshold", 70.0)
        alert_threshold = float(raw_threshold)

        # A deterministic rule hit is flagged on its own, independent of the
        # composite score/threshold: FraudRuleEngine's rules (AI-FRD-001) are
        # high-confidence ground-truth signals by design, and diluting a rule
        # hit into score = ml_score + rule_boost means it can be silently lost
        # whenever ml_score is low or zero (e.g. no trained model — true in
        # every environment until FraudDetector is trained). The composite
        # score/threshold path still applies for pure-ML signals with no
        # triggered rules.
        if score > alert_threshold or triggered_rules:
            fraud_flag = FraudFlag(
                id=uuid.uuid4(),
                partner_id=partner_id,
                ai_score_id=ai_score.id,
                referral_click_id=click_id,
                status="pending_review",
            )
            db.add(fraud_flag)
            logger.warning(
                "Fraud flag raised for partner %s (click %s, score %.2f, "
                "threshold %.2f, triggered_rules=%s)",
                partner_id,
                click_id,
                score,
                alert_threshold,
                triggered_rules,
            )

        # SQLAlchemy's unit-of-work inserts ai_scores before fraud_flags
        # automatically (FK dependency resolution).
        await db.commit()

        logger.info("Fraud score %.2f stored for click %s", score, click_id)

    except Exception:
        logger.exception(
            "score_fraud failed for click %s — no score stored", click_id
        )


async def score_churn(db: AsyncSession, partner_id: uuid.UUID) -> None:
    """Compute and persist a churn risk score for the given partner (AI-CHURN-002).

    Extracts five partner-level features from referral_conversions, calls
    ChurnPredictor.predict(), and appends an ai_scores row. Designed to be
    called from the admin /run-churn-scoring batch endpoint.

    commission_trend is computed as the ratio of recent-90d conversion value
    to prior-90d conversion value (same formula used in the training script,
    which operates on conversion_value because the commissions table is empty
    for synthetic partners). Using a different formula at inference would place
    features outside the training distribution.

    All exceptions are caught and logged — this function never raises.

    Args:
        db:         SQLAlchemy async session (injected from the request scope).
        partner_id: PK of the Partner row to score.
    """
    try:
        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)
        cutoff_90d = now - timedelta(days=90)
        cutoff_180d = now - timedelta(days=180)

        # --- 1. Load partner + tier rank (LEFT JOIN — tier may be unassigned) ---
        partner_result = await db.execute(
            select(Partner, PartnerTier.rank_order)
            .join(PartnerTier, Partner.tier_id == PartnerTier.id, isouter=True)
            .where(Partner.id == partner_id)
        )
        row = partner_result.first()
        if row is None:
            logger.warning("score_churn: partner %s not found — skipping", partner_id)
            return
        partner, tier_rank = row

        # --- 2. days_since_last_referral ---
        last_at_result = await db.execute(
            select(func.max(ReferralConversion.converted_at))
            .where(ReferralConversion.partner_id == partner_id)
            .where(ReferralConversion.is_synthetic == False)  # noqa: E712
        )
        last_converted_at = last_at_result.scalar()
        if last_converted_at is None:
            days_since_last_referral = 9999.0
        else:
            if last_converted_at.tzinfo is None:
                last_converted_at = last_converted_at.replace(tzinfo=timezone.utc)
            days_since_last_referral = float((now - last_converted_at).days)

        # --- 3. referral_count_30d ---
        count_30d_result = await db.execute(
            select(func.count())
            .select_from(ReferralConversion)
            .where(ReferralConversion.partner_id == partner_id)
            .where(ReferralConversion.is_synthetic == False)  # noqa: E712
            .where(ReferralConversion.converted_at >= cutoff_30d)
        )
        referral_count_30d = int(count_30d_result.scalar() or 0)

        # --- 4. referral_count_90d ---
        count_90d_result = await db.execute(
            select(func.count())
            .select_from(ReferralConversion)
            .where(ReferralConversion.partner_id == partner_id)
            .where(ReferralConversion.is_synthetic == False)  # noqa: E712
            .where(ReferralConversion.converted_at >= cutoff_90d)
        )
        referral_count_90d = int(count_90d_result.scalar() or 0)

        # --- 5. commission_trend: ratio of recent vs prior 90d conversion value ---
        recent_result = await db.execute(
            select(func.coalesce(func.sum(ReferralConversion.conversion_value), 0))
            .where(ReferralConversion.partner_id == partner_id)
            .where(ReferralConversion.is_synthetic == False)  # noqa: E712
            .where(ReferralConversion.converted_at >= cutoff_90d)
        )
        recent_90d = float(recent_result.scalar() or 0.0)

        prior_result = await db.execute(
            select(func.coalesce(func.sum(ReferralConversion.conversion_value), 0))
            .where(ReferralConversion.partner_id == partner_id)
            .where(ReferralConversion.is_synthetic == False)  # noqa: E712
            .where(ReferralConversion.converted_at >= cutoff_180d)
            .where(ReferralConversion.converted_at < cutoff_90d)
        )
        prior_90d = float(prior_result.scalar() or 0.0)

        commission_trend = recent_90d / (prior_90d + 1.0)

        features: dict = {
            "days_since_last_referral": days_since_last_referral,
            "referral_count_30d": referral_count_30d,
            "referral_count_90d": referral_count_90d,
            "commission_trend": commission_trend,
            "tier_rank": int(tier_rank) if tier_rank is not None else 1,
        }

        # --- Score ---
        predictor = ChurnPredictor()
        score: float = predictor.predict(features)

        # SHAP explanation for GradientBoosting churn model.
        churn_top_factors: dict = {}
        churn_explanation: Optional[str] = None
        try:
            churn_top_factors = Explainer().explain_tree(
                predictor._pipeline, features, CHURN_FEATURE_NAMES
            )
            churn_explanation = Explainer().to_plain_language(
                "churn_risk", churn_top_factors
            )
        except Exception:
            pass  # missing model file still produces a score row

        # --- Persist ---
        ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="partner",
            entity_id=partner_id,
            score_type="churn_risk",
            score=Decimal(str(round(score, 2))),
            contributing_factors=churn_top_factors or None,
            explanation=churn_explanation,
            model_version="1.0",
            is_synthetic=False,
        )
        db.add(ai_score)
        await db.commit()

        logger.info("Churn score %.2f stored for partner %s", score, partner_id)

    except Exception:
        logger.exception(
            "score_churn failed for partner %s — no score stored", partner_id
        )


async def score_ranking(db: AsyncSession, partner_id: uuid.UUID) -> None:
    """Compute and persist a composite ranking score for the given partner (AI-RANK-001).

    Combines quality score, inverted churn risk, normalised referral volume, and
    normalised revenue contribution using weights from the 'ranking.weights' setting
    (default: quality=0.4, churn=0.2, volume=0.2, revenue=0.2).

    Normalisation divides each partner's raw counter by the maximum observed across
    all active non-synthetic partners so the output is always 0–100.

    All exceptions are caught and logged — this function never raises.

    Args:
        db:         SQLAlchemy async session.
        partner_id: PK of the Partner row to score.
    """
    try:
        # 1. Load partner (non-synthetic only)
        partner = await db.scalar(
            select(Partner)
            .where(Partner.id == partner_id)
            .where(Partner.is_synthetic == False)  # noqa: E712
        )
        if partner is None:
            logger.warning("score_ranking: partner %s not found or synthetic — skipping", partner_id)
            return

        # 2. Load ranking weights from settings
        weights = await SettingService(db).get(
            "ranking.weights",
            {"quality": 0.4, "churn": 0.2, "volume": 0.2, "revenue": 0.2},
        )
        if not isinstance(weights, dict):
            weights = {"quality": 0.4, "churn": 0.2, "volume": 0.2, "revenue": 0.2}

        # 3. Latest quality score for this partner (default 50 when not yet scored)
        quality_raw = await db.scalar(
            select(AIScore.score)
            .where(AIScore.entity_id == partner_id)
            .where(AIScore.score_type == "quality")
            .where(AIScore.is_synthetic == False)  # noqa: E712
            .order_by(AIScore.calculated_at.desc())
            .limit(1)
        )
        quality_score = float(quality_raw) if quality_raw is not None else 50.0

        # 4. Latest churn_risk score, inverted so higher = better (default 50)
        churn_raw = await db.scalar(
            select(AIScore.score)
            .where(AIScore.entity_id == partner_id)
            .where(AIScore.score_type == "churn_risk")
            .where(AIScore.is_synthetic == False)  # noqa: E712
            .order_by(AIScore.calculated_at.desc())
            .limit(1)
        )
        churn_score = 100.0 - float(churn_raw) if churn_raw is not None else 50.0

        # 5. Normalise volume and revenue against all active non-synthetic partners
        max_row = (await db.execute(
            select(
                func.max(Partner.total_referral_count),
                func.max(Partner.total_revenue_contribution),
            )
            .where(Partner.status == "active")
            .where(Partner.is_synthetic == False)  # noqa: E712
        )).one()
        max_vol = float(max_row[0] or 1)
        max_rev = float(max_row[1] or 1)

        volume_score = min(100.0, float(partner.total_referral_count) / max_vol * 100.0)
        revenue_score = min(100.0, float(partner.total_revenue_contribution) / max_rev * 100.0)

        # 6. Weighted composite (weights sum to 1.0 by convention)
        composite = (
            quality_score * float(weights.get("quality", 0.4))
            + churn_score * float(weights.get("churn", 0.2))
            + volume_score * float(weights.get("volume", 0.2))
            + revenue_score * float(weights.get("revenue", 0.2))
        )

        contributing_factors = {
            "quality_score": round(quality_score, 2),
            "churn_inverted": round(churn_score, 2),
            "volume_score": round(volume_score, 2),
            "revenue_score": round(revenue_score, 2),
        }
        explanation = (
            f"Composite ranking: quality {quality_score:.0f}, "
            f"churn resistance {churn_score:.0f}, "
            f"volume {volume_score:.0f}, "
            f"revenue {revenue_score:.0f}."
        )

        # 7. Persist
        ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="partner",
            entity_id=partner_id,
            score_type="ranking",
            score=Decimal(str(round(composite, 2))),
            contributing_factors=contributing_factors,
            explanation=explanation,
            model_version="1.0",
            is_synthetic=False,
        )
        db.add(ai_score)
        await db.commit()

        logger.info("Ranking score %.2f stored for partner %s", composite, partner_id)

    except Exception:
        logger.exception(
            "score_ranking failed for partner %s — no score stored", partner_id
        )
