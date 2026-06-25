# ReferrAI — Database Design

## Design Principles

- UUIDs for all primary keys (portable, safe for future distribution)
- `DECIMAL(12,2)` for all monetary values — never `FLOAT`
- JSONB for flexible/variable data (device info, score factors, settings values)
- `is_synthetic` flag on all tables that can contain AI-generated training data
- Soft deletes via status fields (no `deleted_at` pattern — business data must be preserved for audit)
- All timestamp columns use `TIMESTAMP WITH TIME ZONE` (stored as UTC)

---

## Entity Relationship Overview

```
users ──────────────── partners
                           │
              ┌────────────┼────────────┐
              │            │            │
      partner_tiers  referral_links  referral_codes
                           │            │
                     referral_clicks ───┘
                           │
                  referral_conversions
                           │
                       commissions
                           │
                        wallets
                           │
                      withdrawals
                           │
                      transactions
                           │
                       ai_scores
                           │
                      fraud_flags
                           │
                  discovered_partners
                           │
                       settings
                           │
                       audit_logs
```

---

## Tables

### users

Stores authentication credentials and role for both admins and partners.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() |
| email | VARCHAR(255) | NOT NULL, UNIQUE |
| password_hash | VARCHAR(255) | NOT NULL |
| role | VARCHAR(20) | NOT NULL, CHECK IN ('admin', 'partner') |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `email` (unique), `role`

---

### partner_tiers

Admin-configured tier definitions. Each tier has its own commission override.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(100) | NOT NULL, UNIQUE |
| rank_order | INTEGER | NOT NULL, UNIQUE — 1=lowest, ascending |
| min_referral_count | INTEGER | NOT NULL, DEFAULT 0 |
| min_revenue_contribution | DECIMAL(12,2) | NOT NULL, DEFAULT 0 |
| commission_type | VARCHAR(20) | NOT NULL, CHECK IN ('percentage', 'fixed', 'tier_based') |
| commission_value | DECIMAL(10,4) | NOT NULL — percentage as decimal (e.g. 0.10) or fixed amount |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

---

### partners

Partner profile linked one-to-one with a user account.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | NOT NULL, UNIQUE, FK → users.id |
| name | VARCHAR(255) | NOT NULL |
| business_name | VARCHAR(255) | |
| category | VARCHAR(100) | |
| email | VARCHAR(255) | NOT NULL |
| phone | VARCHAR(50) | |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'active', CHECK IN ('active', 'suspended', 'pending') |
| tier_id | UUID | FK → partner_tiers.id, NULLABLE |
| total_referral_count | INTEGER | NOT NULL, DEFAULT 0 — denormalized counter |
| total_revenue_contribution | DECIMAL(12,2) | NOT NULL, DEFAULT 0 — denormalized sum |
| is_synthetic | BOOLEAN | NOT NULL, DEFAULT FALSE |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `user_id` (unique), `tier_id`, `status`, `is_synthetic`

> `total_referral_count` and `total_revenue_contribution` are denormalized for performance. They are incremented atomically within the same transaction as `CommissionService.calculate_for_conversion()`.

---

### referral_links

One or more referral links per partner.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| partner_id | UUID | NOT NULL, FK → partners.id |
| slug | VARCHAR(100) | NOT NULL, UNIQUE — URL-safe identifier |
| destination_url | VARCHAR(2048) | NOT NULL |
| qr_code_data | TEXT | NULLABLE — base64 PNG or URL |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `partner_id`, `slug` (unique)

---

### referral_codes

Short alphanumeric codes per partner (e.g. `JOHN2024`).

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| partner_id | UUID | NOT NULL, FK → partners.id |
| code | VARCHAR(50) | NOT NULL, UNIQUE |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `partner_id`, `code` (unique)

---

### referral_clicks

One row per click event on a referral link or code.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| referral_link_id | UUID | FK → referral_links.id, NULLABLE |
| referral_code_id | UUID | FK → referral_codes.id, NULLABLE |
| partner_id | UUID | NOT NULL, FK → partners.id — denormalized for query efficiency |
| ip_address | VARCHAR(45) | NULLABLE — IPv4 or IPv6 |
| device_info | JSONB | NULLABLE — user-agent, OS, device type |
| source | VARCHAR(255) | NULLABLE — utm_source or referring domain |
| clicked_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| is_synthetic | BOOLEAN | NOT NULL, DEFAULT FALSE |

**Constraints:** CHECK (referral_link_id IS NOT NULL OR referral_code_id IS NOT NULL)

**Indexes:** `partner_id`, `clicked_at`, `ip_address`, `is_synthetic`

> `ip_address` and device fingerprinting data from `device_info` are used by the fraud detector.

---

### referral_conversions

Records when a referred user completes the desired action (signup, purchase, etc.).

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| partner_id | UUID | NOT NULL, FK → partners.id |
| click_id | UUID | FK → referral_clicks.id, NULLABLE — null if code-only attribution |
| referral_link_id | UUID | FK → referral_links.id, NULLABLE |
| referral_code_id | UUID | FK → referral_codes.id, NULLABLE |
| conversion_value | DECIMAL(12,2) | NOT NULL, DEFAULT 0 — monetary value of this conversion |
| attribution_model | VARCHAR(20) | NOT NULL, CHECK IN ('first_click', 'last_click') |
| converted_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| is_synthetic | BOOLEAN | NOT NULL, DEFAULT FALSE |

**Indexes:** `partner_id`, `click_id`, `converted_at`, `is_synthetic`

---

### commissions

One commission record per conversion. Immutable after creation except for status.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| partner_id | UUID | NOT NULL, FK → partners.id |
| conversion_id | UUID | NOT NULL, UNIQUE, FK → referral_conversions.id |
| amount | DECIMAL(12,2) | NOT NULL |
| commission_type | VARCHAR(20) | NOT NULL, CHECK IN ('percentage', 'fixed', 'tier_based') |
| tier_id | UUID | FK → partner_tiers.id, NULLABLE — snapshot of tier at time of calculation |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'approved', CHECK IN ('pending', 'approved', 'paid', 'reversed') |
| calculated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `partner_id`, `conversion_id` (unique), `status`, `calculated_at`

---

### wallets

One wallet per partner. Acts as the ledger summary.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| partner_id | UUID | NOT NULL, UNIQUE, FK → partners.id |
| balance | DECIMAL(12,2) | NOT NULL, DEFAULT 0, CHECK (balance >= 0) |
| total_earned | DECIMAL(12,2) | NOT NULL, DEFAULT 0 |
| total_withdrawn | DECIMAL(12,2) | NOT NULL, DEFAULT 0 |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `partner_id` (unique)

---

### withdrawals

Withdrawal requests submitted by partners.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| partner_id | UUID | NOT NULL, FK → partners.id |
| wallet_id | UUID | NOT NULL, FK → wallets.id |
| amount | DECIMAL(12,2) | NOT NULL, CHECK (amount > 0) |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending', CHECK IN ('pending', 'approved', 'rejected', 'paid') |
| requires_manual_review | BOOLEAN | NOT NULL, DEFAULT FALSE |
| reviewed_by | UUID | FK → users.id, NULLABLE |
| reviewed_at | TIMESTAMPTZ | NULLABLE |
| notes | TEXT | NULLABLE |
| requested_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `partner_id`, `status`, `requested_at`

---

### transactions

Immutable ledger of all wallet movements.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| wallet_id | UUID | NOT NULL, FK → wallets.id |
| reference_id | UUID | NOT NULL — commission.id or withdrawal.id |
| reference_type | VARCHAR(20) | NOT NULL, CHECK IN ('commission', 'withdrawal') |
| amount | DECIMAL(12,2) | NOT NULL — positive = credit, negative = debit |
| balance_after | DECIMAL(12,2) | NOT NULL — snapshot of wallet.balance post-transaction |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `wallet_id`, `reference_id`, `created_at`

> Transactions are append-only. No updates or deletes. The balance can be reconstructed by summing this table.

---

### settings

Key-value store for all admin-configurable business rules.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| key | VARCHAR(100) | NOT NULL, UNIQUE |
| value | JSONB | NOT NULL |
| description | TEXT | |
| updated_by | UUID | FK → users.id, NULLABLE |
| updated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `key` (unique)

**Canonical Setting Keys:**

| Key | Value Type | Default | Description |
|---|---|---|---|
| `commission.default_type` | string | `"percentage"` | Default commission type |
| `commission.default_percentage` | number | `0.10` | e.g. 0.10 = 10% |
| `commission.default_fixed_amount` | number | `10.00` | Fixed commission amount |
| `wallet.min_withdrawal_amount` | number | `10.00` | Minimum withdrawal |
| `wallet.auto_approval_threshold` | number | `100.00` | Auto-approve below this |
| `referral.attribution_model` | string | `"last_click"` | `first_click` or `last_click` |
| `referral.attribution_window_days` | number | `30` | Days click is valid for attribution |
| `fraud.alert_threshold` | number | `70` | Score 0–100; flag if exceeded |
| `churn.alert_threshold` | number | `65` | Score 0–100; alert if exceeded |
| `ranking.weights` | object | `{quality:0.4, churn:0.2, volume:0.2, revenue:0.2}` | Composite rank weights |

---

### ai_scores

Stores all AI-generated scores with their explanations. Append-only — do not update existing rows; insert a new row on each re-score.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| entity_type | VARCHAR(20) | NOT NULL, CHECK IN ('referral', 'partner', 'candidate') |
| entity_id | UUID | NOT NULL |
| score_type | VARCHAR(30) | NOT NULL, CHECK IN ('quality', 'fraud_risk', 'churn_risk', 'ranking', 'partner_potential') |
| score | DECIMAL(5,2) | NOT NULL, CHECK (score >= 0 AND score <= 100) |
| contributing_factors | JSONB | NULLABLE — feature name → SHAP value pairs |
| explanation | TEXT | NULLABLE — plain language explanation |
| model_version | VARCHAR(50) | NULLABLE |
| is_synthetic | BOOLEAN | NOT NULL, DEFAULT FALSE |
| calculated_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `(entity_type, entity_id)`, `score_type`, `calculated_at`

> To get the current score for an entity, query the latest `calculated_at` for the given `entity_id` and `score_type`.

---

### fraud_flags

Created when a fraud score exceeds the configured threshold. One flag per scoring event.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| partner_id | UUID | NOT NULL, FK → partners.id |
| ai_score_id | UUID | NOT NULL, FK → ai_scores.id |
| referral_click_id | UUID | FK → referral_clicks.id, NULLABLE |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending_review', CHECK IN ('pending_review', 'confirmed', 'dismissed') |
| reviewed_by | UUID | FK → users.id, NULLABLE |
| reviewed_at | TIMESTAMPTZ | NULLABLE |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `partner_id`, `status`, `created_at`

---

### discovered_partners

Candidate businesses identified by the AI Partner Discovery module.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| candidate_name | VARCHAR(255) | NOT NULL |
| business_category | VARCHAR(100) | |
| geographic_data | JSONB | NULLABLE |
| raw_data | JSONB | NULLABLE — full source record |
| potential_score | DECIMAL(5,2) | NULLABLE, CHECK (potential_score >= 0 AND potential_score <= 100) |
| score_factors | JSONB | NULLABLE — contributing factor breakdown |
| ai_score_id | UUID | FK → ai_scores.id, NULLABLE |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'new', CHECK IN ('new', 'reviewed', 'invited', 'dismissed') |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `status`, `potential_score`, `created_at`

---

### audit_logs

Immutable log of all administrative and system actions. Append-only.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NULLABLE — null for system-generated events |
| action | VARCHAR(100) | NOT NULL — e.g. `settings.updated`, `fraud_flag.reviewed`, `withdrawal.approved` |
| entity_type | VARCHAR(50) | NULLABLE |
| entity_id | UUID | NULLABLE |
| old_value | JSONB | NULLABLE |
| new_value | JSONB | NULLABLE |
| ip_address | VARCHAR(45) | NULLABLE |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() |

**Indexes:** `user_id`, `action`, `entity_type`, `created_at`

---

## Migration Strategy

- All schema changes are managed through **Alembic** auto-generated migrations
- Migrations are run in CI before deployment (`alembic upgrade head`)
- Never modify existing migration files — always create a new revision
- Seed data (default settings, default tier) is inserted via a dedicated seed migration, not application code

## Performance Notes

- Dashboard aggregate queries should use date-range filters and exclude `is_synthetic` records via a partial index: `CREATE INDEX ... WHERE is_synthetic = FALSE`
- The `ai_scores` table will grow large; consider a partial index on `(entity_type, entity_id, score_type)` filtered to the last 30 days for current-score lookups
- `referral_clicks` will be the highest-volume table; `clicked_at` index is essential for time-series fraud velocity queries
