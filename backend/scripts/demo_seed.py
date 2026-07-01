#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# backend/scripts/demo_seed.py
#
# DEMO-001 — Seeds a running local ReferrAI instance with realistic demo data
# so the full platform flow can be demonstrated end-to-end:
#
#   admin registration → partner registrations → referral links/codes →
#   simulated clicks → synthetic ML training data → real conversions →
#   churn scoring → wallet balances
#
# Prerequisites:
#   1. docker-compose up --build (or uvicorn app.main:app --reload)
#   2. alembic upgrade head
#   3. pip install httpx  (already in requirements.txt)
#
# Usage:
#   python backend/scripts/demo_seed.py
#   python backend/scripts/demo_seed.py --reset   # prints DB wipe instructions
# -----------------------------------------------------------------------------

import argparse
import sys
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8000"

ADMIN_EMAIL = "admin@referrai.com"
ADMIN_PASSWORD = "Admin123!"

PARTNER_PASSWORD = "Partner123!"
PARTNER_COUNT = 3

# Real conversion values spread between $50–$500 (one per slot, 5 total)
CONVERSION_VALUES = [150.00, 320.00, 75.50, 490.00, 200.00]

# Synthetic data parameters
SYNTHETIC_PARAMS = {
    "num_partners": 20,
    "num_clicks_per_partner": 15,
    "num_conversions": 30,
    "fraud_ratio": 0.25,
    "churn_ratio": 0.3,
}

# Endpoints that generate ML training data or score many rows can be slow.
LONG_TIMEOUT = 180.0
DEFAULT_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def _err(msg: str) -> None:
    print(f"  [ERR] {msg}", file=sys.stderr)


def _section(title: str) -> None:
    bar = "-" * 60
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_register_admin(client: httpx.Client) -> None:
    """POST /api/v1/auth/register — create the admin account (idempotent)."""
    try:
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "role": "admin"},
        )
        if resp.status_code == 201:
            _ok(f"Admin registered: {ADMIN_EMAIL}")
        elif resp.status_code == 409:
            _ok(f"Admin already exists (skipping): {ADMIN_EMAIL}")
        else:
            _err(f"Unexpected {resp.status_code}: {resp.text}")
    except Exception as exc:
        _err(f"Admin registration request failed: {exc}")


def step_login_admin(client: httpx.Client) -> Optional[str]:
    """POST /api/v1/auth/login — obtain admin JWT; returns token or None."""
    try:
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        resp.raise_for_status()
        token: str = resp.json()["access_token"]
        _ok(f"Admin JWT obtained (…{token[-12:]})")
        return token
    except Exception as exc:
        _err(f"Admin login failed: {exc}")
        return None


def step_register_partners(client: httpx.Client) -> list[dict]:
    """POST /api/v1/auth/register × 3 — create partner accounts."""
    partners: list[dict] = []
    for i in range(1, PARTNER_COUNT + 1):
        email = f"partner{i}@referrai.com"
        name = f"Demo Partner {i}"
        try:
            resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": email,
                    "password": PARTNER_PASSWORD,
                    "role": "partner",
                    "name": name,
                },
            )
            if resp.status_code in (201, 409):
                note = "registered" if resp.status_code == 201 else "already exists"
                _ok(f"{email} — {note}")
                partners.append(
                    {
                        "email": email,
                        "name": name,
                        "token": None,
                        "partner_id": None,
                        "slug": None,
                        "code": None,
                    }
                )
            else:
                _err(f"{email}: unexpected {resp.status_code} — {resp.text}")
        except Exception as exc:
            _err(f"{email}: register failed — {exc}")
    return partners


def step_partner_setup(client: httpx.Client, partners: list[dict]) -> None:
    """For each partner: login → GET /me/partner → POST link → POST code."""
    for p in partners:
        # Login
        try:
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": p["email"], "password": PARTNER_PASSWORD},
            )
            resp.raise_for_status()
            p["token"] = resp.json()["access_token"]
            _ok(f"{p['email']} logged in")
        except Exception as exc:
            _err(f"{p['email']}: login failed — {exc}")
            continue

        hdrs = {"Authorization": f"Bearer {p['token']}"}

        # Fetch partner profile to resolve partner_id (needed for conversions)
        try:
            resp = client.get("/api/v1/me/partner", headers=hdrs)
            resp.raise_for_status()
            p["partner_id"] = resp.json()["id"]
            _ok(f"{p['email']} partner_id={p['partner_id']}")
        except Exception as exc:
            _err(f"{p['email']}: GET /me/partner failed — {exc}")

        # Create referral link
        destination = (
            f"https://demo.referrai.com/landing/{p['email'].split('@')[0]}"
        )
        try:
            resp = client.post(
                "/api/v1/referrals/links",
                json={"destination_url": destination},
                headers=hdrs,
            )
            resp.raise_for_status()
            p["slug"] = resp.json()["slug"]
            _ok(f"{p['email']} link slug={p['slug']!r}")
        except Exception as exc:
            _err(f"{p['email']}: create referral link failed — {exc}")

        # Create referral code (no request body required)
        try:
            resp = client.post("/api/v1/referrals/codes", headers=hdrs)
            resp.raise_for_status()
            p["code"] = resp.json()["code"]
            _ok(f"{p['email']} code={p['code']!r}")
        except Exception as exc:
            _err(f"{p['email']}: create referral code failed — {exc}")


def step_simulate_clicks(client: httpx.Client, partners: list[dict]) -> int:
    """GET /r/{slug} × 10 per partner — simulates organic link traffic."""
    total = 0
    clicks_per_partner = 10
    for p in partners:
        slug = p.get("slug")
        if not slug:
            _err(f"{p['email']}: no slug — skipping clicks")
            continue
        for _ in range(clicks_per_partner):
            try:
                resp = client.get(f"/r/{slug}", follow_redirects=False)
                if resp.status_code in (301, 302):
                    total += 1
                else:
                    _err(f"GET /r/{slug}: unexpected status {resp.status_code}")
            except Exception as exc:
                _err(f"GET /r/{slug}: request failed — {exc}")
    return total


def step_synthetic_data(
    client: httpx.Client, admin_headers: dict
) -> None:
    """POST /api/v1/admin/synthetic-data — generate ML training data."""
    try:
        resp = client.post(
            "/api/v1/admin/synthetic-data",
            json=SYNTHETIC_PARAMS,
            headers=admin_headers,
            timeout=LONG_TIMEOUT,
        )
        resp.raise_for_status()
        _ok(f"Synthetic data created: {resp.json()}")
    except Exception as exc:
        _err(f"Synthetic data generation failed: {exc}")


def step_record_conversions(
    client: httpx.Client, admin_headers: dict, partners: list[dict]
) -> int:
    """POST /api/v1/referrals/conversions — record 5 real conversions."""
    eligible = [p for p in partners if p.get("partner_id")]
    if not eligible:
        _err("No partners with resolved IDs — skipping conversions")
        return 0

    recorded = 0
    for i, value in enumerate(CONVERSION_VALUES):
        # Cycle through partners so each gets roughly equal coverage
        p = eligible[i % len(eligible)]
        payload: dict = {
            "partner_id": p["partner_id"],
            "conversion_value": str(value),
        }
        # Attach referral code when available for attribution
        if p.get("code"):
            payload["referral_code"] = p["code"]

        try:
            resp = client.post(
                "/api/v1/referrals/conversions",
                json=payload,
                headers=admin_headers,
            )
            resp.raise_for_status()
            recorded += 1
            _ok(f"Conversion ${value:.2f} → {p['email']}")
        except Exception as exc:
            _err(f"Conversion {i + 1} (${value:.2f}) failed: {exc}")

    return recorded


def step_run_churn_scoring(
    client: httpx.Client, admin_headers: dict
) -> None:
    """POST /api/v1/admin/run-churn-scoring — score all active non-synthetic partners."""
    try:
        resp = client.post(
            "/api/v1/admin/run-churn-scoring",
            headers=admin_headers,
            timeout=LONG_TIMEOUT,
        )
        resp.raise_for_status()
        _ok(f"Churn scoring complete: {resp.json()}")
    except Exception as exc:
        _err(f"Churn scoring failed: {exc}")


def step_print_summary(
    client: httpx.Client,
    partners: list[dict],
    total_clicks: int,
    real_conversions: int,
) -> None:
    """GET /api/v1/wallet per partner — print final balance table."""
    print()
    col_email = 32
    col_id = 38
    col_bal = 15
    header = (
        f"  {'Partner Email':<{col_email}} {'Partner ID':<{col_id}} "
        f"{'Wallet Balance':>{col_bal}}"
    )
    print(header)
    print(f"  {'-' * col_email} {'-' * col_id} {'-' * col_bal}")

    for p in partners:
        if not p.get("token"):
            continue
        hdrs = {"Authorization": f"Bearer {p['token']}"}
        balance_str = "n/a"
        try:
            resp = client.get("/api/v1/wallet", headers=hdrs)
            resp.raise_for_status()
            balance_str = f"${float(resp.json()['balance']):.2f}"
        except Exception as exc:
            balance_str = f"err: {exc}"

        pid = str(p.get("partner_id") or "—")
        print(
            f"  {p['email']:<{col_email}} {pid:<{col_id}} "
            f"{balance_str:>{col_bal}}"
        )

    print()
    print(f"  Partners created/verified : {len([p for p in partners if p.get('partner_id')])}")
    print(f"  Clicks simulated          : {total_clicks}")
    print(f"  Real conversions recorded : {real_conversions}")
    print()
    print(f"  Admin login  : {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"  Partner login: partner1@referrai.com / {PARTNER_PASSWORD}")
    print(f"  Frontend     : http://localhost:5173")
    print(f"  API docs     : {BASE_URL}/docs")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Seed demo data into a running ReferrAI instance at "
            f"{BASE_URL}."
        )
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Print instructions for wiping the database before re-running "
            "this script, then exit."
        ),
    )
    args = parser.parse_args()

    if args.reset:
        print()
        print("  To reset the database and start fresh:")
        print()
        print("    docker-compose down -v          # drops all volumes")
        print("    docker-compose up -d db          # restart Postgres only")
        print("    cd backend")
        print("    alembic upgrade head             # re-apply migrations")
        print()
        print("  Then re-run without --reset:")
        print("    python backend/scripts/demo_seed.py")
        print()
        sys.exit(0)

    # Use a single persistent connection for all steps
    client = httpx.Client(base_url=BASE_URL, timeout=DEFAULT_TIMEOUT)

    try:
        # Step 1 — Register admin (idempotent — 409 is OK)
        _section("Step 1: Register admin user")
        step_register_admin(client)

        # Step 2 — Admin login; abort if token cannot be obtained
        _section("Step 2: Admin login")
        admin_token = step_login_admin(client)
        if admin_token is None:
            _err("Cannot continue without admin token.")
            sys.exit(1)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Step 3 — Register 3 partner accounts
        _section("Step 3: Register partner users")
        partners = step_register_partners(client)

        # Step 4 — Partner login, profile lookup, link + code creation
        _section("Step 4: Partner logins, referral links and codes")
        step_partner_setup(client, partners)

        # Step 5 — 10 clicks per partner link (public endpoint, no auth)
        _section("Step 5: Simulate 10 clicks per referral link")
        total_clicks = step_simulate_clicks(client, partners)
        _ok(f"{total_clicks} total clicks recorded")

        # Step 6 — Generate synthetic ML training data
        _section("Step 6: Generate synthetic data (may take ~30 s)")
        step_synthetic_data(client, admin_headers)

        # Step 7 — Record 5 real conversions as admin
        _section("Step 7: Record 5 real conversions ($50–$500)")
        real_conversions = step_record_conversions(client, admin_headers, partners)
        _ok(f"{real_conversions}/5 conversions recorded")

        # Step 8 — Trigger churn scoring batch
        _section("Step 8: Run churn scoring for all active partners")
        step_run_churn_scoring(client, admin_headers)

        # Step 9 — Print summary table with wallet balances
        _section("Step 9: Summary")
        step_print_summary(client, partners, total_clicks, real_conversions)

    finally:
        client.close()


if __name__ == "__main__":
    main()
