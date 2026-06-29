# Referral Conversion Contract

> **Audience:** Mukul — building `CommissionService.calculate_for_conversion()` in COM-001.
> This document describes exactly what data your code will read from the database
> and when that data exists.

---

## How the flow works

1. A partner generates a referral **link** (`/api/v1/referrals/links`) or a short **code** (`/api/v1/referrals/codes`). Both are stored in the DB and tied to a `partner_id`.

2. An anonymous visitor follows the link. `GET /r/{slug}` records a **ReferralClick** row — capturing the link that was followed, the partner it belongs to, the visitor's IP, user-agent, and UTM source — then immediately 302-redirects the visitor to the destination URL. The click insert is best-effort: if it fails, the redirect still happens.

3. When the visitor completes a purchase or sign-up, the **conversion** is recorded by `REF-004` (not yet built — see the note below). `REF-004` creates a `ReferralConversion` row that ties the conversion back to a click (using the attribution model from the settings table) and to the partner who should receive commission.

4. **Your job (COM-001):** Once a `ReferralConversion` row exists, `calculate_for_conversion()` reads it, looks up the partner's tier and the default commission settings, and writes a `Commission` row.

---

## The `referral_conversions` table

This is the table your code reads. Each row represents one completed conversion that earns a commission.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `UUID` | No | Primary key |
| `partner_id` | `UUID` (FK → `partners.id`) | No | The partner who earns the commission |
| `click_id` | `UUID` (FK → `referral_clicks.id`) | Yes | The click that led to this conversion; null if attribution could not be resolved |
| `referral_link_id` | `UUID` (FK → `referral_links.id`) | Yes | The link the visitor originally followed; null if conversion came via a code |
| `referral_code_id` | `UUID` (FK → `referral_codes.id`) | Yes | The code the visitor used; null if conversion came via a link |
| `conversion_value` | `DECIMAL(12,2)` | No | The monetary value of the conversion (e.g. purchase amount) |
| `attribution_model` | `VARCHAR(20)` CHECK IN `('first_click', 'last_click')` | No | Which click was credited — determined at conversion time from the `referral.attribution_model` setting |
| `converted_at` | `TIMESTAMPTZ` | No | UTC timestamp of the conversion event |
| `is_synthetic` | `BOOLEAN` | No | `true` for AI-generated training data; **always filter `is_synthetic = false`** in real queries |

---

## Critical note: REF-004 does not exist yet

This branch (`feat/referrals-REF-001-003`) only builds:
- Link generation (REF-001)
- Code generation (REF-002)
- Click tracking + redirect (REF-003)

**REF-004 — the endpoint that creates `ReferralConversion` rows — has not been implemented.** Until REF-004 ships, the `referral_conversions` table will be empty. Your `calculate_for_conversion()` code can be written now and will work correctly once REF-004 exists, but there is no test data in the DB today.

Do not write defensive code assuming conversions might arrive in a different shape — the table schema is final (it comes from the DB-002 initial migration and will not change). Just write against the schema above.

---

## Example: what a `ReferralConversion` row looks like

Once REF-004 ships, a row created from a link click might look like this:

```json
{
  "id": "a3f1c2d4-89ab-4cde-b012-3456789abcde",
  "partner_id": "7f8e9d0c-1234-5678-9abc-def012345678",
  "click_id": "b2e3f4a5-5678-4abc-def0-123456789abc",
  "referral_link_id": "c1d2e3f4-abcd-4ef0-1234-56789abcdef0",
  "referral_code_id": null,
  "conversion_value": "149.99",
  "attribution_model": "last_click",
  "converted_at": "2026-06-29T14:32:01.000Z",
  "is_synthetic": false
}
```

For a code-based conversion (no click tracked):

```json
{
  "id": "d4e5f6a7-bcde-4f01-2345-6789abcdef01",
  "partner_id": "7f8e9d0c-1234-5678-9abc-def012345678",
  "click_id": null,
  "referral_link_id": null,
  "referral_code_id": "e5f6a7b8-cdef-4012-3456-789abcdef012",
  "conversion_value": "49.00",
  "attribution_model": "last_click",
  "converted_at": "2026-06-29T15:10:44.000Z",
  "is_synthetic": false
}
```
