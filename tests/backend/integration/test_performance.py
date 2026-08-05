# -----------------------------------------------------------------------------
# tests/backend/integration/test_performance.py
#
# TST-003 — Performance baseline tests.
#
# These are single-request baseline checks, not load tests. They verify that
# individual API endpoints and AI scoring functions complete within generous
# wall-clock limits under zero concurrency. A failure here indicates a
# pathological regression (missing index, N+1 query, blocking I/O) rather than
# normal latency variation. All timings use time.perf_counter; no external
# benchmarking library is required.
# -----------------------------------------------------------------------------

import time
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.referral import ReferralClick, ReferralConversion
from app.services import ai_service

_API_LIMIT_S = 2.0
_SCORE_LIMIT_S = 1.0


@pytest_asyncio.fixture
async def perf_data(engine, seed: dict) -> dict:
    """Seed a conversion and a click row for AI scoring timing tests.

    Returns the seed dict extended with:
        conversion_id – UUID of the seeded ReferralConversion
        click_id      – UUID of the seeded ReferralClick
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)
    conversion_id = uuid.uuid4()
    click_id = uuid.uuid4()

    async with factory() as session:
        conversion = ReferralConversion(
            id=conversion_id,
            partner_id=seed["partner_id"],
            external_reference=f"perf-test-{conversion_id}",
            conversion_value=Decimal("150.00"),
            attribution_model="last_click",
            is_synthetic=False,
        )
        session.add(conversion)

        click = ReferralClick(
            id=click_id,
            referral_link_id=seed["link_id"],
            partner_id=seed["partner_id"],
            is_synthetic=False,
        )
        session.add(click)
        await session.commit()

    return {**seed, "conversion_id": conversion_id, "click_id": click_id}


async def test_api_response_under_2s(client: AsyncClient, seed: dict) -> None:
    """Each admin API endpoint must respond in under 2.0 seconds."""
    headers = seed["admin_headers"]
    endpoints = [
        "/api/v1/settings",
        "/api/v1/partners",
        "/api/v1/dashboard/admin",
    ]
    for path in endpoints:
        t0 = time.perf_counter()
        resp = await client.get(path, headers=headers)
        elapsed = time.perf_counter() - t0

        assert resp.status_code == 200, f"{path} returned {resp.status_code}"
        assert elapsed < _API_LIMIT_S, (
            f"{path} took {elapsed:.3f}s — exceeds {_API_LIMIT_S}s baseline limit"
        )


async def test_quality_scoring_under_1s(engine, perf_data: dict) -> None:
    """score_referral_quality must complete in under 1.0 second."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        t0 = time.perf_counter()
        await ai_service.score_referral_quality(session, perf_data["conversion_id"])
        elapsed = time.perf_counter() - t0

    assert elapsed < _SCORE_LIMIT_S, (
        f"score_referral_quality took {elapsed:.3f}s — exceeds {_SCORE_LIMIT_S}s baseline limit"
    )


async def test_fraud_scoring_under_1s(engine, perf_data: dict) -> None:
    """score_fraud must complete in under 1.0 second."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        t0 = time.perf_counter()
        await ai_service.score_fraud(session, perf_data["click_id"])
        elapsed = time.perf_counter() - t0

    assert elapsed < _SCORE_LIMIT_S, (
        f"score_fraud took {elapsed:.3f}s — exceeds {_SCORE_LIMIT_S}s baseline limit"
    )
