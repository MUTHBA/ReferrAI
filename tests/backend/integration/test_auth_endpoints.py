# -----------------------------------------------------------------------------
# tests/backend/integration/test_auth_endpoints.py
#
# TST-001 — Auth endpoint integration tests.
#
# Covers: partner registration (201), duplicate-email rejection (409),
# successful login returning a JWT, and wrong-password rejection (401).
# Uses the bare `client` fixture (no pre-seeded data) so each test registers
# its own user and avoids email conflicts with the shared `seed` fixture.
# -----------------------------------------------------------------------------

from httpx import AsyncClient

_EMAIL = "newpartner@test.referrai"
_PASSWORD = "strongpass1"
_REGISTER_PAYLOAD = {
    "email": _EMAIL,
    "password": _PASSWORD,
    "role": "partner",
    "name": "New Partner",
}


async def test_register_partner(client: AsyncClient) -> None:
    """POST /auth/register with valid partner payload returns 201 and user data."""
    resp = await client.post("/api/v1/auth/register", json=_REGISTER_PAYLOAD)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == _EMAIL
    assert body["role"] == "partner"
    assert "id" in body


async def test_register_duplicate_email_rejected(client: AsyncClient) -> None:
    """Registering the same email twice returns 409."""
    await client.post("/api/v1/auth/register", json=_REGISTER_PAYLOAD)
    resp = await client.post("/api/v1/auth/register", json=_REGISTER_PAYLOAD)
    assert resp.status_code == 409, resp.text


async def test_login_returns_token(client: AsyncClient) -> None:
    """POST /auth/login with correct credentials returns an access token."""
    await client.post("/api/v1/auth/register", json=_REGISTER_PAYLOAD)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": _EMAIL, "password": _PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    """POST /auth/login with wrong password returns 401."""
    await client.post("/api/v1/auth/register", json=_REGISTER_PAYLOAD)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": _EMAIL, "password": "wrongpassword"},
    )
    assert resp.status_code == 401, resp.text


async def test_login_unknown_email_rejected(client: AsyncClient) -> None:
    """POST /auth/login for an email that was never registered returns 401."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.referrai", "password": "doesnotmatter"},
    )
    assert resp.status_code == 401, resp.text
