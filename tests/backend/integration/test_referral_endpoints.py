# -----------------------------------------------------------------------------
# tests/backend/integration/test_referral_endpoints.py
#
# TST-001 — Referral endpoint integration tests.
#
# Covers: create referral link (partner), list referral links, simulate a
# click via the public /r/{slug} redirect, and record a conversion (admin).
# The `seed` fixture provides a pre-existing partner, wallet, and referral
# link so tests start from a known state without re-registering users.
# Partner JWT is obtained via the HTTP login endpoint to also exercise the
# auth flow.
# -----------------------------------------------------------------------------

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

import uuid

from app.models.referral import ReferralClick, ReferralConversion


async def _partner_headers(client: AsyncClient) -> dict:
    """Log in as the seeded partner and return Authorization headers."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "partner@test.referrai", "password": "x"},
    )
    assert resp.status_code == 200, f"Partner login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_referral_link(client: AsyncClient, seed: dict) -> None:
    """POST /referrals/links returns 201 with a slug and referral_url."""
    headers = await _partner_headers(client)
    resp = await client.post(
        "/api/v1/referrals/links",
        json={"destination_url": "https://example.com/promo"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "slug" in body
    assert "referral_url" in body
    assert body["is_active"] is True


async def test_list_referral_links(client: AsyncClient, seed: dict) -> None:
    """GET /referrals/links returns the partner's referral links."""
    headers = await _partner_headers(client)
    resp = await client.get("/api/v1/referrals/links", headers=headers)
    assert resp.status_code == 200, resp.text
    links = resp.json()
    assert isinstance(links, list)
    # The seed fixture already created one link
    assert len(links) >= 1
    assert any(link["slug"] == seed["link_slug"] for link in links)


async def test_simulate_click_records_in_db(
    client: AsyncClient, seed: dict, engine
) -> None:
    """GET /r/{slug} returns 302 and writes a ReferralClick row to the DB."""
    resp = await client.get(
        f"/r/{seed['link_slug']}",
        follow_redirects=False,
    )
    assert resp.status_code == 302, resp.text
    assert "example.com" in resp.headers.get("location", "")

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        result = await session.execute(select(ReferralClick))
        clicks = result.scalars().all()
    assert len(clicks) == 1
    assert clicks[0].referral_link_id == seed["link_id"]


async def test_record_conversion(
    client: AsyncClient, seed: dict, engine
) -> None:
    """POST /referrals/conversions (admin) returns 201 and persists a conversion row."""
    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "partner_id": str(seed["partner_id"]),
            "conversion_value": "150.00",
        },
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "id" in body

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        conv = await session.get(ReferralConversion, uuid.UUID(body["id"]))
    assert conv is not None
    assert float(conv.conversion_value) == 150.00
