# -----------------------------------------------------------------------------
# tests/backend/integration/test_graceful_degradation.py
#
# TST-002 — Graceful degradation tests.
#
# Verifies that AI scoring failures (quality, fraud, churn) never produce an
# HTTP 500 and never corrupt core business data (conversions, commissions,
# wallet credits, click records). All AI components are mocked to raise inside
# their respective score_* functions; the outer try/except in each function
# catches the error, logs it, and returns cleanly so the background task does
# not propagate an exception through the ASGI stack.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.ai_score import AIScore
from app.models.commission import Commission
from app.models.referral import ReferralClick, ReferralConversion
from app.models.wallet import Wallet
from app.services import ai_service


async def test_conversion_succeeds_when_ai_fails(
    client: AsyncClient,
    seed: dict,
    engine,
) -> None:
    """A conversion records as 201 even when the quality scorer raises."""
    payload = {
        "partner_id": str(seed["partner_id"]),
        "conversion_value": "100.00",
    }
    # Patch the scorer class so that predict() raises inside score_referral_quality.
    # The function's outer try/except catches this and returns without writing an
    # ai_scores row — the background task itself never raises.
    with patch("app.services.ai_service.ReferralQualityScorer") as mock_cls:
        mock_cls.return_value.predict.side_effect = Exception("AI unavailable")
        resp = await client.post(
            "/api/v1/referrals/conversions",
            json=payload,
            headers=seed["admin_headers"],
        )

    assert resp.status_code == 201, resp.text
    conversion_id = uuid.UUID(resp.json()["id"])

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        conv = await session.get(ReferralConversion, conversion_id)
        assert conv is not None

        ai_result = await session.execute(
            select(AIScore)
            .where(AIScore.entity_id == conversion_id)
            .where(AIScore.score_type == "quality")
        )
        ai_row = ai_result.scalar_one_or_none()
        # Scorer raised before writing — no score row, never a 500.
        assert ai_row is None or ai_row.score is None


async def test_commission_succeeds_when_ai_fails(
    client: AsyncClient,
    seed: dict,
    engine,
) -> None:
    """Commission row and wallet credit are written even when quality scoring raises."""
    payload = {
        "partner_id": str(seed["partner_id"]),
        "conversion_value": "200.00",
    }
    with patch("app.services.ai_service.ReferralQualityScorer") as mock_cls:
        mock_cls.return_value.predict.side_effect = Exception("AI unavailable")
        resp = await client.post(
            "/api/v1/referrals/conversions",
            json=payload,
            headers=seed["admin_headers"],
        )

    assert resp.status_code == 201, resp.text
    conversion_id = uuid.UUID(resp.json()["id"])

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        commission_result = await session.execute(
            select(Commission).where(Commission.conversion_id == conversion_id)
        )
        commission = commission_result.scalar_one_or_none()
        assert commission is not None, "commission row must exist even when AI fails"
        assert commission.amount > Decimal("0.00")

        wallet_result = await session.execute(
            select(Wallet).where(Wallet.partner_id == seed["partner_id"])
        )
        wallet = wallet_result.scalar_one()
        assert wallet.balance > Decimal("0.00"), "wallet must be credited even when AI fails"


async def test_click_tracking_succeeds_when_fraud_scoring_fails(
    client: AsyncClient,
    seed: dict,
    engine,
) -> None:
    """GET /r/{slug} returns 302 and writes a click row even when fraud scoring raises."""
    slug = seed["link_slug"]
    # Patch FraudDetector so predict() raises inside score_fraud.
    # The outer try/except catches it; the background task does not propagate.
    with patch("app.services.ai_service.FraudDetector") as mock_cls:
        mock_cls.return_value.predict.side_effect = Exception("AI unavailable")
        resp = await client.get(f"/r/{slug}", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/landing"

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        click_result = await session.execute(
            select(ReferralClick).order_by(ReferralClick.clicked_at.desc()).limit(1)
        )
        click = click_result.scalar_one_or_none()
        assert click is not None, "click row must be recorded even when fraud scoring fails"


async def test_churn_scoring_failure_does_not_propagate(
    seed: dict,
    engine,
) -> None:
    """score_churn swallows predictor failures and returns without raising."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        with patch("app.services.ai_service.ChurnPredictor") as mock_cls:
            mock_cls.return_value.predict.side_effect = Exception("AI unavailable")
            # Must complete without raising — graceful degradation is the contract.
            await ai_service.score_churn(session, seed["partner_id"])
