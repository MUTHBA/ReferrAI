# ReferrAI — Architecture Document

## 1. System Overview

ReferrAI is a three-layer web application: a React frontend, a FastAPI backend, and a PostgreSQL database. The AI capabilities are implemented as an internal Python package within the backend process, not as a separate microservice. This keeps deployment simple while satisfying the resilience requirement that the core platform must continue operating when AI models are unavailable.

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│          Admin Dashboard        Partner Dashboard           │
│                    React.js (SPA)                           │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS / REST JSON
┌──────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │   Auth   │  │ Referral │  │Commission│  │  Partner  │  │
│  │  Module  │  │  Module  │  │  Module  │  │  Module   │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Wallet & │  │Dashboard │  │ Settings │  │  Audit    │  │
│  │  Payout  │  │Reporting │  │  Module  │  │   Log     │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   AI Module (internal pkg)          │   │
│  │  SyntheticGen │ QualityScorer │ FraudDetector       │   │
│  │  ChurnPredict │ PartnerRanker │ PartnerDiscovery     │   │
│  │  Explainability (SHAP)                              │   │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │ SQLAlchemy (async)
┌──────────────────────▼──────────────────────────────────────┐
│                    PostgreSQL                               │
│     Users │ Partners │ Referrals │ Commissions │ Wallets    │
│     AIScores │ FraudFlags │ Settings │ AuditLogs │ ...      │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Backend Layer Design

The backend uses a strict four-layer architecture. Each layer has a single responsibility and dependencies only point downward.

```
HTTP Request
     │
     ▼
┌─────────────┐
│   Routes    │  Validate input (Pydantic), call service, return response.
│  (api/v1/)  │  No business logic here.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Services   │  Business logic, orchestration, transaction boundaries.
│ (services/) │  Calls repositories and AI module. Raises domain exceptions.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Repositories │  All database queries. Returns domain models or None.
│(repositories│  No business logic. One repository class per entity.
└──────┬──────┘
       │
       ▼
┌─────────────┐
│SQLAlchemy   │  ORM models. Defines table structure and relationships.
│  Models     │
└─────────────┘
```

---

## 3. Module Responsibilities

### 3.1 Authentication Module
- User registration, login, password reset
- JWT token issuance and validation
- Role-based access control middleware (Admin / Partner)
- All protected routes declare a `Depends(get_current_user)` or `Depends(require_admin)` dependency

### 3.2 Referral Management Module
- Generate referral links (slug-based URLs) and referral codes per partner
- Generate QR codes from referral link URLs (served as PNG or base64)
- Track clicks: log IP, device info, source, timestamp on every `GET /r/{slug}` hit
- Record conversions: link a conversion to a click (first-click or last-click per settings)
- Attribution logic lives in `ReferralService.attribute_conversion()` and reads `referral.attribution_model` from settings at runtime

### 3.3 Commission Management Module
- `CommissionService.calculate_for_conversion()` is triggered after every conversion is recorded
- Reads the partner's current tier and the active commission settings to determine type (percentage / fixed / tier-based) and value
- Creates a `Commission` record and credits the partner's `Wallet`
- Creates a `Transaction` record for the wallet ledger
- Evaluates tier upgrade eligibility after crediting (calls `PartnerService.evaluate_tier_upgrade()`)

### 3.4 Partner Management Module
- Partner profiles (name, business name, category, contact, status, tier)
- Tier definitions are admin-configured (name, thresholds, commission overrides)
- `evaluate_tier_upgrade()` checks the partner's lifetime referral volume and revenue against tier thresholds; upgrades are one-way (never downgrade automatically)
- Displays AI scores (quality, fraud risk, churn risk, rank) sourced from `AIScores`

### 3.5 Wallet & Payout Module
- Each partner has exactly one `Wallet` (created on partner registration)
- `WithdrawalService.request_withdrawal()`:
  1. Checks balance sufficiency
  2. Checks partner's active fraud flags — if any exist with `pending_review` status, force manual review regardless of amount
  3. Checks amount against `wallet.auto_approval_threshold` — auto-approve if below threshold
  4. Otherwise sets status to `pending` for admin review
- Every balance change (commission credit or withdrawal debit) writes a `Transaction` record

### 3.6 Dashboard & Reporting Module
- Admin dashboard: referral volume, conversion count, commission totals, payout status, fraud alert list, churn alert list
- Partner dashboard: own referrals, commissions, wallet balance, quality score, rank
- All dashboard queries default to excluding `is_synthetic = true` records
- CSV export via streaming response for large datasets

### 3.7 Settings Module
- Key-value store in the `settings` table
- All values stored as JSONB for flexibility (numbers, strings, lists)
- `SettingsService.get(key)` is used by all other services — no direct table reads
- Every write calls `AuditLogService.log()` (FR-SET-009)

### 3.8 AI Module

The AI module is a Python package (`backend/app/ai/`) with the following sub-modules:

| Sub-module | Class | Model/Method |
|---|---|---|
| `generators/` | `SyntheticDataGenerator` | Faker + statistical distributions |
| `scoring/quality.py` | `ReferralQualityScorer` | Scikit-learn classifier (Random Forest) |
| `scoring/fraud.py` | `FraudDetector` | Isolation Forest + rule-based signals |
| `scoring/churn.py` | `ChurnPredictor` | Scikit-learn classifier (Gradient Boosting) |
| `scoring/ranking.py` | `PartnerRanker` | Weighted composite scoring |
| `discovery/` | `PartnerDiscovery` | Sentence Transformers + cosine similarity |
| `explainability/` | `Explainer` | SHAP TreeExplainer + plain-language templates |

**AI Invocation Pattern:**

AI scoring is **never** called synchronously in the request-response cycle for core operations. It is triggered as a FastAPI `BackgroundTask` after a conversion is recorded or on a scheduled basis.

```
POST /conversions
  → CommissionService.calculate_for_conversion()   [synchronous, blocking]
  → BackgroundTasks.add_task(ai_service.score_referral, conversion_id)  [async, non-blocking]
  → return 201 to client

# Background task:
  → FraudDetector.score(click_data)               [try/except]
  → ReferralQualityScorer.score(conversion_data)  [try/except]
  → Store results in ai_scores                    [try/except]
  → Create fraud_flag if score > threshold        [try/except]
  # Any exception here is logged and swallowed — core data is already committed
```

---

## 4. Key Data Flows

### 4.1 Referral Click Tracking
```
Browser GET /r/{slug}
  → ReferralClickRepository.create(link_id, ip, device, source)
  → HTTP 302 Redirect to destination URL
```
Click tracking is fire-and-forget from the user's perspective. Even if the DB write fails, the redirect still occurs.

### 4.2 Referral Conversion Recording
```
POST /conversions  { referral_code | click_id, conversion_value }
  → ReferralService.attribute_conversion()      # find the right click per attribution model
  → ReferralConversionRepository.create()
  → CommissionService.calculate_for_conversion()
      → Read partner tier + settings
      → Create Commission record
      → WalletService.credit(partner_id, amount)
          → Update wallet.balance
          → Create Transaction record
      → PartnerService.evaluate_tier_upgrade()
  → BackgroundTask: AI scoring
  → 201 Created
```

### 4.3 Withdrawal Request
```
POST /withdrawals  { amount }
  → Validate balance >= amount
  → Check for active fraud flags  →  force manual review if flagged
  → Compare amount to auto_approval_threshold
      If amount <= threshold AND no fraud flags:
          → auto-approve
          → WalletService.debit(amount)
          → Create Transaction record
      Else:
          → status = 'pending'
          → Notify admin queue
  → 201 Created
```

### 4.4 Admin Fraud Flag Review
```
PATCH /fraud-flags/{id}  { status: 'confirmed' | 'dismissed' }
  → FraudFlagService.review(flag_id, admin_user, status)
  → Update fraud_flags.status
  → AuditLogService.log(action='fraud_flag_reviewed', ...)
  → 200 OK
```

---

## 5. Security Design

- Passwords hashed with `bcrypt` via `passlib`
- JWT access tokens; short expiry (configurable)
- All routes use `Depends(get_current_user)`; admin routes additionally use `Depends(require_role('admin'))`
- HTTPS enforced at the reverse proxy / Docker layer in deployed environments
- All admin-side mutations (settings, payout approvals, fraud reviews) write to `audit_logs`
- AI predictions never trigger automated account suspension (FR-AI-FRD-006)

---

## 6. Resilience Design

Per NFR-REL-001 and NFR-REL-002:

- Every AI call is wrapped in `try/except Exception`. On failure, the score is stored as `null` and the exception is logged. The calling service continues normally.
- Referral click tracking and fraud rule checks (velocity, IP reuse, device reuse) run as deterministic rule-based checks independent of ML models.
- The `settings` table has application-level defaults used if a key is missing, so a missing settings row never crashes the application.

---

## 7. Deployment Architecture

```
┌──────────────────────────────────────┐
│           Docker Compose             │
│  ┌─────────┐  ┌────────┐  ┌──────┐  │
│  │ nginx   │  │backend │  │  db  │  │
│  │ :80/443 │→ │ :8000  │→ │ :5432│  │
│  └─────────┘  └────────┘  └──────┘  │
│               ┌────────┐            │
│               │frontend│            │
│               │ :3000  │            │
│               └────────┘            │
└──────────────────────────────────────┘
```

nginx serves the React build as static files and reverse-proxies `/api/*` to the FastAPI backend. All services share a Docker network. The database volume is persisted. Environment variables are injected via `.env` file.
