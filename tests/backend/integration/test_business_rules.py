# -----------------------------------------------------------------------------
# tests/backend/integration/test_business_rules.py
#
# Regression tests for the business-logic fixes: auth hardening, wallet
# locking and fund holds, withdrawal lifecycle, attribution, idempotency,
# settings validation + audit, synthetic-data exclusion, AI-score RBAC,
# commission endpoints and suspended-partner rules. Runs on PostgreSQL so row
# locks and constraints are real.
# Change: code-ownership test replaced by partner-derivation tests; conversions post referral_code instead of partner_id.
# -----------------------------------------------------------------------------

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.security import create_password_reset_token, password_fingerprint
from app.models.ai_score import AIScore
from app.models.audit_log import AuditLog
from app.models.fraud_flag import FraudFlag
from app.models.partner import Partner
from app.models.referral import ReferralClick, ReferralCode, ReferralConversion
from app.models.setting import Setting
from app.models.user import User
from app.models.wallet import Transaction, Wallet, Withdrawal

API = "/api/v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _set_balance(session_factory, partner_id, amount: str) -> None:
    async with session_factory() as s:
        await s.execute(
            update(Wallet).where(Wallet.partner_id == partner_id).values(balance=Decimal(amount), total_earned=Decimal(amount))
        )
        await s.commit()


async def _wallet(session_factory, partner_id) -> Wallet:
    async with session_factory() as s:
        return (await s.execute(select(Wallet).where(Wallet.partner_id == partner_id))).scalar_one()


async def _add_click(session_factory, partner_id, link_id, clicked_at, *, synthetic=False) -> uuid.UUID:
    cid = uuid.uuid4()
    async with session_factory() as s:
        s.add(
            ReferralClick(
                id=cid,
                referral_link_id=link_id,
                partner_id=partner_id,
                ip_address="203.0.113.7",
                device_info={"user_agent": "pytest", "device_type": "desktop"},
                clicked_at=clicked_at,
                is_synthetic=synthetic,
            )
        )
        await s.commit()
    return cid


async def _convert(client, seed, ref, value="100.00", **extra):
    return await client.post(
        f"{API}/referrals/conversions",
        json={"referral_code": seed["referral_code"], "external_reference": ref, "conversion_value": value, **extra},
        headers=seed["admin_headers"],
    )


async def _set_setting(session_factory, key, value) -> None:
    async with session_factory() as s:
        await s.execute(update(Setting).where(Setting.key == key).values(value=value))
        await s.commit()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
async def test_public_registration_cannot_create_admin(client: AsyncClient, engine) -> None:
    resp = await client.post(
        f"{API}/auth/register",
        json={"email": "evil@x.io", "password": "password123", "role": "admin", "name": "Evil"},
    )
    assert resp.status_code == 422


async def test_registration_creates_partner_on_base_tier(client: AsyncClient, session_factory) -> None:
    resp = await client.post(
        f"{API}/auth/register", json={"email": "New@X.io", "password": "password123", "name": "New Partner"}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "partner"
    async with session_factory() as s:
        partner = (await s.execute(select(Partner).where(Partner.email == "new@x.io"))).scalar_one()
        assert partner.tier_id is not None


async def test_reset_token_is_not_an_access_token_and_is_single_use(
    client: AsyncClient, seed: dict, session_factory
) -> None:
    async with session_factory() as s:
        user = await s.get(User, seed["partner_user_id"])
        token = create_password_reset_token(str(user.id), password_fingerprint(user.password_hash))

    resp = await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401

    first = await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "brand-new-pass"})
    assert first.status_code == 200
    again = await client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "another-pass1"})
    assert again.status_code == 400


# ---------------------------------------------------------------------------
# Wallet / withdrawals
# ---------------------------------------------------------------------------
async def test_concurrent_withdrawals_cannot_overdraw(client: AsyncClient, seed: dict, session_factory) -> None:
    await _set_balance(session_factory, seed["partner_id"], "100.00")
    r1, r2 = await asyncio.gather(
        client.post(f"{API}/withdrawals", json={"amount": "60.00"}, headers=seed["partner_headers"]),
        client.post(f"{API}/withdrawals", json={"amount": "60.00"}, headers=seed["partner_headers"]),
    )
    assert sorted([r1.status_code, r2.status_code]) == [201, 422]
    wallet = await _wallet(session_factory, seed["partner_id"])
    assert wallet.balance == Decimal("40.00")


async def test_pending_withdrawal_holds_funds_and_rejection_refunds(
    client: AsyncClient, seed: dict, session_factory
) -> None:
    await _set_balance(session_factory, seed["partner_id"], "500.00")
    resp = await client.post(f"{API}/withdrawals", json={"amount": "200.00"}, headers=seed["partner_headers"])
    assert resp.status_code == 201
    w = resp.json()
    assert w["status"] == "pending" and w["requires_manual_review"] is True

    wallet = (await client.get(f"{API}/wallet", headers=seed["partner_headers"])).json()
    assert Decimal(wallet["balance"]) == Decimal("300.00")
    assert Decimal(wallet["pending_withdrawals"]) == Decimal("200.00")

    # Cannot request more than what is left after the hold.
    over = await client.post(f"{API}/withdrawals", json={"amount": "350.00"}, headers=seed["partner_headers"])
    assert over.status_code == 422

    rej = await client.patch(
        f"{API}/withdrawals/{w['id']}", json={"status": "rejected", "notes": "no"}, headers=seed["admin_headers"]
    )
    assert rej.status_code == 200
    wallet = await _wallet(session_factory, seed["partner_id"])
    assert wallet.balance == Decimal("500.00")
    assert wallet.total_withdrawn == Decimal("0.00")
    async with session_factory() as s:
        types = (
            await s.execute(select(Transaction.reference_type, Transaction.amount).where(Transaction.reference_id == uuid.UUID(w["id"])))
        ).all()
        assert sorted(t for t, _ in types) == ["withdrawal", "withdrawal_reversal"]
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "withdrawal.rejected"))).scalar_one()
        assert audit.user_id == seed["admin_id"]


async def test_approve_then_mark_paid(client: AsyncClient, seed: dict, session_factory) -> None:
    await _set_balance(session_factory, seed["partner_id"], "500.00")
    w = (await client.post(f"{API}/withdrawals", json={"amount": "250.00"}, headers=seed["partner_headers"])).json()

    ok = await client.patch(f"{API}/withdrawals/{w['id']}", json={"status": "approved"}, headers=seed["admin_headers"])
    assert ok.status_code == 200
    wallet = await _wallet(session_factory, seed["partner_id"])
    assert wallet.balance == Decimal("250.00") and wallet.total_withdrawn == Decimal("250.00")

    paid = await client.post(f"{API}/withdrawals/{w['id']}/paid", headers=seed["admin_headers"])
    assert paid.status_code == 200 and paid.json()["status"] == "paid"
    again = await client.post(f"{API}/withdrawals/{w['id']}/paid", headers=seed["admin_headers"])
    assert again.status_code == 409

    queue = (await client.get(f"{API}/withdrawals", headers=seed["admin_headers"])).json()
    assert queue[0]["partner_name"] == "Test Partner"
    mine = (await client.get(f"{API}/me/withdrawals", headers=seed["partner_headers"])).json()
    assert [m["status"] for m in mine] == ["paid"]


async def test_concurrent_approvals_only_one_wins(client: AsyncClient, seed: dict, session_factory) -> None:
    await _set_balance(session_factory, seed["partner_id"], "500.00")
    w = (await client.post(f"{API}/withdrawals", json={"amount": "300.00"}, headers=seed["partner_headers"])).json()
    r1, r2 = await asyncio.gather(
        client.patch(f"{API}/withdrawals/{w['id']}", json={"status": "approved"}, headers=seed["admin_headers"]),
        client.patch(f"{API}/withdrawals/{w['id']}", json={"status": "rejected"}, headers=seed["admin_headers"]),
    )
    assert sorted([r1.status_code, r2.status_code]) == [200, 409]
    wallet = await _wallet(session_factory, seed["partner_id"])
    assert wallet.balance + wallet.total_withdrawn in (Decimal("500.00"),)


async def test_auto_approval_has_rolling_24h_cap(client: AsyncClient, seed: dict, session_factory) -> None:
    await _set_balance(session_factory, seed["partner_id"], "500.00")
    first = (await client.post(f"{API}/withdrawals", json={"amount": "60.00"}, headers=seed["partner_headers"])).json()
    second = (await client.post(f"{API}/withdrawals", json={"amount": "60.00"}, headers=seed["partner_headers"])).json()
    assert first["status"] == "approved"
    assert second["status"] == "pending", "Splitting into small requests must not bypass the threshold"
    async with session_factory() as s:
        assert (
            await s.execute(select(AuditLog).where(AuditLog.action == "withdrawal.auto_approved"))
        ).scalar_one().user_id is None


async def test_threshold_is_exclusive(client: AsyncClient, seed: dict, session_factory) -> None:
    await _set_balance(session_factory, seed["partner_id"], "500.00")
    w = (await client.post(f"{API}/withdrawals", json={"amount": "100.00"}, headers=seed["partner_headers"])).json()
    assert w["status"] == "pending"


async def test_multiple_pending_fraud_flags_block_auto_approval(client: AsyncClient, seed: dict, session_factory) -> None:
    await _set_balance(session_factory, seed["partner_id"], "500.00")
    async with session_factory() as s:
        for _ in range(2):
            score = AIScore(
                id=uuid.uuid4(), entity_type="partner", entity_id=seed["partner_id"],
                score_type="fraud_risk", score=Decimal("90"), status="ok", is_synthetic=False,
            )
            s.add(score)
            await s.flush()
            s.add(FraudFlag(id=uuid.uuid4(), partner_id=seed["partner_id"], ai_score_id=score.id, status="pending_review"))
        await s.commit()
    resp = await client.post(f"{API}/withdrawals", json={"amount": "20.00"}, headers=seed["partner_headers"])
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending"


async def test_withdrawal_amount_must_have_two_decimals(client: AsyncClient, seed: dict, session_factory) -> None:
    await _set_balance(session_factory, seed["partner_id"], "500.00")
    resp = await client.post(f"{API}/withdrawals", json={"amount": "15.005"}, headers=seed["partner_headers"])
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Attribution / conversions
# ---------------------------------------------------------------------------
async def test_last_and_first_click_attribution_over_link_clicks(client: AsyncClient, seed: dict, session_factory) -> None:
    old = await _add_click(session_factory, seed["partner_id"], seed["link_id"], _now() - timedelta(days=3))
    new = await _add_click(session_factory, seed["partner_id"], seed["link_id"], _now() - timedelta(hours=1))
    await _add_click(session_factory, seed["partner_id"], seed["link_id"], _now() - timedelta(days=60))  # outside window
    await _add_click(session_factory, seed["partner_id"], seed["link_id"], _now(), synthetic=True)  # synthetic

    r1 = await _convert(client, seed, "order-1")
    assert r1.status_code == 201
    assert r1.json()["click_id"] == str(new)
    assert r1.json()["attribution_model"] == "last_click"

    await _set_setting(session_factory, "referral.attribution_model", "first_click")
    r2 = await _convert(client, seed, "order-2")
    assert r2.json()["click_id"] == str(old)
    assert r2.json()["attribution_model"] == "first_click"

    # Both eligible clicks are now used; the next conversion has no click.
    r3 = await _convert(client, seed, "order-3")
    assert r3.status_code == 201 and r3.json()["click_id"] is None


async def test_partner_is_derived_from_the_referral_code_not_the_caller(client: AsyncClient, seed: dict, session_factory, partner_factory) -> None:
    # Week-11 hardening: the partner comes from the code/click, so a caller-supplied
    # (or mismatched) partner_id can never credit someone else's wallet.
    async with session_factory() as s:
        other = await partner_factory(s, email="other@x.io", tier_id=seed["bronze_tier_id"])
        s.add(ReferralCode(id=uuid.uuid4(), partner_id=other["partner_id"], code="OTHER123", is_active=True))
        await s.commit()
    resp = await _convert(client, seed, "order-x", referral_code="OTHER123", partner_id=str(seed["partner_id"]))
    assert resp.status_code == 201
    assert resp.json()["partner_id"] == str(other["partner_id"])

    assert (await _convert(client, seed, "order-y", referral_code="NOPE0000")).status_code == 404


async def test_conversion_without_click_or_code_is_rejected(client: AsyncClient, seed: dict) -> None:
    resp = await client.post(
        f"{API}/referrals/conversions",
        json={"partner_id": str(seed["partner_id"]), "external_reference": "bare", "conversion_value": "10.00"},
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 422


async def test_duplicate_conversions_are_idempotent_under_concurrency(client: AsyncClient, seed: dict, session_factory) -> None:
    r1, r2 = await asyncio.gather(_convert(client, seed, "dup-1"), _convert(client, seed, "dup-1"))
    assert sorted([r1.status_code, r2.status_code]) == [201, 409]
    wallet = await _wallet(session_factory, seed["partner_id"])
    assert wallet.balance == Decimal("10.00")


async def test_commission_ledger_row_references_commission(client: AsyncClient, seed: dict, session_factory) -> None:
    resp = await _convert(client, seed, "ledger-1", value="99.95")
    assert resp.status_code == 201
    async with session_factory() as s:
        tx = (await s.execute(select(Transaction).where(Transaction.reference_type == "commission"))).scalar_one()
        conv_id = uuid.UUID(resp.json()["id"])
        from app.models.commission import Commission

        commission = (await s.execute(select(Commission).where(Commission.conversion_id == conv_id))).scalar_one()
        assert tx.reference_id == commission.id
        assert commission.amount == Decimal("10.00")  # 9.995 rounds half-up


async def test_invalid_conversion_value_rejected(client: AsyncClient, seed: dict) -> None:
    assert (await _convert(client, seed, "neg", value="-5")).status_code == 422
    assert (await _convert(client, seed, "zero", value="0")).status_code == 422


# ---------------------------------------------------------------------------
# Suspended partners
# ---------------------------------------------------------------------------
async def test_suspended_partner_cannot_earn_or_withdraw(client: AsyncClient, seed: dict, session_factory) -> None:
    await _set_balance(session_factory, seed["partner_id"], "50.00")
    patch = await client.patch(
        f"{API}/partners/{seed['partner_id']}", json={"status": "suspended"}, headers=seed["admin_headers"]
    )
    assert patch.status_code == 200
    assert (await client.post(f"{API}/referrals/links", json={"destination_url": "https://a.b"}, headers=seed["partner_headers"])).status_code == 403
    assert (await client.post(f"{API}/withdrawals", json={"amount": "20.00"}, headers=seed["partner_headers"])).status_code == 403
    assert (await _convert(client, seed, "susp-1")).status_code == 409

    # The visitor is still redirected, but no click is recorded.
    r = await client.get(f"/r/{seed['link_slug']}", follow_redirects=False)
    assert r.status_code == 302
    async with session_factory() as s:
        assert (await s.execute(select(ReferralClick))).first() is None
        audit = (await s.execute(select(AuditLog).where(AuditLog.action == "partner.status_changed"))).scalar_one()
        assert audit.new_value == {"status": "suspended"}


async def test_destination_url_must_be_http(client: AsyncClient, seed: dict) -> None:
    resp = await client.post(
        f"{API}/referrals/links", json={"destination_url": "javascript:alert(1)"}, headers=seed["partner_headers"]
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
async def test_settings_are_validated_and_audited(client: AsyncClient, seed: dict, session_factory) -> None:
    h = seed["admin_headers"]
    assert (await client.put(f"{API}/settings/commission.default_percentage", json={"value": 10}, headers=h)).status_code == 422
    assert (await client.put(f"{API}/settings/referral.attribution_model", json={"value": "middle"}, headers=h)).status_code == 422
    assert (await client.put(f"{API}/settings/ranking.weights", json={"value": {"quality": 1}}, headers=h)).status_code == 422

    ok = await client.put(f"{API}/settings/commission.default_percentage", json={"value": 0.12}, headers=h)
    assert ok.status_code == 200 and ok.json()["value"] == 0.12
    async with session_factory() as s:
        log = (await s.execute(select(AuditLog).where(AuditLog.action == "settings.updated"))).scalar_one()
        assert log.old_value == {"key": "commission.default_percentage", "value": 0.1}
        assert log.ip_address is not None

    schema = (await client.get(f"{API}/settings/schema", headers=h)).json()
    assert {d["key"] for d in schema} >= {"wallet.auto_approval_threshold", "referral.attribution_model"}


# ---------------------------------------------------------------------------
# Synthetic exclusion + dashboards
# ---------------------------------------------------------------------------
async def test_synthetic_partners_excluded_from_admin_views(client: AsyncClient, seed: dict, session_factory, partner_factory) -> None:
    async with session_factory() as s:
        await partner_factory(s, email="synthetic@x.io", is_synthetic=True)
        await s.commit()
    partners = (await client.get(f"{API}/partners", headers=seed["admin_headers"])).json()
    assert [p["email"] for p in partners] == ["partner@test.referrai"]
    assert partners[0]["tier_name"] == "Bronze"

    await _add_click(session_factory, seed["partner_id"], seed["link_id"], _now() - timedelta(hours=2))
    await _convert(client, seed, "dash-1", value="200.00")
    dash = (await client.get(f"{API}/dashboard/admin?days=7", headers=seed["admin_headers"])).json()
    assert dash["kpis"]["active_partners"] == 1
    assert Decimal(dash["kpis"]["total_revenue"]) == Decimal("200.00")
    assert Decimal(dash["kpis"]["total_commission"]) == Decimal("20.00")
    assert dash["kpis"]["conversion_rate"] == 1.0
    assert len(dash["volume_chart"]) == 7
    assert dash["top_partners"][0]["name"] == "Test Partner"

    pdash = (await client.get(f"{API}/dashboard/partner", headers=seed["partner_headers"])).json()
    assert pdash["kpis"]["conversion_count"] == 1
    assert pdash["kpis"]["click_count"] == 1
    assert pdash["tier"]["current_tier"] == "Bronze"


async def test_partner_quality_score_is_average_of_conversion_scores(client: AsyncClient, seed: dict, session_factory) -> None:
    ids = []
    for i, value in enumerate(("100.00", "50.00")):
        ids.append(uuid.UUID((await _convert(client, seed, f"q-{i}", value=value)).json()["id"]))
    async with session_factory() as s:
        for cid, sc in zip(ids, (80, 60)):
            s.add(AIScore(id=uuid.uuid4(), entity_type="referral", entity_id=cid, score_type="quality",
                          score=Decimal(sc), status="ok", is_synthetic=False))
        await s.commit()
    pdash = (await client.get(f"{API}/dashboard/partner", headers=seed["partner_headers"])).json()
    assert float(pdash["quality_score"]) == 70.0
    partners = (await client.get(f"{API}/partners", headers=seed["admin_headers"])).json()
    assert partners[0]["quality_score"] == 70.0


# ---------------------------------------------------------------------------
# AI score RBAC
# ---------------------------------------------------------------------------
async def test_partners_only_read_their_own_non_fraud_scores(client: AsyncClient, seed: dict, session_factory, partner_factory) -> None:
    async with session_factory() as s:
        other = await partner_factory(s, email="other2@x.io")
        for pid, st in ((seed["partner_id"], "churn_risk"), (seed["partner_id"], "fraud_risk"), (other["partner_id"], "churn_risk")):
            s.add(AIScore(id=uuid.uuid4(), entity_type="partner", entity_id=pid, score_type=st,
                          score=Decimal("42"), status="ok", is_synthetic=False))
        await s.commit()
    ph = seed["partner_headers"]
    assert (await client.get(f"{API}/ai-scores/{seed['partner_id']}?score_type=churn_risk", headers=ph)).status_code == 200
    assert (await client.get(f"{API}/ai-scores/{seed['partner_id']}?score_type=fraud_risk", headers=ph)).status_code == 403
    assert (await client.get(f"{API}/ai-scores/{other['partner_id']}?score_type=churn_risk", headers=ph)).status_code == 403
    assert (await client.get(f"{API}/ai-scores/{other['partner_id']}?score_type=churn_risk", headers=seed["admin_headers"])).status_code == 200


# ---------------------------------------------------------------------------
# Commission endpoints
# ---------------------------------------------------------------------------
async def test_commission_listing_and_reversal(client: AsyncClient, seed: dict, session_factory) -> None:
    await _convert(client, seed, "c-1", value="300.00")
    page = (await client.get(f"{API}/me/commissions", headers=seed["partner_headers"])).json()
    assert page["total"] == 1
    item = page["items"][0]
    assert Decimal(item["amount"]) == Decimal("30.00") and item["external_reference"] == "c-1"

    admin_page = (await client.get(f"{API}/commissions", headers=seed["admin_headers"])).json()
    assert admin_page["items"][0]["partner_name"] == "Test Partner"
    assert (await client.get(f"{API}/commissions", headers=seed["partner_headers"])).status_code == 403

    rev = await client.post(f"{API}/commissions/{item['id']}/reverse", json={"reason": "fraud"}, headers=seed["admin_headers"])
    assert rev.status_code == 200 and rev.json()["status"] == "reversed"
    wallet = await _wallet(session_factory, seed["partner_id"])
    assert wallet.balance == Decimal("0.00") and wallet.total_earned == Decimal("0.00")
    assert (await client.post(f"{API}/commissions/{item['id']}/reverse", headers=seed["admin_headers"])).status_code == 409
