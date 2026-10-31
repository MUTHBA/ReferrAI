# -----------------------------------------------------------------------------
# tests/backend/integration/test_performance.py
#
# NFR-PER-001/002: API responses under 2s; a single AI score (prediction +
# explanation, including the DB reads) under 1s. Uses the trained models.
# -----------------------------------------------------------------------------

import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from app.models.ai_score import AIScore
from app.models.referral import ReferralClick, ReferralConversion
from app.services import ai_service


async def _click_and_conversion(session_factory, seed) -> tuple[uuid.UUID, uuid.UUID]:
    click_id, conv_id = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(timezone.utc)
    async with session_factory() as s:
        s.add(
            ReferralClick(
                id=click_id, referral_link_id=seed["link_id"], partner_id=seed["partner_id"], ip_address="198.51.100.4",
                device_info={"user_agent": "Mozilla/5.0", "device_type": "desktop", "fingerprint": "perf"},
                source="google", clicked_at=now - timedelta(hours=3), is_synthetic=False,
            )
        )
        await s.flush()
        s.add(
            ReferralConversion(
                id=conv_id, partner_id=seed["partner_id"], click_id=click_id, referral_link_id=seed["link_id"],
                external_reference="perf-1", conversion_value=Decimal("120.00"), attribution_model="last_click",
                converted_at=now, is_synthetic=False,
            )
        )
        await s.commit()
    return click_id, conv_id


async def test_api_response_under_2s(client: AsyncClient, seed: dict) -> None:
    t = time.perf_counter()
    resp = await client.get("/api/v1/dashboard/admin", headers=seed["admin_headers"])
    assert resp.status_code == 200
    assert time.perf_counter() - t < 2.0


async def test_quality_and_fraud_scoring_under_1s(seed: dict, session_factory, trained_models) -> None:
    click_id, conv_id = await _click_and_conversion(session_factory, seed)
    for func, entity in ((ai_service.score_referral_quality, conv_id), (ai_service.score_fraud, click_id)):
        async with session_factory() as s:
            await func(s, entity)  # warm-up (model load)
        async with session_factory() as s:
            t = time.perf_counter()
            await func(s, entity)
            elapsed = time.perf_counter() - t
        assert elapsed < 1.0, f"{func.__name__} took {elapsed:.2f}s"

    async with session_factory() as s:
        q = (await s.execute(select(AIScore).where(AIScore.entity_id == conv_id))).scalars().first()
        assert q.score is not None and q.status == "ok"
