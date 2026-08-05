# -----------------------------------------------------------------------------
# tests/backend/integration/test_core_flow.py
#
# TST-001 — End-to-end integration coverage of the core platform flow:
# registration -> login -> RBAC -> settings -> referral link -> click tracking
# -> conversion -> commission -> wallet credit -> withdrawal (auto-approve,
# manual review, fraud-flag override) -> admin withdrawal approval.
#
# Uses the shared `client`/`engine` fixtures from tests/backend/conftest.py
# (isolated in-memory SQLite per test — never the dev/Postgres database).
# The conftest `seed` fixture is intentionally NOT used here: this suite
# exercises registration and login themselves as first-class behavior, so
# each test (or the `registered_users` fixture) creates its own users via the
# real HTTP endpoints rather than inserting rows directly.
#
# `settings_seeded` inserts the canonical settings rows (normally written by
# the DB-003 seed migration) that the in-memory test DB does not otherwise
# have — SettingService.set() (PUT /settings/{key}) 404s on a key with no
# existing row, so tests that update settings need it seeded first.
# -----------------------------------------------------------------------------

import uuid
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.ai_score import AIScore
from app.models.audit_log import AuditLog
from app.models.commission import Commission
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner
from app.models.referral import ReferralClick
from app.models.setting import Setting
from app.models.user import User
from app.models.wallet import Transaction, Wallet

ADMIN_EMAIL = "admin@flow.test"
ADMIN_PASSWORD = "adminpass123"
PARTNER_EMAIL = "partner@flow.test"
PARTNER_PASSWORD = "partnerpass123"
PARTNER_NAME = "Flow Partner"


# ---------------------------------------------------------------------------
# Helpers (plain async functions, not fixtures — safe to call multiple times
# within a single test to build up whatever state that test needs).
# ---------------------------------------------------------------------------


async def _register(client: AsyncClient, email: str, password: str, role: str, name: str | None = None):
    payload = {"email": email, "password": password, "role": role}
    if name is not None:
        payload["name"] = name
    return await client.post("/api/v1/auth/register", json=payload)


async def _login(client: AsyncClient, email: str, password: str):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


async def _create_referral_link(
    client: AsyncClient, headers: dict, destination_url: str = "https://merchant.example.com/thank-you"
) -> dict:
    resp = await client.post(
        "/api/v1/referrals/links",
        json={"destination_url": destination_url},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _click_link(client: AsyncClient, slug: str, expected_destination: str) -> None:
    resp = await client.get(f"/r/{slug}", follow_redirects=False)
    assert resp.status_code == 302, resp.text
    assert resp.headers["location"] == expected_destination


async def _latest_click_id(engine, referral_link_id: uuid.UUID) -> uuid.UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        click_id = (
            await session.execute(
                select(ReferralClick.id)
                .where(ReferralClick.referral_link_id == referral_link_id)
                .order_by(ReferralClick.clicked_at.desc())
                .limit(1)
            )
        ).scalar_one()
    return click_id


async def _record_conversion_via_click(
    client: AsyncClient,
    engine,
    admin_headers: dict,
    partner_headers: dict,
    conversion_value: str,
) -> dict:
    """Create a referral link, click it, and record a conversion against that click.

    Returns {"link": <link json>, "click_id": UUID, "conversion": <conversion json>}.
    """
    destination = "https://merchant.example.com/thank-you"
    link = await _create_referral_link(client, partner_headers, destination)
    await _click_link(client, link["slug"], destination)
    click_id = await _latest_click_id(engine, uuid.UUID(link["id"]))

    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={"click_id": str(click_id), "conversion_value": conversion_value},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return {"link": link, "click_id": click_id, "conversion": resp.json()}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def settings_seeded(engine) -> dict:
    """Seed the canonical settings rows this suite depends on.

    In production these rows come from the DB-003 seed migration; the
    in-memory SQLite test DB only runs Base.metadata.create_all, so tests
    that call SettingService.set() (which 404s on an unknown key) need them
    inserted directly.
    """
    values: dict = {
        "commission.default_percentage": 0.10,
        "commission.default_type": "percentage",
        "wallet.auto_approval_threshold": 100.0,
        "wallet.min_withdrawal_amount": 10.0,
        "referral.attribution_model": "last_click",
        "referral.attribution_window_days": 30,
    }
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        for key, value in values.items():
            session.add(Setting(id=uuid.uuid4(), key=key, value=value, description=None))
        await session.commit()
    return values


@pytest_asyncio.fixture
async def registered_users(client: AsyncClient, engine, settings_seeded: dict) -> dict:
    """Register + log in one admin and one partner via the real HTTP endpoints.

    Returns:
        admin_headers, admin_id, partner_headers, partner_user_id,
        partner_id (Partner.id), wallet_id (Wallet.id) — the latter two
        looked up directly from the DB since RegisterResponse doesn't expose
        them.
    """
    admin_resp = await _register(client, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    assert admin_resp.status_code == 201, admin_resp.text
    admin_id = uuid.UUID(admin_resp.json()["id"])

    admin_login = await _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert admin_login.status_code == 200, admin_login.text
    admin_token = admin_login.json()["access_token"]

    partner_resp = await _register(client, PARTNER_EMAIL, PARTNER_PASSWORD, "partner", name=PARTNER_NAME)
    assert partner_resp.status_code == 201, partner_resp.text
    partner_user_id = uuid.UUID(partner_resp.json()["id"])

    partner_login = await _login(client, PARTNER_EMAIL, PARTNER_PASSWORD)
    assert partner_login.status_code == 200, partner_login.text
    partner_token = partner_login.json()["access_token"]

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        partner_row = (
            await session.execute(select(Partner).where(Partner.user_id == partner_user_id))
        ).scalar_one()
        wallet_row = (
            await session.execute(select(Wallet).where(Wallet.partner_id == partner_row.id))
        ).scalar_one()

    return {
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "admin_id": admin_id,
        "partner_headers": {"Authorization": f"Bearer {partner_token}"},
        "partner_user_id": partner_user_id,
        "partner_id": partner_row.id,
        "wallet_id": wallet_row.id,
    }


@pytest_asyncio.fixture
async def recorded_conversion(client: AsyncClient, engine, registered_users: dict) -> dict:
    """A partner referral link, click, and admin-recorded $100 conversion.

    At the default 10% commission rate this credits the partner's wallet
    with exactly 10.00 — also the seeded wallet.min_withdrawal_amount, which
    tests 18/16/17 rely on.
    """
    result = await _record_conversion_via_click(
        client,
        engine,
        registered_users["admin_headers"],
        registered_users["partner_headers"],
        conversion_value="100.00",
    )
    return {**registered_users, **result}


# ---------------------------------------------------------------------------
# 1-3: Registration
# ---------------------------------------------------------------------------


async def test_register_admin_creates_user(client: AsyncClient, engine) -> None:
    resp = await _register(client, "admin1@flow.test", ADMIN_PASSWORD, "admin")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "admin"
    assert body["email"] == "admin1@flow.test"

    user_id = uuid.UUID(body["id"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = await session.get(User, user_id)
    assert user is not None
    assert user.role == "admin"


async def test_register_partner_creates_partner_and_wallet(client: AsyncClient, engine) -> None:
    resp = await _register(client, "partner1@flow.test", PARTNER_PASSWORD, "partner", name="Acme Co")
    assert resp.status_code == 201, resp.text
    user_id = uuid.UUID(resp.json()["id"])

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        partner = (
            await session.execute(select(Partner).where(Partner.user_id == user_id))
        ).scalar_one_or_none()
        assert partner is not None, "Partner row must be auto-created on partner registration"
        assert partner.name == "Acme Co"

        wallet = (
            await session.execute(select(Wallet).where(Wallet.partner_id == partner.id))
        ).scalar_one_or_none()
        assert wallet is not None, "Wallet row must be auto-created on partner registration"
        assert wallet.balance == Decimal("0.00")


async def test_register_partner_without_name_returns_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "noname@flow.test", "password": PARTNER_PASSWORD, "role": "partner"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 4: Login
# ---------------------------------------------------------------------------


async def test_login_returns_jwt_for_admin_and_partner(client: AsyncClient) -> None:
    await _register(client, "loginadmin@flow.test", ADMIN_PASSWORD, "admin")
    await _register(client, "loginpartner@flow.test", PARTNER_PASSWORD, "partner", name="Login Partner")

    admin_login = await _login(client, "loginadmin@flow.test", ADMIN_PASSWORD)
    assert admin_login.status_code == 200, admin_login.text
    assert admin_login.json()["access_token"]
    assert admin_login.json()["token_type"] == "bearer"

    partner_login = await _login(client, "loginpartner@flow.test", PARTNER_PASSWORD)
    assert partner_login.status_code == 200, partner_login.text
    assert partner_login.json()["access_token"]


# ---------------------------------------------------------------------------
# 5-6: RBAC on an admin-only route
# ---------------------------------------------------------------------------


async def test_partner_cannot_access_admin_settings_route(client: AsyncClient, registered_users: dict) -> None:
    resp = await client.get("/api/v1/settings", headers=registered_users["partner_headers"])
    assert resp.status_code == 403, resp.text


async def test_admin_can_access_settings_route(client: AsyncClient, registered_users: dict) -> None:
    resp = await client.get("/api/v1/settings", headers=registered_users["admin_headers"])
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# 7-9: Settings updates + audit logging
# ---------------------------------------------------------------------------


async def test_admin_setting_update_persists_and_writes_audit_log(
    client: AsyncClient, engine, registered_users: dict
) -> None:
    admin_headers = registered_users["admin_headers"]

    update_resp = await client.put(
        "/api/v1/settings/commission.default_percentage",
        json={"value": 0.15},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["value"] == 0.15

    follow_up = await client.get("/api/v1/settings", headers=admin_headers)
    assert follow_up.status_code == 200, follow_up.text
    updated = next(s for s in follow_up.json() if s["key"] == "commission.default_percentage")
    assert updated["value"] == 0.15

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        log = (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.entity_type == "setting")
                .where(AuditLog.action == "settings.updated")
                .order_by(AuditLog.created_at.desc())
            )
        ).scalars().first()

    assert log is not None
    assert log.old_value == 0.10
    assert log.new_value == 0.15
    assert log.user_id == registered_users["admin_id"]


async def test_partner_cannot_update_setting(client: AsyncClient, registered_users: dict) -> None:
    resp = await client.put(
        "/api/v1/settings/commission.default_percentage",
        json={"value": 0.99},
        headers=registered_users["partner_headers"],
    )
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# 10-12: Referral link creation + click tracking
# ---------------------------------------------------------------------------


async def test_partner_creates_referral_link(client: AsyncClient, registered_users: dict) -> None:
    resp = await client.post(
        "/api/v1/referrals/links",
        json={"destination_url": "https://merchant.example.com/landing"},
        headers=registered_users["partner_headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["slug"]
    assert body["destination_url"] == "https://merchant.example.com/landing"


async def test_referral_click_redirects_and_records_click(
    client: AsyncClient, engine, registered_users: dict
) -> None:
    destination = "https://merchant.example.com/thanks"
    link = await _create_referral_link(client, registered_users["partner_headers"], destination)

    await _click_link(client, link["slug"], destination)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        click = (
            await session.execute(
                select(ReferralClick).where(ReferralClick.referral_link_id == uuid.UUID(link["id"]))
            )
        ).scalar_one_or_none()
    assert click is not None
    assert click.referral_link_id == uuid.UUID(link["id"])


# ---------------------------------------------------------------------------
# 13-17: Conversions (admin-only, partner_id derived server-side) + commission
# + wallet credit
# ---------------------------------------------------------------------------


async def test_partner_cannot_call_conversions_endpoint(
    client: AsyncClient, engine, registered_users: dict
) -> None:
    link = await _create_referral_link(client, registered_users["partner_headers"])
    await _click_link(client, link["slug"], link["destination_url"])
    click_id = await _latest_click_id(engine, uuid.UUID(link["id"]))

    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={"click_id": str(click_id), "conversion_value": "50.00"},
        headers=registered_users["partner_headers"],
    )
    assert resp.status_code == 403, resp.text


async def test_admin_conversion_derives_partner_id_from_click(recorded_conversion: dict) -> None:
    conversion = recorded_conversion["conversion"]
    assert conversion["partner_id"] == str(recorded_conversion["partner_id"])
    assert conversion["click_id"] == str(recorded_conversion["click_id"])


async def test_admin_conversion_with_unknown_click_id_returns_404(
    client: AsyncClient, registered_users: dict
) -> None:
    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={"click_id": str(uuid.uuid4()), "conversion_value": "50.00"},
        headers=registered_users["admin_headers"],
    )
    assert resp.status_code == 404, resp.text


async def test_conversion_creates_commission_with_correct_amount(
    recorded_conversion: dict, engine, settings_seeded: dict
) -> None:
    conversion_id = uuid.UUID(recorded_conversion["conversion"]["id"])
    rate = Decimal(str(settings_seeded["commission.default_percentage"]))
    expected = (Decimal("100.00") * rate).quantize(Decimal("0.01"))

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        commission = (
            await session.execute(select(Commission).where(Commission.conversion_id == conversion_id))
        ).scalar_one_or_none()

    assert commission is not None
    assert commission.amount == expected


async def test_conversion_credits_wallet_and_writes_transaction(recorded_conversion: dict, engine) -> None:
    conversion_id = uuid.UUID(recorded_conversion["conversion"]["id"])
    wallet_id = recorded_conversion["wallet_id"]

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        wallet = await session.get(Wallet, wallet_id)
        commission = (
            await session.execute(select(Commission).where(Commission.conversion_id == conversion_id))
        ).scalar_one()
        # WalletService.credit() records the conversion's id as reference_id,
        # not the commission's id — the ledger entry references the source
        # event, and one conversion has exactly one commission.
        transaction = (
            await session.execute(
                select(Transaction)
                .where(Transaction.wallet_id == wallet_id)
                .where(Transaction.reference_id == conversion_id)
            )
        ).scalar_one_or_none()

    assert wallet.balance == commission.amount
    assert wallet.total_earned == commission.amount
    assert transaction is not None
    assert transaction.reference_type == "commission"
    assert transaction.amount == commission.amount
    assert transaction.balance_after == wallet.balance


# ---------------------------------------------------------------------------
# 18-21: Withdrawals — auto-approval, manual review, fraud-flag override,
# admin approval
# ---------------------------------------------------------------------------


async def test_withdrawal_below_threshold_auto_approves_and_debits_wallet(
    client: AsyncClient, engine, registered_users: dict, settings_seeded: dict
) -> None:
    await _record_conversion_via_click(
        client,
        engine,
        registered_users["admin_headers"],
        registered_users["partner_headers"],
        conversion_value="100.00",
    )
    wallet_id = registered_users["wallet_id"]

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        balance_before = (await session.get(Wallet, wallet_id)).balance

    withdraw_amount = balance_before  # 10.00 — below the 100.00 auto-approval threshold
    resp = await client.post(
        "/api/v1/withdrawals",
        json={"amount": str(withdraw_amount)},
        headers=registered_users["partner_headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "approved"
    assert body["requires_manual_review"] is False

    async with factory() as session:
        wallet_after = await session.get(Wallet, wallet_id)
        transaction = (
            await session.execute(
                select(Transaction)
                .where(Transaction.wallet_id == wallet_id)
                .where(Transaction.reference_id == uuid.UUID(body["id"]))
            )
        ).scalar_one_or_none()

    assert wallet_after.balance == balance_before - withdraw_amount
    assert transaction is not None
    assert transaction.amount == -withdraw_amount
    assert transaction.balance_after == wallet_after.balance


async def test_withdrawal_above_threshold_requires_manual_review_and_wallet_unchanged(
    client: AsyncClient, engine, registered_users: dict, settings_seeded: dict
) -> None:
    await _record_conversion_via_click(
        client,
        engine,
        registered_users["admin_headers"],
        registered_users["partner_headers"],
        conversion_value="2000.00",  # commission 200.00 — above the 100.00 threshold
    )
    wallet_id = registered_users["wallet_id"]

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        balance_before = (await session.get(Wallet, wallet_id)).balance

    withdraw_amount = Decimal("150.00")
    assert withdraw_amount <= balance_before

    resp = await client.post(
        "/api/v1/withdrawals",
        json={"amount": str(withdraw_amount)},
        headers=registered_users["partner_headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["requires_manual_review"] is True

    async with factory() as session:
        balance_after = (await session.get(Wallet, wallet_id)).balance
    assert balance_after == balance_before, "balance must not change until an admin approves"


async def test_active_fraud_flag_forces_manual_review_below_threshold(
    client: AsyncClient, engine, registered_users: dict, settings_seeded: dict
) -> None:
    await _record_conversion_via_click(
        client,
        engine,
        registered_users["admin_headers"],
        registered_users["partner_headers"],
        conversion_value="600.00",  # commission 60.00 — enough to cover the withdrawal below
    )
    partner_id = registered_users["partner_id"]
    wallet_id = registered_users["wallet_id"]

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        ai_score = AIScore(
            id=uuid.uuid4(),
            entity_type="partner",
            entity_id=partner_id,
            score_type="fraud_risk",
            score=Decimal("90.00"),
        )
        session.add(ai_score)
        await session.flush()

        session.add(
            FraudFlag(
                id=uuid.uuid4(),
                partner_id=partner_id,
                ai_score_id=ai_score.id,
                status="pending_review",
            )
        )
        await session.commit()

        balance_before = (await session.get(Wallet, wallet_id)).balance

    withdraw_amount = Decimal("50.00")  # below the 100.00 auto-approval threshold
    assert withdraw_amount <= balance_before

    resp = await client.post(
        "/api/v1/withdrawals",
        json={"amount": str(withdraw_amount)},
        headers=registered_users["partner_headers"],
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending", "an active pending_review fraud flag must force manual review"
    assert body["requires_manual_review"] is True

    async with factory() as session:
        balance_after = (await session.get(Wallet, wallet_id)).balance
    assert balance_after == balance_before


async def test_admin_approves_pending_withdrawal_debits_wallet_and_writes_audit_log(
    client: AsyncClient, engine, registered_users: dict, settings_seeded: dict
) -> None:
    await _record_conversion_via_click(
        client,
        engine,
        registered_users["admin_headers"],
        registered_users["partner_headers"],
        conversion_value="2000.00",  # commission 200.00 — above threshold, forces pending
    )
    wallet_id = registered_users["wallet_id"]

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        balance_before = (await session.get(Wallet, wallet_id)).balance

    withdraw_amount = Decimal("150.00")
    create_resp = await client.post(
        "/api/v1/withdrawals",
        json={"amount": str(withdraw_amount)},
        headers=registered_users["partner_headers"],
    )
    assert create_resp.status_code == 201, create_resp.text
    withdrawal_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending"

    approve_resp = await client.patch(
        f"/api/v1/withdrawals/{withdrawal_id}",
        json={"status": "approved"},
        headers=registered_users["admin_headers"],
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["status"] == "approved"

    async with factory() as session:
        balance_after = (await session.get(Wallet, wallet_id)).balance
        log = (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.entity_type == "withdrawal")
                .where(AuditLog.entity_id == uuid.UUID(withdrawal_id))
            )
        ).scalar_one_or_none()

    assert balance_after == balance_before - withdraw_amount
    assert log is not None
    assert log.action == "withdrawal.approved"
    assert log.user_id == registered_users["admin_id"]
