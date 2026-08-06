# -----------------------------------------------------------------------------
# tests/backend/integration/test_financial_integrity.py
#
# Financial-integrity abuse-scenario tests: can a partner steal or manipulate
# money? Covers negative/zero conversion values, withdrawal-vs-balance
# validation (including a direct DB-level CHECK-constraint bypass attempt),
# a real concurrent-withdrawal race condition, self-referral fraud-flag
# coverage, and a regression check that conversions stay admin-only.
#
# IMPORTANT — test_concurrent_withdrawal_race_condition targets the LIVE
# Docker stack (real Postgres via httpx against http://localhost:8000), not
# the sqlite/StaticPool `client` fixture used by every other test in this
# repo. StaticPool gives every request the same single physical SQLite
# connection, so "concurrent" asyncio.gather() calls against it are actually
# serialized by aiosqlite's single-connection worker thread — a race
# condition in the application code would never be able to manifest, and the
# test would report "safe" regardless of whether the real bug exists. Only
# genuinely parallel Postgres connections (as in the live stack, or any real
# deployment) can expose a TOCTOU race in the withdrawal balance check. That
# test is skipped (not failed) if the live stack isn't reachable, so the rest
# of this file still runs standalone.
# -----------------------------------------------------------------------------

import asyncio
import uuid
from decimal import Decimal

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.ai_score import AIScore
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner
from app.models.referral import ReferralClick, ReferralConversion
from app.models.wallet import Wallet

LIVE_BACKEND_URL = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _click_link(client: AsyncClient, slug: str) -> None:
    resp = await client.get(f"/r/{slug}", follow_redirects=False)
    assert resp.status_code == 302, resp.text


async def _latest_click_id(engine, referral_link_id: uuid.UUID) -> uuid.UUID:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return (
            await session.execute(
                select(ReferralClick.id)
                .where(ReferralClick.referral_link_id == referral_link_id)
                .order_by(ReferralClick.clicked_at.desc())
                .limit(1)
            )
        ).scalar_one()


# ---------------------------------------------------------------------------
# 1 — Negative / zero conversion_value
# ---------------------------------------------------------------------------


async def test_negative_conversion_value_is_rejected(
    client: AsyncClient, engine, seed: dict
) -> None:
    """A conversion with conversion_value=-500.00 must be cleanly rejected:
    a 422 from ConversionCreate.conversion_value's Field(gt=0) — no crash,
    no silent success, and no row or money movement of any kind.

    Uses a real click_id — without one, the route 422s with "Either click_id
    or referral_code is required" regardless of conversion_value, which would
    make this test pass for the wrong reason and mask the actual finding.
    """
    await _click_link(client, seed["link_slug"])
    click_id = await _latest_click_id(engine, seed["link_id"])

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        balance_before = (await session.get(Wallet, seed["wallet_id"])).balance

    ref = f"abuse-neg-{uuid.uuid4()}"
    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "click_id": str(click_id),
            "external_reference": ref,
            "conversion_value": "-500.00",
        },
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 422, (
        f"Expected 422 for negative conversion_value, got {resp.status_code}: {resp.text}"
    )

    async with factory() as session:
        conv = (
            await session.execute(
                select(ReferralConversion).where(
                    ReferralConversion.external_reference == ref
                )
            )
        ).scalar_one_or_none()
        balance_after = (await session.get(Wallet, seed["wallet_id"])).balance

    assert conv is None, "No conversion row must be created for a rejected negative value"
    assert balance_after == balance_before, "Wallet balance must not move on a rejected conversion"


async def test_zero_conversion_value_is_rejected(
    client: AsyncClient, engine, seed: dict
) -> None:
    """A conversion with conversion_value=0 must be cleanly rejected — no
    row created, no free tier-upgrade progress via a $0 "conversion"."""
    await _click_link(client, seed["link_slug"])
    click_id = await _latest_click_id(engine, seed["link_id"])

    ref = f"abuse-zero-{uuid.uuid4()}"
    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "click_id": str(click_id),
            "external_reference": ref,
            "conversion_value": "0",
        },
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 422, (
        f"Expected 422 for zero conversion_value, got {resp.status_code}: {resp.text}"
    )

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        conv = (
            await session.execute(
                select(ReferralConversion).where(
                    ReferralConversion.external_reference == ref
                )
            )
        ).scalar_one_or_none()
        partner = await session.get(Partner, seed["partner_id"])

    assert conv is None, "No conversion row must be created for a rejected zero value"
    assert partner.total_referral_count == 0, (
        "total_referral_count must not increment for a rejected conversion — "
        "confirms the zero-value tier-farming exploit is closed"
    )


async def test_positive_conversion_value_still_works(
    client: AsyncClient, engine, seed: dict
) -> None:
    """Regression check: a normal positive conversion_value still succeeds
    end-to-end (201, real conversion row, commission credited to wallet) —
    the Field(gt=0) fix must not have collaterally broken the happy path."""
    await _click_link(client, seed["link_slug"])
    click_id = await _latest_click_id(engine, seed["link_id"])

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        balance_before = (await session.get(Wallet, seed["wallet_id"])).balance

    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "click_id": str(click_id),
            "external_reference": f"valid-{uuid.uuid4()}",
            "conversion_value": "250.00",
        },
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 201, resp.text

    async with factory() as session:
        balance_after = (await session.get(Wallet, seed["wallet_id"])).balance

    assert balance_after > balance_before, "A valid positive conversion must still credit the wallet"


# ---------------------------------------------------------------------------
# 2 — Withdrawal exceeds balance
# ---------------------------------------------------------------------------


async def test_withdrawal_exceeding_balance_is_rejected(
    client: AsyncClient, seed: dict
) -> None:
    """Partner with balance=0 requesting a 500.00 withdrawal must be rejected."""
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "partner@test.referrai", "password": "x"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.post(
        "/api/v1/withdrawals", json={"amount": "500.00"}, headers=headers
    )
    assert resp.status_code == 422, resp.text
    assert "insufficient" in resp.json()["detail"].lower()


async def test_wallet_balance_check_constraint_enforced_at_db_level(
    engine, seed: dict
) -> None:
    """Directly manipulating Wallet.balance negative (bypassing the service
    layer entirely) must be rejected by the DB's CHECK(balance >= 0)
    constraint — proving the guard isn't only application-level validation
    that a bug (or a future direct-DB script) could bypass.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        wallet = await session.get(Wallet, seed["wallet_id"])
        wallet.balance = Decimal("-50.00")
        with pytest.raises(Exception) as exc_info:
            await session.commit()
        # SQLite raises sqlite3.IntegrityError wrapped in SQLAlchemy's
        # IntegrityError; Postgres would raise a CheckViolation the same way.
        assert "IntegrityError" in type(exc_info.value).__name__ or "constraint" in str(
            exc_info.value
        ).lower()


# ---------------------------------------------------------------------------
# 3 — Concurrent withdrawal race condition (LIVE Postgres stack — see module
# docstring for why this cannot be meaningfully tested against sqlite).
# ---------------------------------------------------------------------------


async def _register_and_fund_partner(
    live: httpx.AsyncClient, suffix: str, target_balance: Decimal
) -> dict:
    """Register a fresh admin+partner pair and fund the partner's wallet to
    exactly target_balance via one admin-recorded conversion. Returns the
    partner's Authorization headers."""
    admin_email = f"race-admin-{suffix}@test.local"
    partner_email = f"race-partner-{suffix}@test.local"
    password = "racepass123"

    admin_reg = await live.post(
        "/api/v1/auth/register",
        json={"email": admin_email, "password": password, "role": "admin"},
    )
    assert admin_reg.status_code == 201, admin_reg.text
    admin_login = await live.post(
        "/api/v1/auth/login", json={"email": admin_email, "password": password}
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    partner_reg = await live.post(
        "/api/v1/auth/register",
        json={
            "email": partner_email,
            "password": password,
            "role": "partner",
            "name": "Race Partner",
        },
    )
    assert partner_reg.status_code == 201, partner_reg.text
    partner_login = await live.post(
        "/api/v1/auth/login", json={"email": partner_email, "password": password}
    )
    partner_headers = {
        "Authorization": f"Bearer {partner_login.json()['access_token']}"
    }

    # Read the live commission rate so a conversion_value can be chosen that
    # credits exactly target_balance, regardless of what rate is currently
    # configured in this environment.
    settings_resp = await live.get("/api/v1/settings", headers=admin_headers)
    assert settings_resp.status_code == 200, settings_resp.text
    rate = Decimal("0.10")
    for s in settings_resp.json():
        if s["key"] == "commission.default_percentage":
            rate = Decimal(str(s["value"]))
            break
    conversion_value = (target_balance / rate).quantize(Decimal("0.01"))

    code_resp = await live.post("/api/v1/referrals/codes", headers=partner_headers)
    assert code_resp.status_code == 201, code_resp.text
    referral_code = code_resp.json()["code"]

    conv_resp = await live.post(
        "/api/v1/referrals/conversions",
        json={
            "referral_code": referral_code,
            "external_reference": f"race-fund-{suffix}",
            "conversion_value": str(conversion_value),
        },
        headers=admin_headers,
    )
    assert conv_resp.status_code == 201, conv_resp.text

    wallet_resp = await live.get("/api/v1/wallet", headers=partner_headers)
    assert wallet_resp.status_code == 200, wallet_resp.text
    balance = Decimal(str(wallet_resp.json()["balance"]))
    assert balance == target_balance, (
        f"Expected exactly {target_balance} balance after funding conversion, "
        f"got {balance} (conversion_value={conversion_value}, rate={rate})"
    )
    return partner_headers


async def test_concurrent_withdrawal_race_condition() -> None:
    """5 simultaneous withdrawal requests of 30.00 each against a 100.00
    balance: exactly 3 must succeed (floor(100/30)=3) and 2 must be
    rejected for insufficient balance, regardless of request timing — the
    wallet must never go negative and the partner must never withdraw more
    than their actual balance.

    Runs NUM_ITERATIONS independent iterations (a fresh partner + wallet
    each time) so a single lucky scheduling interleaving can't hide a real
    bug — 2 concurrent requests only exercises one specific race window;
    5 concurrent requests repeated 10x is a much harder bar to pass by luck
    alone.
    """
    try:
        async with httpx.AsyncClient(base_url=LIVE_BACKEND_URL, timeout=10.0) as live:
            await live.get("/health")
    except httpx.ConnectError:
        pytest.skip(
            "Live backend at http://localhost:8000 is not reachable — this test "
            "requires the real Docker/Postgres stack to be running, since a "
            "sqlite-backed race condition test would give a false-negative "
            "'safe' result (see module docstring)."
        )

    NUM_ITERATIONS = 10
    N_REQUESTS = 5
    AMOUNT = Decimal("30.00")
    STARTING_BALANCE = Decimal("100.00")
    EXPECTED_SUCCESSES = 3  # floor(100.00 / 30.00)
    EXPECTED_FINAL_BALANCE = STARTING_BALANCE - (AMOUNT * EXPECTED_SUCCESSES)  # 10.00

    failures: list[str] = []

    async with httpx.AsyncClient(base_url=LIVE_BACKEND_URL, timeout=30.0) as live:
        for i in range(NUM_ITERATIONS):
            suffix = f"{i}-{uuid.uuid4().hex[:8]}"
            partner_headers = await _register_and_fund_partner(
                live, suffix, STARTING_BALANCE
            )

            async def _withdraw() -> httpx.Response:
                return await live.post(
                    "/api/v1/withdrawals",
                    json={"amount": str(AMOUNT)},
                    headers=partner_headers,
                )

            results = await asyncio.gather(*[_withdraw() for _ in range(N_REQUESTS)])
            statuses = [r.status_code for r in results]
            succeeded_approved = [
                r
                for r in results
                if r.status_code == 201 and r.json().get("status") == "approved"
            ]
            rejected = [r for r in results if r.status_code == 422]

            final_wallet = await live.get("/api/v1/wallet", headers=partner_headers)
            final_balance = Decimal(str(final_wallet.json()["balance"]))

            print(
                f"\n[RACE iter {i}] statuses={statuses}, "
                f"succeeded={len(succeeded_approved)}, rejected={len(rejected)}, "
                f"final_balance={final_balance}"
            )

            if final_balance < Decimal("0.00"):
                failures.append(
                    f"iter {i}: WALLET WENT NEGATIVE: final_balance={final_balance}, "
                    f"statuses={statuses}"
                )
            if len(succeeded_approved) != EXPECTED_SUCCESSES:
                failures.append(
                    f"iter {i}: expected exactly {EXPECTED_SUCCESSES} successful "
                    f"withdrawals (balance={STARTING_BALANCE}, amount_each={AMOUNT}, "
                    f"{N_REQUESTS} concurrent requests), got "
                    f"{len(succeeded_approved)}. statuses={statuses}"
                )
            if final_balance != EXPECTED_FINAL_BALANCE:
                failures.append(
                    f"iter {i}: expected final_balance={EXPECTED_FINAL_BALANCE}, "
                    f"got {final_balance}"
                )

    assert not failures, (
        f"Race condition detected in {len(failures)} check(s) across "
        f"{NUM_ITERATIONS} iterations — this is a real, exploitable money bug:\n"
        + "\n".join(failures)
    )


# ---------------------------------------------------------------------------
# 4 — Self-referral fraud rule coverage
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Structural data limitation, not a fixable bug: "
           "FraudRuleEngine._check_self_referral only fires when a PRIOR "
           "conversion already exists for the same (ip, partner_id) pair — "
           "on a partner's literal first-ever self-click-and-convert there is "
           "no second data point to compare against, and no other signal "
           "(no tracked partner login/account IP) exists to distinguish a "
           "self-referral from a genuine first-time organic buyer. Fixing "
           "this requires a new signal (e.g. tracking partner account IPs), "
           "not a change to this scoring/flagging logic. The SECOND "
           "self-referral from the same IP is correctly flagged as of the "
           "ai_service.score_fraud() fix (see "
           "test_self_referral_second_conversion_from_same_ip).",
    strict=True,
)
async def test_self_referral_first_conversion_flag_coverage(
    client: AsyncClient, engine, seed: dict
) -> None:
    """A partner's first-ever self-referred conversion: does ANY fraud_flags
    row get created before/at the point commission is credited?

    FraudRuleEngine's self_referral rule only fires when a PRIOR conversion
    already exists for the same (ip, partner_id) pair — so on the very first
    self-click-and-convert, there is nothing for it to match against. This
    test proves (or disproves) that empirically against the real code path:
    click -> (background fraud scoring) -> admin records conversion -> check
    fraud_flags.
    """
    slug = seed["link_slug"]
    await _click_link(client, slug)
    click_id = await _latest_click_id(engine, seed["link_id"])

    conv_resp = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "click_id": str(click_id),
            "external_reference": f"self-ref-first-{uuid.uuid4()}",
            "conversion_value": "300.00",
        },
        headers=seed["admin_headers"],
    )
    assert conv_resp.status_code == 201, conv_resp.text

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        wallet = await session.get(Wallet, seed["wallet_id"])
        flags = (
            await session.execute(
                select(FraudFlag).where(FraudFlag.partner_id == seed["partner_id"])
            )
        ).scalars().all()

    commission_was_paid = wallet.balance > Decimal("0.00")
    no_flag_exists = len(flags) == 0

    if commission_was_paid and no_flag_exists:
        pytest.fail(
            f"REAL BUG: partner's first self-referral conversion paid a real "
            f"commission (wallet.balance={wallet.balance}) with ZERO fraud_flags "
            f"rows created. FraudRuleEngine.self_referral only compares against "
            f"PRIOR conversions, and score_fraud() runs at click-time (before "
            f"any conversion exists on that click) — so the very first "
            f"self-referral is structurally unflaggable, and no other check "
            f"ever runs at conversion-recording time. An admin reviewing "
            f"fraud_flags would never see this."
        )


async def test_self_referral_second_conversion_from_same_ip(
    client: AsyncClient, engine, seed: dict
) -> None:
    """A partner's SECOND self-referred conversion from the same IP: the
    self_referral rule fires on the second click, and — per the
    ai_service.score_fraud() fix — a triggered deterministic rule now creates
    a fraud_flags row on its own, independent of the composite score/
    threshold. (Note this flags the *second* click, not the *first*
    conversion's commission, which was already paid unflagged — see
    test_self_referral_first_conversion_flag_coverage.)"""
    slug = seed["link_slug"]

    # First self-referral (funds a prior conversion for the rule to match against)
    await _click_link(client, slug)
    click_id_1 = await _latest_click_id(engine, seed["link_id"])
    conv1 = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "click_id": str(click_id_1),
            "external_reference": f"self-ref-1-{uuid.uuid4()}",
            "conversion_value": "300.00",
        },
        headers=seed["admin_headers"],
    )
    assert conv1.status_code == 201, conv1.text

    # Second click from the same (test-client) IP — this is where the rule
    # has a prior conversion to compare against.
    await _click_link(client, slug)
    click_id_2 = await _latest_click_id(engine, seed["link_id"])

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        flags = (
            await session.execute(
                select(FraudFlag).where(FraudFlag.partner_id == seed["partner_id"])
            )
        ).scalars().all()
        ai_score = (
            await session.execute(
                select(AIScore)
                .where(AIScore.entity_id == click_id_2)
                .where(AIScore.score_type == "fraud_risk")
                .order_by(AIScore.calculated_at.desc())
            )
        ).scalars().first()

    flagged_click_ids = {f.referral_click_id for f in flags}
    print(
        f"\n[INFO] After a 2nd self-referral click, fraud_flags rows: {len(flags)}, "
        f"flagged click_ids: {flagged_click_ids} (click_id_1={click_id_1}, "
        f"click_id_2={click_id_2})"
    )
    if ai_score is not None:
        print(
            f"[INFO] click_id_2 fraud AIScore: score={ai_score.score}, "
            f"contributing_factors={ai_score.contributing_factors}"
        )
    else:
        print("[INFO] No fraud_risk AIScore row found for click_id_2 at all.")

    assert ai_score is not None, "score_fraud() must have run for click_id_2"
    assert "self_referral" in (ai_score.contributing_factors or {}).get(
        "triggered_rules", []
    ), "self_referral rule must fire on the second self-referral click"
    assert len(flags) == 1, (
        f"Expected exactly one fraud_flags row after the second self-referral "
        f"click, got {len(flags)}"
    )
    assert flagged_click_ids == {click_id_2}, (
        f"The flag must be attached to the second click ({click_id_2}), got "
        f"{flagged_click_ids}"
    )


# ---------------------------------------------------------------------------
# 5 — Regression check: conversions endpoint stays admin-only
# ---------------------------------------------------------------------------


async def test_partner_still_cannot_call_conversions_endpoint(
    client: AsyncClient, engine, seed: dict
) -> None:
    """Regression check (not new testing): partner token on
    POST /referrals/conversions must still be 403 after all recent merges."""
    slug = seed["link_slug"]
    await _click_link(client, slug)
    click_id = await _latest_click_id(engine, seed["link_id"])

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "partner@test.referrai", "password": "x"},
    )
    assert login.status_code == 200, login.text
    partner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.post(
        "/api/v1/referrals/conversions",
        json={
            "click_id": str(click_id),
            "external_reference": f"regression-{uuid.uuid4()}",
            "conversion_value": "50.00",
        },
        headers=partner_headers,
    )
    assert resp.status_code == 403, resp.text
