# -----------------------------------------------------------------------------
# tests/backend/conftest.py
#
# Shared fixtures for all backend integration and unit tests.
#
# Database strategy: each test gets an isolated in-memory SQLite database via
# StaticPool (single connection). The `seed` fixture writes all prerequisite
# rows and closes its session before yielding, so the StaticPool connection is
# available for the HTTP client's sessions. Verification sessions are opened
# after each HTTP call completes (after which the route session is also closed).
#
# Run from repo root:
#   pip install -r requirements-test.txt
#   PYTHONPATH=backend pytest
# -----------------------------------------------------------------------------

import os
import pathlib
import sys

# Override DATABASE_URL before the app modules are imported so that
# app.core.database does not try to load asyncpg (a PostgreSQL driver that is
# not required for the SQLite-backed test suite).
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

# Ensure the backend package is importable when pytest is run from the repo root.
_BACKEND_DIR = pathlib.Path(__file__).parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import uuid  # noqa: E402
from decimal import Decimal  # noqa: E402
from typing import AsyncGenerator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler  # noqa: E402

# SQLite does not have a native JSONB type. Patch its type compiler so that
# `create_all()` renders JSONB columns as plain JSON (TEXT storage on SQLite).
if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"

from app.core.database import get_db  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Partner, User, Wallet  # noqa: E402
from app.models.referral import ReferralClick, ReferralLink  # noqa: E402


@pytest_asyncio.fixture
async def engine():
    """Fresh in-memory SQLite engine per test; StaticPool shares one connection."""
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with the DB dependency wired to the test engine."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed(engine) -> dict:
    """Seed an admin user, a partner with wallet, and a referral link.

    The session is closed before yielding so the single StaticPool connection
    is free for the HTTP client when the test makes its first request.

    Yields a dict with:
        admin_headers  – Authorization header for the admin user
        partner_id     – UUID of the seeded partner
        wallet_id      – UUID of the partner's wallet
        link_slug      – slug of the seeded referral link
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)

    admin_id = uuid.uuid4()
    partner_user_id = uuid.uuid4()
    partner_id = uuid.uuid4()
    wallet_id = uuid.uuid4()
    link_id = uuid.uuid4()
    slug = "tst-slug"

    async with factory() as session:
        admin = User(
            id=admin_id,
            email="admin@test.referrai",
            password_hash=hash_password("x"),
            role="admin",
            is_active=True,
        )
        session.add(admin)

        partner_user = User(
            id=partner_user_id,
            email="partner@test.referrai",
            password_hash=hash_password("x"),
            role="partner",
            is_active=True,
        )
        session.add(partner_user)
        await session.flush()

        partner = Partner(
            id=partner_id,
            user_id=partner_user_id,
            name="Test Partner",
            email="partner@test.referrai",
            status="active",
            total_referral_count=0,
            total_revenue_contribution=Decimal("0.00"),
            is_synthetic=False,
        )
        session.add(partner)
        await session.flush()

        wallet = Wallet(
            id=wallet_id,
            partner_id=partner_id,
            balance=Decimal("0.00"),
            total_earned=Decimal("0.00"),
            total_withdrawn=Decimal("0.00"),
        )
        session.add(wallet)

        link = ReferralLink(
            id=link_id,
            partner_id=partner_id,
            slug=slug,
            destination_url="https://example.com/landing",
            is_active=True,
        )
        session.add(link)
        await session.commit()
    # Context manager exit closes the session and returns the connection to StaticPool.

    admin_token = create_access_token(
        subject=str(admin_id),
        role="admin",
        email="admin@test.referrai",
    )
    return {
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "partner_id": partner_id,
        "wallet_id": wallet_id,
        "link_id": link_id,
        "link_slug": slug,
    }


@pytest_asyncio.fixture
async def seed_click(engine, seed: dict) -> uuid.UUID:
    """Insert a ReferralClick row for the seeded link/partner.

    POST /referrals/conversions does not accept partner_id directly — it
    derives partner_id from click_id (via referral_clicks.partner_id) or
    referral_code — so tests need a real click row to post against.
    """
    click_id = uuid.uuid4()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            ReferralClick(
                id=click_id,
                referral_link_id=seed["link_id"],
                partner_id=seed["partner_id"],
                is_synthetic=False,
            )
        )
        await session.commit()
    return click_id
