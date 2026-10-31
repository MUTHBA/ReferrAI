# -----------------------------------------------------------------------------
# tests/backend/conftest.py
#
# Shared fixtures for the backend test suite.
#
# Database: tests run against a REAL PostgreSQL database so row locks
# (SELECT ... FOR UPDATE), CHECK constraints, JSONB and timezone handling
# behave exactly as in production. Point TEST_DATABASE_URL at an empty
# database you don't mind being wiped, e.g.
#
#   createdb referrai_test
#   export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/referrai_test
#   PYTHONPATH=backend pytest
#
# or with Docker:  docker compose up -d db  (then use the compose credentials).
#
# The schema is created once per session from the ORM metadata. Every test
# starts from empty tables re-seeded with the canonical settings (from
# app/core/setting_definitions.py) and the Bronze base tier, matching what
# the Alembic seed migrations install in a real deployment.
# -----------------------------------------------------------------------------

import os
import pathlib
import sys

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://referrai:referrai@localhost:5432/referrai_test",
)
# Must be set before any app module is imported: background tasks and batch
# jobs open sessions from app.core.database directly.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DB_NULL_POOL"] = "true"
os.environ["ENV"] = "test"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
# Empty model dir by default: tests that need trained models use the
# `trained_models` fixture, everything else sees "model not trained".
import tempfile  # noqa: E402

os.environ["AI_MODEL_DIR"] = tempfile.mkdtemp(prefix="referrai-models-empty-")

_BACKEND_DIR = pathlib.Path(__file__).parents[2] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import uuid  # noqa: E402
from decimal import Decimal  # noqa: E402
from typing import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.database import get_db  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.core.setting_definitions import SETTING_DEFINITIONS  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Partner, PartnerTier, Setting, User, Wallet  # noqa: E402
from app.models.referral import ReferralLink  # noqa: E402

_schema_ready = False


async def _reset_schema(eng) -> None:
    global _schema_ready
    async with eng.begin() as conn:
        if not _schema_ready:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            _schema_ready = True
        else:
            tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


async def seed_reference_data(session: AsyncSession) -> PartnerTier:
    """Canonical settings + Bronze base tier (what the seed migrations install)."""
    for d in SETTING_DEFINITIONS.values():
        session.add(Setting(id=uuid.uuid4(), key=d.key, value=d.default, description=d.description))
    bronze = PartnerTier(
        id=uuid.uuid4(),
        name="Bronze",
        rank_order=1,
        min_referral_count=0,
        min_revenue_contribution=Decimal("0"),
        commission_type="percentage",
        commission_value=Decimal("0.10"),
    )
    session.add(bronze)
    await session.flush()
    return bronze


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    await _reset_schema(eng)
    factory = async_sessionmaker(eng, expire_on_commit=False)
    async with factory() as session:
        await seed_reference_data(session)
        await session.commit()
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client with the DB dependency wired to the test engine."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def auth_headers(user_id: uuid.UUID, role: str, email: str) -> dict:
    token = create_access_token(subject=str(user_id), role=role, email=email)
    return {"Authorization": f"Bearer {token}"}


async def make_partner(
    session: AsyncSession,
    *,
    email: str,
    name: str = "Partner",
    balance: Decimal = Decimal("0.00"),
    status: str = "active",
    tier_id: uuid.UUID | None = None,
    is_synthetic: bool = False,
) -> dict:
    user = User(id=uuid.uuid4(), email=email, password_hash=hash_password("x"), role="partner", is_active=True)
    session.add(user)
    await session.flush()
    partner = Partner(
        id=uuid.uuid4(),
        user_id=user.id,
        name=name,
        email=email,
        status=status,
        tier_id=tier_id,
        total_referral_count=0,
        total_revenue_contribution=Decimal("0.00"),
        is_synthetic=is_synthetic,
    )
    session.add(partner)
    await session.flush()
    wallet = Wallet(
        id=uuid.uuid4(),
        partner_id=partner.id,
        balance=balance,
        total_earned=balance,
        total_withdrawn=Decimal("0.00"),
    )
    session.add(wallet)
    await session.flush()
    return {
        "user_id": user.id,
        "partner_id": partner.id,
        "wallet_id": wallet.id,
        "headers": auth_headers(user.id, "partner", email),
    }


@pytest_asyncio.fixture
async def seed(engine) -> dict:
    """Seed an admin, a partner (Bronze tier) with an empty wallet, and a referral link.

    Yields: admin_id, admin_headers, partner_id, partner_user_id, partner_headers,
    wallet_id, link_id, link_slug, bronze_tier_id.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)
    admin_id = uuid.uuid4()
    link_id = uuid.uuid4()
    slug = "tst-slug"

    async with factory() as session:
        bronze = (
            await session.execute(text("SELECT id FROM partner_tiers WHERE name = 'Bronze'"))
        ).scalar_one()
        session.add(
            User(
                id=admin_id,
                email="admin@test.referrai",
                password_hash=hash_password("x"),
                role="admin",
                is_active=True,
            )
        )
        p = await make_partner(session, email="partner@test.referrai", name="Test Partner", tier_id=bronze)
        session.add(
            ReferralLink(
                id=link_id,
                partner_id=p["partner_id"],
                slug=slug,
                destination_url="https://example.com/landing",
                is_active=True,
            )
        )
        await session.commit()

    return {
        "admin_id": admin_id,
        "admin_headers": auth_headers(admin_id, "admin", "admin@test.referrai"),
        "partner_id": p["partner_id"],
        "partner_user_id": p["user_id"],
        "partner_headers": p["headers"],
        "wallet_id": p["wallet_id"],
        "link_id": link_id,
        "link_slug": slug,
        "bronze_tier_id": bronze,
    }


@pytest.fixture(scope="session")
def trained_model_dir(tmp_path_factory) -> str:
    """Train all three models once per test session on a small synthetic world."""
    from app.ai.train import train_models
    from app.core.config import settings as app_settings

    target = str(tmp_path_factory.mktemp("models"))
    previous = app_settings.AI_MODEL_DIR
    app_settings.AI_MODEL_DIR = target
    try:
        train_models(n_partners=80, seed=3)
    finally:
        app_settings.AI_MODEL_DIR = previous
    return target


@pytest.fixture
def trained_models(trained_model_dir, monkeypatch) -> str:
    """Point the model registry at the trained models for this test."""
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "AI_MODEL_DIR", trained_model_dir)
    return trained_model_dir


@pytest.fixture
def partner_factory():
    """Expose make_partner to tests: `await partner_factory(session, email=...)`."""
    return make_partner


@pytest.fixture
def anyio_backend():
    return "asyncio"
