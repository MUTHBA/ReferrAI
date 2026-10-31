# -----------------------------------------------------------------------------
# backend/app/services/ai_service.py
#
# AI scoring jobs (quality, fraud, churn, ranking). They run AFTER the core
# business transaction — as FastAPI background tasks or scheduled batches —
# and can never block or roll back referral tracking or commissions.
#
# Graceful degradation: if a model has not been trained, or prediction fails,
# the row is stored with score = NULL and status 'model_unavailable'/'error'
# (never a made-up value). Fraud still runs its deterministic rules without
# the model. Model inference runs in a worker thread (anyio.to_thread) so the
# event loop is never blocked.
#
# Fraud flags: raised (status 'pending_review') when the combined fraud score
# is above the fraud.alert_threshold setting, at most one open flag per
# partner per 24h. Accounts are NEVER suspended automatically.
#
# Background tasks must be scheduled with run_in_new_session(fn, entity_id):
# FastAPI closes the request's DB session before background tasks run.
# -----------------------------------------------------------------------------

import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

import anyio
from sqlalchemy import func, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import explain, registry
from app.ai.features import (
    churn_features,
    fraud_features,
    load_churn_inputs,
    load_fraud_inputs,
    load_quality_inputs,
    quality_features,
)
from app.ai.scoring.fraud_rules import FraudRuleEngine
from app.models.ai_score import AIScore
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner
from app.repositories.ai_score_repository import AIScoreRepository
from app.repositories.fraud_flag_repository import FraudFlagRepository
from app.services.setting_service import SettingService

logger = logging.getLogger(__name__)

RULE_LABELS = {
    FraudRuleEngine.RULE_CLICKS_PER_HOUR: "too many clicks from one IP in an hour",
    FraudRuleEngine.RULE_DEVICE_SPREAD: "same device clicked many different partners",
    FraudRuleEngine.RULE_SELF_REFERRAL: "IP already converted for this partner (possible self-referral)",
}


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------
async def run_in_new_session(func, *args) -> None:
    """Run `func(session, *args)` in its own session; never raises."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            await func(session, *args)
        except Exception:
            logger.exception("Background AI task %s failed", getattr(func, "__name__", func))
            await session.rollback()


async def score_all_active_partners(func) -> int:
    """Run a partner-level scorer for every active, non-synthetic partner, each
    in its own session. Returns the number of partners attempted."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        ids = list(
            (
                await session.execute(
                    select(Partner.id).where(Partner.status == "active").where(Partner.is_synthetic == False)  # noqa: E712
                )
            ).scalars()
        )
    for partner_id in ids:
        await run_in_new_session(func, partner_id)
    return len(ids)


async def _predict(name: str, features: dict, subject: str):
    """Return (score|None, status, factors|None, explanation|None, version|None)."""
    bundle = registry.get(name)
    if bundle is None:
        return None, "model_unavailable", None, f"{subject}: model not trained yet.", None

    score_fn = (lambda x: registry.predict_fraud(bundle, x)) if name == "fraud" else (lambda x: registry.predict_proba(bundle, x))

    def _run():
        score = score_fn(features)
        factors, text = explain.explain(bundle, features, score, score_fn, subject)
        return score, factors, text

    try:
        score, factors, text = await anyio.to_thread.run_sync(_run)
    except Exception:
        logger.exception("%s model prediction failed", name)
        return None, "error", {"inputs": features}, f"{subject}: scoring failed.", bundle.version
    return score, "ok", factors, text, bundle.version


def _dec(score: Optional[float]) -> Optional[Decimal]:
    return None if score is None else Decimal(str(round(max(0.0, min(100.0, score)), 2)))


async def _store(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    score_type: str,
    score: Optional[float],
    status: str,
    factors: Optional[dict],
    explanation: Optional[str],
    version: Optional[str],
) -> AIScore:
    row = AIScore(
        id=uuid.uuid4(),
        entity_type=entity_type,
        entity_id=entity_id,
        score_type=score_type,
        score=_dec(score),
        status=status,
        contributing_factors=factors,
        explanation=explanation,
        model_version=version,
        is_synthetic=False,
    )
    return await AIScoreRepository(db).create(row)


# ---------------------------------------------------------------------------
# Quality (per conversion)
# ---------------------------------------------------------------------------
async def score_referral_quality(db: AsyncSession, conversion_id: uuid.UUID) -> None:
    loaded = await load_quality_inputs(db, conversion_id)
    if loaded is None:
        logger.warning("score_referral_quality: conversion %s not found", conversion_id)
        return
    features = quality_features(*loaded)
    score, status, factors, text, version = await _predict("quality", features, "Referral quality")
    await _store(db, "referral", conversion_id, "quality", score, status, factors, text, version)
    await db.commit()


# ---------------------------------------------------------------------------
# Fraud (per click)
# ---------------------------------------------------------------------------
async def score_fraud(db: AsyncSession, click_id: uuid.UUID) -> None:
    loaded = await load_fraud_inputs(db, click_id)
    if loaded is None:
        logger.warning("score_fraud: click %s not found", click_id)
        return
    click, history = loaded
    settings_svc = SettingService(db)
    rule_weight = float(await settings_svc.get("fraud.rule_weight"))
    threshold = float(await settings_svc.get("fraud.alert_threshold"))

    triggered = await FraudRuleEngine(db).check(click_id)
    features = fraud_features(click, history)
    ml_score, status, factors, text, version = await _predict("fraud", features, "Fraud risk")

    rule_score = min(100.0, rule_weight * len(triggered))
    if ml_score is None:
        # Model unavailable: the deterministic rules still protect the platform.
        combined = rule_score
        status, version = "ok", "rules-only"
        text = "Fraud model not trained yet; score is from rules only."
    else:
        combined = min(100.0, ml_score + rule_score)
    factors = {**(factors or {"inputs": features}), "ml_score": ml_score, "triggered_rules": triggered}
    if triggered:
        text = f"{text} Rules triggered: " + "; ".join(RULE_LABELS.get(r, r) for r in triggered) + "."

    click_row = await _store(db, "referral", click_id, "fraud_risk", combined, status, factors, text, version)
    partner_row = await _store(db, "partner", click.partner_id, "fraud_risk", combined, status, factors, text, version)

    if combined > threshold:
        # Serialise flag creation per partner: background tasks for rapid
        # consecutive clicks run concurrently and would otherwise both see
        # "no open flag yet". The lock is released when the transaction ends.
        await db.execute(sql_text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"fraud-flag:{click.partner_id}"})
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        if not await FraudFlagRepository(db).has_open_flag_since(click.partner_id, since):
            await FraudFlagRepository(db).create(
                FraudFlag(
                    id=uuid.uuid4(),
                    partner_id=click.partner_id,
                    ai_score_id=partner_row.id,
                    referral_click_id=click_id,
                    status="pending_review",
                )
            )
            logger.warning("Fraud flag raised for partner %s (score %.1f)", click.partner_id, combined)
    _ = click_row
    await db.commit()


# ---------------------------------------------------------------------------
# Churn (per partner)
# ---------------------------------------------------------------------------
MIN_CHURN_TENURE_DAYS = 30  # the churn model is trained on partners at least this old


async def score_churn(db: AsyncSession, partner_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    loaded = await load_churn_inputs(db, partner_id, now)
    if loaded is None:
        return
    features = churn_features(loaded[0], now, loaded[1], loaded[2])
    if features["tenure_days"] < MIN_CHURN_TENURE_DAYS:
        await _store(
            db, "partner", partner_id, "churn_risk", None, "insufficient_data", {"inputs": features},
            f"Churn risk: partner joined less than {MIN_CHURN_TENURE_DAYS} days ago — not enough history yet.", None,
        )
        await db.commit()
        return
    score, status, factors, text, version = await _predict("churn", features, "Churn risk")
    await _store(db, "partner", partner_id, "churn_risk", score, status, factors, text, version)
    await db.commit()


# ---------------------------------------------------------------------------
# Ranking (per partner, deterministic composite)
# ---------------------------------------------------------------------------
async def score_ranking(db: AsyncSession, partner_id: uuid.UUID) -> None:
    """Weighted composite of quality, churn resistance, volume and revenue.

    Volume and revenue are normalised against the best active real partner.
    A component with no data yet (no quality or churn score) counts as a
    neutral 50 and is reported as such in contributing_factors.
    """
    partner = await db.scalar(
        select(Partner).where(Partner.id == partner_id).where(Partner.is_synthetic == False)  # noqa: E712
    )
    if partner is None:
        return
    weights = await SettingService(db).get("ranking.weights")
    scores = AIScoreRepository(db)

    quality = (await scores.partner_quality_averages([partner_id])).get(partner_id)
    churn_row = await scores.get_latest(partner_id, "churn_risk", "partner")
    churn = float(churn_row.score) if churn_row is not None and churn_row.score is not None else None

    max_vol, max_rev = (
        await db.execute(
            select(func.max(Partner.total_referral_count), func.max(Partner.total_revenue_contribution))
            .where(Partner.status == "active")
            .where(Partner.is_synthetic == False)  # noqa: E712
        )
    ).one()
    volume = 100.0 * partner.total_referral_count / float(max_vol) if max_vol else 0.0
    revenue = 100.0 * float(partner.total_revenue_contribution) / float(max_rev) if max_rev else 0.0

    components = {
        "quality": quality if quality is not None else 50.0,
        "churn": (100.0 - churn) if churn is not None else 50.0,
        "volume": min(100.0, volume),
        "revenue": min(100.0, revenue),
    }
    total_w = sum(float(weights[k]) for k in components) or 1.0
    composite = sum(components[k] * float(weights[k]) for k in components) / total_w

    factors = {
        "components": {k: round(v, 2) for k, v in components.items()},
        "weights": weights,
        "neutral_defaults": [k for k, v in (("quality", quality), ("churn", churn)) if v is None],
    }
    text = (
        f"Ranking {composite:.0f}/100 — quality {components['quality']:.0f}, "
        f"churn resistance {components['churn']:.0f}, volume {components['volume']:.0f}, "
        f"revenue {components['revenue']:.0f}."
    )
    await _store(db, "partner", partner_id, "ranking", composite, "ok", factors, text, "ranking-weighted")
    await db.commit()
