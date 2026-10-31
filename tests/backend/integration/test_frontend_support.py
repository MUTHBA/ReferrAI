# -----------------------------------------------------------------------------
# tests/backend/integration/test_frontend_support.py
#
# Endpoints added for the redesigned dashboards: enriched conversion rows,
# link/code usage counts, admin partner detail (dashboard + conversions),
# transaction labels, withdrawal context for payouts, commission search,
# partner score lists (churn/ranking), the audit log, and change-password.
# Change: conversions post referral_code instead of partner_id (partner is derived server-side).
# -----------------------------------------------------------------------------

from datetime import datetime, timezone
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import update

from app.models.referral import ReferralClick
from app.models.wallet import Wallet

API = "/api/v1"


async def _click_and_convert(client: AsyncClient, seed: dict, ref: str, value: str = "200.00") -> dict:
    # One real tracked click through the public redirect, then a conversion.
    r = await client.get(f"/r/{seed['link_slug']}?utm_source=newsletter", headers={"User-Agent": "Mozilla/5.0 (iPhone)"})
    assert r.status_code in (302, 307)
    resp = await client.post(
        f"{API}/referrals/conversions",
        json={"referral_code": seed["referral_code"], "external_reference": ref, "conversion_value": value},
        headers=seed["admin_headers"],
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_conversion_rows_include_commission_and_click(client: AsyncClient, seed: dict) -> None:
    await _click_and_convert(client, seed, "fe-1")
    rows = (await client.get(f"{API}/referrals/conversions", headers=seed["partner_headers"])).json()
    assert len(rows) == 1
    row = rows[0]
    assert Decimal(row["commission_amount"]) == Decimal("20.00")
    assert row["commission_status"] == "approved"
    assert row["source"] == "newsletter"
    assert row["device_type"] == "mobile"
    assert row["clicked_at"] is not None and row["via_code"] is False

    # Same rows for the admin partner-detail page; partners can't use it.
    admin_rows = (
        await client.get(f"{API}/partners/{seed['partner_id']}/conversions", headers=seed["admin_headers"])
    ).json()
    assert [r["external_reference"] for r in admin_rows] == ["fe-1"]
    assert (
        await client.get(f"{API}/partners/{seed['partner_id']}/conversions", headers=seed["partner_headers"])
    ).status_code == 403


async def test_link_usage_counts(client: AsyncClient, seed: dict) -> None:
    await _click_and_convert(client, seed, "fe-2")
    links = (await client.get(f"{API}/referrals/links", headers=seed["partner_headers"])).json()
    assert links[0]["click_count"] == 1 and links[0]["conversion_count"] == 1


async def test_admin_partner_dashboard_and_transaction_labels(client: AsyncClient, seed: dict) -> None:
    await _click_and_convert(client, seed, "fe-3")
    dash = await client.get(f"{API}/partners/{seed['partner_id']}/dashboard", headers=seed["admin_headers"])
    assert dash.status_code == 200
    assert Decimal(dash.json()["kpis"]["wallet_balance"]) == Decimal("20.00")

    txs = (await client.get(f"{API}/wallet/transactions", headers=seed["partner_headers"])).json()
    assert txs[0]["description"] == "Commission for fe-3"


async def test_withdrawal_list_has_wallet_and_flag_context(client: AsyncClient, seed: dict, session_factory) -> None:
    async with session_factory() as s:
        await s.execute(update(Wallet).where(Wallet.partner_id == seed["partner_id"]).values(balance=Decimal("500.00")))
        await s.commit()
    assert (await client.post(f"{API}/withdrawals", json={"amount": "250.00"}, headers=seed["partner_headers"])).status_code == 201
    rows = (
        await client.get(f"{API}/withdrawals?partner_id={seed['partner_id']}", headers=seed["admin_headers"])
    ).json()
    assert len(rows) == 1
    assert Decimal(rows[0]["wallet_balance"]) == Decimal("250.00")  # funds are held at request time
    assert rows[0]["open_fraud_flag"] is False


async def test_commission_search(client: AsyncClient, seed: dict) -> None:
    await _click_and_convert(client, seed, "order-abc")
    await _click_and_convert(client, seed, "order-xyz")
    page = (await client.get(f"{API}/commissions?search=xyz", headers=seed["admin_headers"])).json()
    assert page["total"] == 1 and page["items"][0]["external_reference"] == "order-xyz"
    mine = (await client.get(f"{API}/me/commissions?search=abc", headers=seed["partner_headers"])).json()
    assert mine["total"] == 1


async def test_partner_score_rows(client: AsyncClient, seed: dict) -> None:
    rows = (await client.get(f"{API}/ai-scores?score_type=churn_risk", headers=seed["admin_headers"])).json()
    assert [r["name"] for r in rows] == ["Test Partner"]
    assert rows[0]["score"] is None and rows[0]["score_status"] is None
    assert (await client.get(f"{API}/ai-scores?score_type=churn_risk", headers=seed["partner_headers"])).status_code == 403


async def test_audit_log_listing(client: AsyncClient, seed: dict) -> None:
    resp = await client.put(f"{API}/settings/commission.default_percentage", json={"value": 0.12}, headers=seed["admin_headers"])
    assert resp.status_code == 200, resp.text
    await client.patch(f"{API}/partners/{seed['partner_id']}", json={"status": "suspended"}, headers=seed["admin_headers"])

    page = (await client.get(f"{API}/audit-logs", headers=seed["admin_headers"])).json()
    actions = [i["action"] for i in page["items"]]
    assert "settings.updated" in actions and "partner.status_changed" in actions
    assert page["stats"]["admin_24h"] >= 2
    suspended = next(i for i in page["items"] if i["action"] == "partner.status_changed")
    assert suspended["partner_name"] == "Test Partner"
    assert suspended["actor_email"] == "admin@test.referrai"

    filtered = (await client.get(f"{API}/audit-logs?search=Test%20Partner", headers=seed["admin_headers"])).json()
    assert {i["action"] for i in filtered["items"]} == {"partner.status_changed"}
    assert (await client.get(f"{API}/audit-logs?actor=system", headers=seed["admin_headers"])).json()["total"] == 0
    assert "settings.updated" in (await client.get(f"{API}/audit-logs/actions", headers=seed["admin_headers"])).json()
    assert (await client.get(f"{API}/audit-logs", headers=seed["partner_headers"])).status_code == 403


async def test_change_password(client: AsyncClient, seed: dict) -> None:
    # make_partner sets the password to "x".
    bad = await client.post(
        f"{API}/auth/change-password",
        json={"current_password": "wrong", "new_password": "new-password-1"},
        headers=seed["partner_headers"],
    )
    assert bad.status_code == 400
    short = await client.post(
        f"{API}/auth/change-password", json={"current_password": "x", "new_password": "short"}, headers=seed["partner_headers"]
    )
    assert short.status_code == 422
    ok = await client.post(
        f"{API}/auth/change-password",
        json={"current_password": "x", "new_password": "new-password-1"},
        headers=seed["partner_headers"],
    )
    assert ok.status_code == 200
    login = await client.post(f"{API}/auth/login", json={"email": "partner@test.referrai", "password": "new-password-1"})
    assert login.status_code == 200


async def test_commission_totals_and_wallet_limits(client: AsyncClient, seed: dict) -> None:
    await _click_and_convert(client, seed, "tot-1", value="100.00")
    await _click_and_convert(client, seed, "tot-2", value="50.00")
    page = (await client.get(f"{API}/me/commissions?status=reversed", headers=seed["partner_headers"])).json()
    assert page["total"] == 0  # status filter applies to rows...
    assert Decimal(page["totals"]["approved"]) == Decimal("15.00")  # ...but not to totals

    wallet = (await client.get(f"{API}/wallet", headers=seed["partner_headers"])).json()
    assert Decimal(wallet["min_withdrawal_amount"]) == Decimal("10")
    assert Decimal(wallet["auto_approval_threshold"]) == Decimal("100")
