# -----------------------------------------------------------------------------
# tests/backend/unit/test_referral_service.py
#
# Unit tests for ReferralConversionService.record_conversion().
#
# Covers:
#   - Successful first-time conversion records a row and returns it.
#   - DuplicateConversionError is raised (not caught) when the same
#     partner_id + external_reference is submitted a second time.
#   - The route layer translates DuplicateConversionError into HTTP 409.
#
# These tests exercise the full HTTP stack via the test client (same engine as
# integration tests) so they also verify the route's error handling without
# mocking the service layer.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.commission import Commission
from app.models.referral import ReferralClick, ReferralConversion, ReferralLink


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _admin_headers(client: AsyncClient, seed: dict) -> dict:
    return seed["admin_headers"]


def _conversion_payload(click_id: uuid.UUID, reference: str, value: str = "100.00") -> dict:
    return {
        "click_id": str(click_id),
        "external_reference": reference,
        "conversion_value": value,
    }


async def _click_for_partner(engine, partner_id: uuid.UUID) -> uuid.UUID:
    """Insert a fresh referral link + click for an arbitrary partner.

    POST /referrals/conversions derives partner_id from click_id, so tests
    that need a conversion attributed to a specific partner (e.g. a
    second, non-seeded partner) need a real click row for that partner.
    """
    link_id = uuid.uuid4()
    click_id = uuid.uuid4()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            ReferralLink(
                id=link_id,
                partner_id=partner_id,
                slug=f"unit-{click_id}",
                destination_url="https://example.com/landing",
                is_active=True,
            )
        )
        await session.flush()
        session.add(
            ReferralClick(
                id=click_id,
                referral_link_id=link_id,
                partner_id=partner_id,
                is_synthetic=False,
            )
        )
        await session.commit()
    return click_id


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

async def test_record_conversion_creates_row(
    client: AsyncClient, seed: dict, seed_click: uuid.UUID, engine
) -> None:
    """A valid first conversion returns 201 with external_reference in the body."""
    resp = await client.post(
        "/api/v1/referrals/conversions",
        json=_conversion_payload(seed_click, "unit-ref-001"),
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["external_reference"] == "unit-ref-001"
    assert body["partner_id"] == str(seed["partner_id"])

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        row = await session.get(ReferralConversion, uuid.UUID(body["id"]))
    assert row is not None
    assert row.external_reference == "unit-ref-001"


async def test_record_conversion_credits_wallet(
    client: AsyncClient, seed: dict, seed_click: uuid.UUID, engine
) -> None:
    """A successful conversion creates a commission row for the partner."""
    resp = await client.post(
        "/api/v1/referrals/conversions",
        json=_conversion_payload(seed_click, "unit-ref-002", "500.00"),
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 201, resp.text

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        count = (
            await session.execute(
                select(func.count()).select_from(Commission).where(
                    Commission.partner_id == seed["partner_id"]
                )
            )
        ).scalar_one()
    assert count == 1


# ---------------------------------------------------------------------------
# Idempotency — duplicate rejection
# ---------------------------------------------------------------------------

async def test_duplicate_external_reference_returns_409(
    client: AsyncClient, seed: dict, seed_click: uuid.UUID
) -> None:
    """Second POST with the same partner_id + external_reference returns 409."""
    payload = _conversion_payload(seed_click, "unit-ref-dupe")

    resp1 = await client.post(
        "/api/v1/referrals/conversions", json=payload, headers=seed["admin_headers"]
    )
    assert resp1.status_code == 201, resp1.text

    resp2 = await client.post(
        "/api/v1/referrals/conversions", json=payload, headers=seed["admin_headers"]
    )
    assert resp2.status_code == 409, resp2.text


async def test_duplicate_rejection_message_contains_reference(
    client: AsyncClient, seed: dict, seed_click: uuid.UUID
) -> None:
    """The 409 detail message includes the offending external_reference."""
    ref = "unit-ref-msg-check"
    payload = _conversion_payload(seed_click, ref)

    await client.post(
        "/api/v1/referrals/conversions", json=payload, headers=seed["admin_headers"]
    )
    resp = await client.post(
        "/api/v1/referrals/conversions", json=payload, headers=seed["admin_headers"]
    )
    assert resp.status_code == 409
    assert ref in resp.json()["detail"]


async def test_duplicate_does_not_create_second_conversion_row(
    client: AsyncClient, seed: dict, seed_click: uuid.UUID, engine
) -> None:
    """After a 409, exactly one ReferralConversion row exists for that reference."""
    ref = "unit-ref-no-dupe-row"
    payload = _conversion_payload(seed_click, ref)

    await client.post(
        "/api/v1/referrals/conversions", json=payload, headers=seed["admin_headers"]
    )
    await client.post(
        "/api/v1/referrals/conversions", json=payload, headers=seed["admin_headers"]
    )

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        count = (
            await session.execute(
                select(func.count()).select_from(ReferralConversion).where(
                    ReferralConversion.partner_id == seed["partner_id"],
                    ReferralConversion.external_reference == ref,
                )
            )
        ).scalar_one()
    assert count == 1


async def test_duplicate_does_not_create_second_commission(
    client: AsyncClient, seed: dict, seed_click: uuid.UUID, engine
) -> None:
    """After a 409, exactly one Commission row exists for that partner."""
    ref = "unit-ref-no-dupe-commission"
    payload = _conversion_payload(seed_click, ref)

    await client.post(
        "/api/v1/referrals/conversions", json=payload, headers=seed["admin_headers"]
    )
    await client.post(
        "/api/v1/referrals/conversions", json=payload, headers=seed["admin_headers"]
    )

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        count = (
            await session.execute(
                select(func.count()).select_from(Commission).where(
                    Commission.partner_id == seed["partner_id"]
                )
            )
        ).scalar_one()
    assert count == 1


async def test_same_reference_different_partner_is_allowed(
    client: AsyncClient, seed: dict, seed_click: uuid.UUID, engine
) -> None:
    """The same external_reference is allowed for two different partners (constraint is per-partner)."""
    # Register a second partner
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "partner2@unit.test", "password": "password2", "name": "P2", "role": "partner"},
    )
    assert reg.status_code in (200, 201), reg.text
    partner2_id_str = None

    # Get the second partner's id from the partners table via DB
    factory = async_sessionmaker(engine, expire_on_commit=False)
    from app.models import Partner
    async with factory() as session:
        from sqlalchemy import select as sa_select
        row = (
            await session.execute(
                sa_select(Partner).where(Partner.email == "partner2@unit.test")
            )
        ).scalar_one_or_none()
        if row is None:
            pytest.skip("Second partner profile not auto-created; skipping cross-partner test")
        partner2_id_str = str(row.id)

    partner2_click = await _click_for_partner(engine, uuid.UUID(partner2_id_str))
    shared_ref = "shared-order-xyz"

    resp1 = await client.post(
        "/api/v1/referrals/conversions",
        json=_conversion_payload(seed_click, shared_ref),
        headers=seed["admin_headers"],
    )
    assert resp1.status_code == 201, resp1.text

    resp2 = await client.post(
        "/api/v1/referrals/conversions",
        json=_conversion_payload(partner2_click, shared_ref),
        headers=seed["admin_headers"],
    )
    assert resp2.status_code == 201, resp2.text
