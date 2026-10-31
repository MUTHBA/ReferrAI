# Stitch correction prompts — round 2

How to use:

1. Paste **Prompt 0 (every screen)** first, with all screens selected (or once per screen if Stitch won't edit several at once).
2. Then paste the screen's own prompt below, with only that screen selected.
3. Screens marked **light touch** need only small fixes.

The prompts describe only what must change, so Stitch keeps everything else. When Stitch invented something the app does not have, the prompt says **remove**. Please don't put it back: I can't wire it to real data.

---

## Prompt 0 — apply to every screen

```
Apply these fixes to this screen and keep everything else as it is.

1. REMOVE all invented "ledger / crypto / compliance" decoration: block heights, ledger hashes,
   "ledger synchronized/operational/verified", "integrity hash", "SHA-256", "enclave",
   "immutable", "telemetry", "governance engine", model version strings like "v2.4" / "v4.18",
   "calibration run ID", "inference runtime", "Fiscal Q4" labels, and footer lines about any of these.
   Footers should be empty.
2. REMOVE the notification bell from the top bar (the app has no notifications). The top bar keeps
   only: breadcrumb on the left, theme toggle on the right.
3. REMOVE invented IDs: "partner_pn_98124", "PRT-88210", "evt_998124", "#ORD-94119". Show the
   partner's name (and email under it where useful). Order IDs look like "demo-order-2041".
4. Sidebar: full viewport height (min-h-screen, sticky), ink #18222F background, white text.
   Brand block is exactly "ReferrAI" with the subtitle "Admin" on admin screens and "Partner" on
   partner screens (no "Commission Ledger", "Partner Portal"). Menu labels never wrap onto two lines.
   The signed-in user's name and email sit at the bottom with a "Sign out" button.
   Admin menu: Overview, Partners, Payouts, Commissions, Record a sale, Tiers, Settings |
   AI: Models, Fraud alerts, Churn risk, Ranking, Discovery | Audit log.
   Partner menu: Dashboard, Referral links, Conversions, Commissions, Wallet, Profile.
   Do NOT put a "Record a sale" button above the admin menu (it is already a menu item).
5. Typography: one font family, Schibsted Grotesk, for everything. No monospace anywhere, including
   money, dates, IDs and IP addresses. Use tabular figures for numbers instead.
6. Sentence case everywhere. No ALL-CAPS labels, no letter-spaced small-caps eyebrows.
7. Buttons never wrap text: whitespace-nowrap, and shorten the label if needed
   ("Export CSV", "New link"). Icons inside buttons never duplicate a "+" character.
8. Nothing may overflow horizontally at 1280px or 1440px width. Wide tables scroll inside their
   own panel (overflow-x-auto), never the page. Key figures never spill out of their cell; shrink
   the number to 24px when a cell is narrow.
9. Dates are in 2026 (today is 19 Oct 2026), formatted "19 Oct 2026" or "19 Oct 2026, 14:32".
   No dates in the future and no 2024/2025.
10. Money: "$1,240.50". Positive amounts jade, negative amounts rose with a minus sign.
11. Only one toast or one dialog at a time. Never stack a dialog on top of another dialog or toast.
```

---

## Auth screens (no screenshots were exported — HTML only)

### Sign in — light touch
```
Edit the Sign in screen.
- Fields: Email, Password (with show/hide), "Forgot password?" link, primary button "Sign in",
  and "New partner? Create an account" link to Become a partner.
- REMOVE any "Sign in with passkey", SSO/Google buttons, "Remember this device" and
  "Secured by…" badges if present.
- Error state: a rose alert above the form: "Email or password is incorrect."
```

### Become a partner
```
Edit the Become a partner (sign-up) screen.
- Fields only: Full name, Business name (optional), Category (select: Fitness, Fashion & apparel,
  Food & drink, Tech & productivity, Beauty, Travel, Other), Phone (optional), Email, Password.
- Password rule text is exactly: "At least 8 characters." REMOVE strength meters, "entropy",
  and rules about symbols/numbers/uppercase.
- REMOVE the role selector (sign-up only creates partners), terms checkboxes about payouts/KYC,
  and any "verification" or "tax ID" field.
- Primary button "Create account", link "Already a partner? Sign in".
```

### Reset your password
```
Edit the Reset your password screen.
- One field: Email. Button "Send reset link". Link "Back to sign in".
- After submit, replace the form with: "If an account exists for that email, we've sent a reset
  link. It expires in 30 minutes." REMOVE any SMS / authenticator / security-question options.
```

### Choose a new password
```
Edit the Choose a new password screen.
- Fields: New password, Confirm new password. Hint: "At least 8 characters."
- Button "Save new password". Expired-link state: rose alert "This reset link has expired or was
  already used." with a "Request a new link" button.
- REMOVE strength meters and extra password rules.
```

---

## Partner screens

### Partner dashboard
```
Edit the Partner dashboard.
- Ledger strip (one bordered band, 4 cells): Wallet balance, Earned this month, Conversions this
  month, Clicks this month. Each with a small context line ("+12% vs last month").
- Keep the earnings area chart (last 30 days, jade fill) and the tier progress panel.
- Tier progress text: "14 more sales and $1,850 more revenue to reach Gold" — BOTH are needed.
- Keep "Recent conversions" (Date, Order ID, Order value, Commission, Quality score badge).
- REMOVE "trust score", "priority payouts", "escrow" and any badge or text about them.
```

### Referral links
```
Edit the Referral links screen.
- Two sections: "Links" (Link URL like referrai.app/r/k3x9p2, Created, Clicks, Conversions,
  Copy and QR buttons) and "Codes" (Code like PRIYA-7KQ2, Created, Uses, Copy button).
- Codes are generated automatically: the "New code" dialog has no input fields, just
  "We'll create a new code for you." and a "Create code" button. REMOVE custom code input,
  campaign tag, expiry date and usage limit.
- "New link" and "New code" buttons must not wrap.
```

### Conversions (partner)
```
Edit the partner Conversions screen.
- Table columns: Order ID (one line, never wraps; widen the column), Date, Order value,
  Attribution (Last click / First click / Code), Quality, Commission. Remove the "Actions" column;
  the whole row opens the side panel.
- Quality column states: score badge (cobalt outline), "Scoring…" (grey), "Model not trained"
  (grey text). Keep these.
- Side panel: title "Order demo-order-2041", details (Order value, Date, Clicked at, Source,
  Device, Commission earned with rate), then "Referral quality 82/100" with why bars.
  Use these factor labels only: "came from an email", "came from search", "converted 4 hours after
  the click", "order value", "your tier", "your past conversions", "mobile device".
- REMOVE the "Approve payout" and "Export raw event" buttons (partners cannot approve anything),
  the "Verified" badge and the "Audit inspector" label.
```

### Commissions (partner)
```
Edit the partner Commissions screen.
- Ledger strip: Approved (available in wallet), Paid out, Reversed.
  Context lines: "Added to your wallet", "Withdrawn to you", "Refunded or confirmed fraud".
  REMOVE "Transferred to external bank".
- Rename "Export ledger" to "Export CSV" on one line.
- Order ID and money columns in the normal font (not monospace).
```

### Wallet
```
Edit the Wallet screen.
- Ledger strip: Available balance, Pending withdrawals, Total withdrawn.
- "Request withdrawal" dialog: Amount field only, hint "Minimum $10. Requests under $100 are
  approved automatically; larger ones are reviewed by an admin." REMOVE bank account, ACH,
  routing number, payout method and payout schedule.
- Withdrawals table: Requested, Amount, Status (Pending review / Approved / Paid / Rejected),
  Note. Transactions table: Date, Description (Commission for demo-order-2041, Withdrawal,
  Withdrawal refunded, Commission reversed), Amount (+/-), Balance after.
- All numbers in the normal font with tabular figures — no monospace.
```

### Profile
```
Edit the Profile screen.
- Business details card: Full name, Business name, Category, Phone, Email (read-only, small note
  "Contact an admin to change your email"). Button "Save changes".
  REMOVE "Verified entity", "Official verified merchant tax and identity registry", "Primary ID".
- Password card: Current password, New password (placeholder "At least 8 characters" — not
  "passkey"), button "Change password". REMOVE "Entropy: strong" and "Last modified".
- Your tier card: list Bronze / Silver / Gold with "rate · needs N sales and $X revenue" each,
  current tier highlighted, progress bar to the next tier, and
  "Upgrades happen automatically when you reach BOTH targets and apply to future sales."
  REMOVE "locked automatically at month close".
- Account card: Member since, Status (Active pill), Tier. REMOVE Partner ID and Payout cycle.
```

---

## Admin screens

### Admin overview
```
Edit the Admin overview screen.
- Ledger strip with 5 cells that fit without overflow: Revenue referred, Commission paid,
  Pending payouts, Open fraud alerts, Partners at churn risk. Numbers max 28px; the cells must
  never overflow their borders.
- Range switch 7 / 30 / 90 days above the charts.
- Keep: Revenue & commission area chart, Clicks & conversions bar chart, Top partners table
  (Partner, Tier, Conversions, Revenue, Rank score), Recent fraud alerts list with score badges.
- REMOVE model-health/uptime widgets and anything about ledger sync.
```

### Partners
```
Edit the admin Partners screen.
- Toolbar: search, Status filter (All, Active, Suspended), Tier filter, "Export CSV" button.
  REMOVE "Import partners" (there is no import).
- Table: Partner (name + email), Tier, Conversions, Revenue, Rank score, Churn risk, Fraud risk,
  Status, Joined. Joined dates must be in the past (2025–Oct 2026).
- Filter count chips must not overlap the labels; put counts in a separate pill after the label.
- REMOVE region/country flags and ISO badges.
```

### Partner detail
```
Edit the admin Partner detail screen.
- Header: name, email, tier pill, status pill; actions "Change tier", "Suspend partner"
  (destructive, with a confirm dialog) — or "Reactivate" when suspended.
- Ledger strip: Revenue referred, Commission earned, Wallet balance, Conversions, Clicks (30 days).
- Scores row: Rank, Churn risk, Fraud risk, Average referral quality — each with why bars.
  Churn factor labels: "conversions in the last 30 days vs the 30 before", "days since last
  conversion", "clicks in the last 30 days vs the 30 before", "days since last click", "tenure",
  "revenue in the last 90 days".
- Recent conversions table: Order ID never wraps (widen the column or truncate with a tooltip).
- REMOVE "trust score", region/ISO badges and partner ID.
```

### Payouts
```
Edit the Payouts screen.
- The page must fit the content width — no horizontal page scroll. Show ONE dialog at a time.
- Tabs: Pending review, Approved (awaiting payment), Paid, Rejected — each with a count.
- Table: Requested, Partner (name + email), Amount, Wallet balance, Fraud flag (rose pill if
  open), Status, Actions.
- Actions: Pending → "Approve" / "Reject" (reject asks for a reason; the money goes back to the
  partner's wallet). Approved → "Mark as paid" (confirm dialog: "Confirm you've sent $250.00 to
  Priya Nair outside ReferrAI.").
- REMOVE batches, ACH, bank details, "Run payout batch", scheduled payout dates and payment rails.
- Info line under the tabs: "Requests under $100 are approved automatically unless the partner
  has an open fraud alert."
```

### Commissions (admin)
```
Edit the admin Commissions screen.
- Ledger strip: Approved, Paid, Reversed (this month) — REMOVE "AI validation rate".
- Table: Date, Partner, Order ID, Order value, Type (Percentage / Fixed / Tier-based),
  Commission, Status, Action ("Reverse" only on approved or paid rows). Partner names don't wrap.
- Keep the Reverse dialog as it is (reason field, rose "Reverse commission" button). If the
  partner's balance is too low, show the warning INSIDE the dialog as an amber alert —
  not as a separate toast.
- REMOVE the "AI Risk & Validation Engine (Model v4.18)" panel at the bottom and the
  "Fiscal Q4 2026" / "Ledger synchronized" badges.
```

### Record a sale
```
Edit the Record a sale screen.
- Form: Partner (searchable select), Order ID (external reference, e.g. demo-order-2042),
  Order value ($), Referral code (optional), Click ID (optional, under "Advanced").
- Right side: a live preview card "Commission $24.00 at Silver · 12%" and
  "Attribution: last click within 30 days".
- After saving: success toast "Sale recorded. Commission $24.00 credited to Priya Nair." and a
  note that the quality score appears in a few seconds.
- Duplicate order error: "This order ID was already recorded for this partner."
- REMOVE currency picker, tax fields, SKU/line items and "sync to ledger".
```

### Tiers
```
Edit the Tiers screen.
- Fix the "+ + New tier" button: one plus icon, label "New tier".
- Table: Rank, Tier, Needs (e.g. "20 sales and $2,500 revenue"), Commission (12% or $10 per
  sale), Partners, Actions (Edit, Delete — Delete disabled with tooltip when partners are in it).
- Edit dialog is good; keep it. Add the text under the thresholds: "Partners need BOTH targets."
  Commission type options: Percentage of order, Fixed amount per sale.
- REMOVE "Automated progression: Active" and "Evaluated real time on sale" cells from the strip;
  use: Tiers, Partners on top tier, Average commission rate.
- Footer note: "Partners move up automatically when they reach a tier. Upgrades apply to future
  sales only."
```

### Settings
```
Edit the Settings screen. Use exactly these groups, fields and defaults:
- Commission: Commission type (Percentage / Fixed / Tier-based), Default rate 10%,
  Fixed amount $10 (only shown when type is Fixed). REMOVE "fixed floor minimum".
- Wallet: Minimum withdrawal $10, Auto-approve withdrawals under $100.
- Referrals: Attribution model (Last click / First click), Attribution window 30 days.
- Fraud: Alert threshold 70, Rule weight 25 (points added per rule triggered),
  Max clicks per IP per hour 20, Max partners per device 3.
- Churn: Alert threshold 65.
- Ranking weights: Quality 0.4, Churn resistance 0.2, Volume 0.2, Revenue 0.2 — helper text
  "Weights are relative; they don't need to add up to 1." REMOVE the "must total 1.00" error.
- AI: Scoring interval 24 hours (not 6).
- Each group has its own "Save" button and a one-line description. Validation errors appear under
  the field ("Enter a number between 0 and 100").
- REMOVE webhook, API key, SSO, data-residency and notification settings.
```

### AI models
```
Edit the AI models screen.
- Three model rows: Referral quality, Fraud risk, Churn risk. Each shows Status (Trained /
  Not trained), Trained on (date), Training data (e.g. "1,200 synthetic partners"), and
  one accuracy figure: ROC AUC — Quality 0.71, Fraud 0.99, Churn 0.87.
- Feature lists per model (use exactly these):
  Quality: has a click, hours from click to purchase, order value, partner tenure, partner tier,
  partner past conversions, traffic source, device type.
  Fraud: clicks from the same IP in the last hour, partner clicks in the last hour, different IPs
  on the partner in 24h, partners this device clicked in 24h, time since this IP's last click,
  bot user agent, mobile device.
  Churn: conversions last 30 days vs 30 before, clicks last 30 days vs 30 before, days since last
  conversion, days since last click, tenure, tier, revenue last 90 days.
- One primary button "Retrain models" with a confirm dialog ("Takes about a minute. Scoring keeps
  working with the current models.") and a "Run scoring now" secondary button.
- REMOVE version numbers, GPU/inference latency, drift charts, A/B and "deploy to production".
```

### Fraud alerts
```
Edit the Fraud alerts screen.
- Tabs: Pending review, Confirmed, Dismissed.
- Each alert row: Partner, Raised (date), Fraud score badge (rose >70), Why bars, Actions
  "Confirm fraud" (rose) / "Dismiss".
- Why bars use only these labels: "clicks from the same IP in the last hour",
  "partner clicks in the last hour", "different IPs in 24h", "partners this device clicked in 24h",
  "seconds since this IP's last click", "bot user agent".
- Rules triggered appear as small rose pills with these exact texts:
  "too many clicks from one IP in an hour", "same device clicked many different partners",
  "IP already converted for this partner (possible self-referral)".
- Confirm dialog text: "This marks the alert as fraud. The account is not suspended automatically —
  suspend it from the partner page if needed." REMOVE "auto-suspend" and "freeze funds" toggles.
```

### Churn risk
```
Edit the Churn risk screen.
- Ledger strip: Alert threshold (65, link "Change in settings"), Partners above threshold,
  Revenue from them (last 90 days). REMOVE "Intervention window" and "60% retention rate if contacted".
- High-risk table: Partner, Tier, Churn risk badge, Why bars, Last sale, Actions "Email partner"
  (opens the email app) and "Open". Why bar labels only from: "conversions in the last 30 days vs
  the 30 before", "clicks in the last 30 days vs the 30 before", "days since last conversion",
  "days since last click", "tenure", "revenue in the last 90 days".
  REMOVE "unresponsive to promo assets", "extended payout gap", "traffic volume drop".
- Why-bar labels must not overlap the bars — put the label on its own line above each bar.
- "Not enough history yet" table: Partner, Joined, Total sales, and "Day 14 of 30" progress.
  Replace the "Telemetry days" column name with "History". REMOVE the "telemetry buffer" text.
```

### Partner ranking
```
Edit the Partner ranking screen.
- Table: #, Partner, Tier, Rank score, and four component bars: Quality, Churn resistance,
  Volume, Revenue (0–100 each), plus a small note "neutral 50 — no score yet" when a component
  has no data.
- Header note: "Rank = weighted mix of quality 0.4, churn resistance 0.2, volume 0.2,
  revenue 0.2 (change in Settings)."
- REMOVE movement arrows/rank history if they imply data we don't store, and any "league" or
  badge gamification.
```

### Partner discovery
```
Edit the Partner discovery screen.
- The page must fit the width — the candidate table must not run off the right edge.
- Ledger strip: Candidates, New, Invited, Average potential score. REMOVE "Cosine vector affinity",
  "Mean acceptance yield", "Pipeline queue" and the model label in the top bar.
- "Score a candidate" panel: Business name, Category, Description (what they sell and who to).
  REMOVE City & country, Product URL and the CSV upload / template download.
- Candidates table: Business, Category, Potential score badge, Why bars (exactly two:
  "similar to your top partners" and "category fit"), Most similar to (up to 3 partner names),
  Status (New / Reviewed / Invited / Dismissed), Actions (Invite, Mark reviewed, Dismiss).
  REMOVE city/country under the business name.
- Info line: "Candidates are compared with partners who already have sales."
```

### Audit log
```
Edit the Audit log screen.
- REMOVE the whole crypto theme: "cryptographically chained", "Ledger integrity hash",
  "Zero tampering detected", "Block #… verified", "Audit payload signature", "revision_v4.1",
  the footer about SHA-256 and the enclave.
- Ledger strip: Events (24h), By admins, By the system.
- Filters: search (partner, order ID, IP), Action select, Actor select (All, Admins, System),
  date range.
- Table: When, Who (admin email or "System"), Action (plain sentence), IP address, expand chevron.
  Action type pills must not wrap — put the pill on its own line above the sentence if needed.
  System rows show "—" for IP (not "internal-worker-eu-west-1").
- Expanded row: "Before" and "After" columns with setting/field names in plain words
  ("Default commission rate: 10% → 12%"), not code-style keys. Keep the reason/note line.
```

### Page not found (404)
```
Edit the 404 screen. Keep it simple:
- Wordmark "ReferrAI" top-left, nothing else in the header (REMOVE Documentation, Support,
  Sign in, Create account).
- Centre: "404", heading "Page not found", text "This page doesn't exist or you don't have access
  to it.", buttons "Go to dashboard" (primary) and "Sign in" (secondary).
- REMOVE the "Ledger index fault" pill, the diagnostic table, "cryptographic checkpoint",
  "routing identifier", "Contact support desk", and the whole footer (© 2025, Security & compliance,
  Ledger verification, Status).
```
