# ReferrAI — Development Roadmap

## Delivery Philosophy

Build vertically, not horizontally. Complete each phase end-to-end (backend + frontend + tests) before moving to the next. The goal is a demonstrable, working system at the end of each phase — not a collection of half-finished modules.

---

## Phase 1 — Foundation
**Goal:** A running application skeleton with auth, database, and settings infrastructure.

### Deliverables
- Docker Compose environment (PostgreSQL + FastAPI + React + nginx)
- SQLAlchemy models for all entities
- Alembic migration for initial schema
- Seed migration: default settings, default partner tier
- Auth endpoints: register, login, password reset, JWT middleware
- RBAC dependency (`require_admin`, `require_partner`)
- Settings CRUD endpoints (admin only)
- Audit log writes on every settings change
- React app scaffold: routing, auth context, protected routes, layout shells for Admin and Partner dashboards

### Exit Criteria
- `docker-compose up` brings up the full stack
- Admin can log in and update a setting via the UI
- Settings change appears in `audit_logs`

---

## Phase 2 — Core Platform
**Goal:** The complete referral-to-commission lifecycle works end-to-end.

### 2a — Referral Management
- Partner: generate referral link (slug), referral code, QR code
- Click tracking endpoint (`GET /r/{slug}`) — records click, redirects
- Conversion recording endpoint — attributes click per attribution model
- Attribution window enforcement (configurable days)
- First-click and last-click attribution modes

### 2b — Commission Management
- `CommissionService.calculate_for_conversion()` supporting percentage, fixed, and tier-based types
- Reads commission config from settings at runtime
- Creates `Commission` and `Transaction` records atomically
- Credits partner `Wallet`

### 2c — Partner Management
- Partner profile CRUD (admin: full; partner: read own)
- Partner tier CRUD (admin only)
- Automatic tier evaluation after each commission credit
- Partner performance counters (`total_referral_count`, `total_revenue_contribution`)

### 2d — Wallet & Payout
- Wallet balance display
- Withdrawal request submission
- Auto-approval logic (threshold + fraud flag gate)
- Admin withdrawal review (approve / reject)
- Payout history and transaction history views

### Exit Criteria
- A partner can generate a referral link, simulate a click, record a conversion, and see a commission credited to their wallet
- A withdrawal request is auto-approved below threshold and queued for review above it
- Tier upgrade triggers correctly when threshold is crossed

---

## Phase 3 — Dashboards & Reporting
**Goal:** Both dashboards are populated with live data and CSV export works.

### Deliverables
- **Admin dashboard:** referral volume (count + chart), conversion rate, total commissions issued, pending payouts, fraud alert count, churn alert count
- **Partner dashboard:** referral list with status, commission list with amounts, wallet balance, quality score (placeholder until Phase 4), rank
- Date range filters on admin analytics views
- CSV export for referrals, commissions, and partner performance
- All queries exclude `is_synthetic = true` records

### Exit Criteria
- Admin dashboard renders real aggregated data
- Partner dashboard shows the correct partner's own data only
- CSV export downloads a correctly formatted file

---

## Phase 4 — AI Features
**Goal:** All seven AI capabilities are operational and integrated into the UI.

### 4a — Synthetic Data Generation
- `SyntheticDataGenerator` — generates realistic partner, click, conversion, fraud-labelled, and churn-labelled records
- All synthetic records tagged `is_synthetic = true`
- Admin trigger endpoint to generate synthetic data (used for model training and demo)

### 4b — Referral Quality Scoring
- Train `ReferralQualityScorer` on synthetic data
- Features: time-to-convert, source, device type, conversion value, partner tier
- Scores stored in `ai_scores` with `score_type = 'quality'`
- SHAP-based explanation per score
- Score displayed in referral details and partner profile

### 4c — Fraud Detection
- Rule-based pre-checks: referral velocity (clicks/hour), IP reuse, device reuse, self-referral
- `FraudDetector` using Isolation Forest on click pattern features
- Score stored in `ai_scores` with `score_type = 'fraud_risk'`
- `FraudFlag` created when score > `fraud.alert_threshold`
- Fraud alert queue on admin dashboard with explanation
- Withdrawal gate: blocks auto-approval when active fraud flag exists

### 4d — Partner Churn Prediction
- `ChurnPredictor` using Gradient Boosting on partner activity features (recency, frequency, revenue trend)
- Score stored in `ai_scores` with `score_type = 'churn_risk'`
- At-risk partner list on admin dashboard (score > `churn.alert_threshold`)
- Score displayed on partner profile

### 4e — Smart Partner Ranking
- `PartnerRanker` — weighted composite of quality score, churn risk (inverted), referral volume, revenue contribution
- Weights read from `ranking.weights` settings key
- Score stored in `ai_scores` with `score_type = 'ranking'`
- Ranked partner list on admin dashboard
- Rank displayed on partner dashboard

### 4f — AI Partner Discovery
- `PartnerDiscovery` — accepts candidate business records (CSV upload or manual entry)
- Sentence Transformers embed business category + description
- Cosine similarity against existing partner profiles
- `partner_potential` score with geographic and category factors
- Ranked candidate list on admin discovery page with score factors

### 4g — Explainable AI Integration
- Every score stored in `ai_scores` must include `contributing_factors` (SHAP values) and `explanation` (plain language)
- `Explainer` class generates plain-language strings from SHAP top features
- Explanations rendered in the UI next to each score (tooltip or expandable panel)
- All XAI explanations based only on actual model inputs (FR-AI-XAI-004)

### Exit Criteria
- All seven AI features produce scores with explanations
- Fraud alert appears on admin dashboard and blocks withdrawal auto-approval
- Churn alert appears on admin dashboard
- AI failures do not break conversion recording or commission calculation

---

## Phase 5 — Hardening & Demo Preparation
**Goal:** The system is stable, secure, and ready for a live end-to-end demonstration.

### Deliverables
- End-to-end integration tests covering the main happy paths
- Performance validation: API responses < 2s, scoring < 1s (NFR-PER-001/002)
- Graceful degradation testing: confirm core platform works with AI module disabled
- `.env.example` with all required environment variables documented
- Docker Compose production configuration (nginx HTTPS, environment separation)
- Demo script: referral creation → click simulation → conversion → commission → fraud alert → withdrawal → admin review

### Exit Criteria
- Full demo runs without errors
- Fraud detection, churn prediction, and quality scoring all produce explanations visible in the UI
- Admin can configure a commission setting without code changes and see it reflected in the next commission calculation

---

## Scope Boundaries (Not In This Roadmap)

Per BRD Section 4.2 — the following will **not** be built:
- Campaign management or marketing asset management
- Hybrid commission models
- Multi-step payout approval workflows
- Multi-touch attribution
- Multi-tenant SaaS architecture
- Live payment gateway integrations (payout tracking only, no actual fund transfer)
- ERP/CRM integrations
