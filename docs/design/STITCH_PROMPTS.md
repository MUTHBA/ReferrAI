# ReferrAI — Google Stitch prompt pack

Seven prompts that cover every screen of the new frontend (23 pages plus a 404). Each prompt designs a group of up to 5 related screens so they share one style. The full style guide is in `docs/design/DESIGN.md`.

## How to use

1. In Stitch, choose **Web** and the higher-quality model (Gemini Pro / "experimental") for the first prompt; standard mode is fine for later ones if you want to save generations.
2. If Stitch offers a theme panel or DESIGN.md import, load `DESIGN.md` (or set: font Schibsted Grotesk, primary #0F6E56, radius 10px). Either way, **every prompt below already repeats the style block** because Stitch does not enforce a style across separate generations.
3. Paste one prompt per new generation, in order. Prompt 1 sets the look — iterate on it with follow-ups (section "Follow-up prompts") until you like it before moving on.
4. For each finished screen, export:
   - **Code → HTML/Tailwind** (the .zip download is easiest), and
   - a **PNG screenshot** of the screen.
5. Put them in a folder per prompt, e.g. `stitch-exports/03-partner-money/wallet.html` + `wallet.png`, and send me the folders (attach here, or drop them in `D:\Projects\ReferrAI\stitch-exports\`). I'll turn them into React + shadcn/ui components, wire them to the real API and keep the data/fields correct — so don't worry if Stitch invents small details.

Fake data in the prompts uses $ amounts and made-up partners; it's only for the mock-ups.

---

## Style block (already included in every prompt)

```
STYLE: ReferrAI, a referral & commission platform. Calm, precise "money ledger" look; numbers are the heroes. Font Schibsted Grotesk everywhere, tabular figures for numbers, sentence case only (no all-caps labels, no eyebrows). Colours: app background #F2F4F1 (cool sage grey), panels #FFFFFF, borders 1px #DDE2DC, text #18222F, secondary text #5E6B78, primary/positive #0F6E56 (jade), AI elements #3557C9 (cobalt), warning #B7791F (amber), danger/fraud #B83A2E (rose). Left sidebar 248px with #18222F background, white text, jade bar on the active item; content max-width 1280px, left aligned, 32px padding. Key figures shown as ONE bordered "ledger strip" split into cells by vertical dividers (label, big tabular number, small context line) — not separate floating cards. Tables: 44px rows, right-aligned money, status pills (jade tint = approved/active/paid, amber tint = pending, rose tint = rejected/reversed/suspended, grey = dismissed). Radius 10px panels, 6px buttons/inputs, no drop shadows except dialogs. Signature element: AI "why" bars — a score badge plus up to 3 horizontal factor bars growing right in jade (raises the score) or left in rose (lowers it) from a centre line, each with a plain-language label and signed value like "+28". No gradients, glassmorphism, neon, illustrations or stock photos. Desktop 1440px wide, also show it works on mobile.
```

---

## Prompt 1 — Sign in and account access (5 screens)

```
STYLE: ReferrAI, a referral & commission platform. Calm, precise "money ledger" look; numbers are the heroes. Font Schibsted Grotesk everywhere, tabular figures for numbers, sentence case only (no all-caps labels, no eyebrows). Colours: app background #F2F4F1 (cool sage grey), panels #FFFFFF, borders 1px #DDE2DC, text #18222F, secondary text #5E6B78, primary/positive #0F6E56 (jade), AI elements #3557C9 (cobalt), warning #B7791F (amber), danger/fraud #B83A2E (rose). Radius 10px panels, 6px buttons/inputs, no drop shadows except dialogs. No gradients, glassmorphism, neon, illustrations or stock photos. Desktop 1440px wide, also works on mobile.

Design 5 connected screens for signing in to ReferrAI. Layout for all auth screens: split screen. Left 45%: #18222F panel with the ReferrAI wordmark top-left and, centred, a typographic "ledger" composition — three rows of a live-looking commission ledger (e.g. "Peak Fitness Coaching · conversion $240.00 · commission +$24.00", "UrbanThreads · conversion $89.50 · +$8.95", "Northwind Travel · payout −$150.00") in white and jade text, with one short line under it: "Track every referral from click to payout." Right 55%: #F2F4F1 background with a centred 400px white form panel.

1. Sign in: title "Sign in", fields Email and Password (with show/hide), "Forgot password?" link right-aligned under the password, primary button "Sign in" full width, below it "New partner? Create an account". Show an inline error state variant above the button: "Email or password is incorrect."
2. Create a partner account: title "Become a partner", short helper "Earn commission on every sale you refer." Fields: Full name, Email, Password (helper: "At least 8 characters"), primary button "Create account", link "Already have an account? Sign in". No role picker.
3. Forgot password: title "Reset your password", one Email field, button "Send reset link", and the success state replacing the form: "If that email is registered, we've sent a reset link." with a "Back to sign in" link.
4. Set a new password: title "Choose a new password", fields New password and Confirm password, button "Save new password", plus an error state "This reset link has expired or was already used — request a new one."
5. Page not found (404), full-width on #F2F4F1: big tabular "404", one line "This page doesn't exist or you don't have access to it.", buttons "Go to dashboard" (primary) and "Sign in" (secondary).
```

---

## Prompt 2 — Partner: dashboard, referral links, conversions (3 screens)

```
STYLE: ReferrAI, a referral & commission platform. Calm, precise "money ledger" look; numbers are the heroes. Font Schibsted Grotesk everywhere, tabular figures for numbers, sentence case only (no all-caps labels, no eyebrows). Colours: app background #F2F4F1, panels #FFFFFF, borders 1px #DDE2DC, text #18222F, secondary text #5E6B78, primary/positive #0F6E56 (jade), AI elements #3557C9 (cobalt), warning #B7791F (amber), danger #B83A2E (rose). Left sidebar 248px with #18222F background, white text, jade bar on the active item; content max-width 1280px, left aligned, 32px padding. Key figures shown as ONE bordered "ledger strip" split into cells by vertical dividers — not separate cards. Tables: 44px rows, right-aligned money, status pills. Radius 10px panels, 6px buttons/inputs, no drop shadows except dialogs. Signature element: AI "why" bars — a score badge plus up to 3 horizontal factor bars growing right in jade (raises the score) or left in rose (lowers it) from a centre line, each with a plain label and signed value. No gradients, glassmorphism, neon, illustrations. Desktop 1440px, also works on mobile.

These are screens for a PARTNER (someone who earns commission). Sidebar items: Dashboard, Referral links, Conversions, Commissions, Wallet, Profile; bottom of sidebar: partner name "Priya Nair", email, "Sign out". Top-right of every page: light/dark toggle.

1. Partner dashboard. Header "Welcome back, Priya" with a 7 / 30 / 90 days segmented control on the right (30 selected).
   - Ledger strip with 5 cells: Total earned $3,482.40 (+$412.00 last 30 days) | Wallet balance $1,126.80 ($150.00 held for a payout) | Conversions 86 | Clicks 1,940 | Conversion rate 4.4%.
   - Large panel "Earnings": area chart of daily commission over 30 days (jade), with clicks as faint bars behind it; tooltip example "12 Oct · $48.20 earned · 3 conversions · 71 clicks".
   - Right column (1/3 width): panel "Your tier": "Silver · 12% commission", progress bar 68% toward "Gold · 15%", line "14 more conversions or $1,850 more revenue to reach Gold". Below it panel "Your standing": "Ranked #3 of 41 partners" and a cobalt score badge "Referral quality 74/100" with why bars: "traffic from search and email +9", "time from click to purchase +6", "orders below your usual value −4". Link "How scores work".
2. Referral links. Header "Referral links" with primary button "New link". Panel "Links": table with columns Link (full URL https://referrai.app/r/qpXppy8n1Gs with a copy icon), Destination (https://peakfitness.com/plans), Clicks 642, Conversions 31, Created 2 Sep 2026, Status pill Active, row actions "Show QR code" and "Copy". Include a dialog variant "New referral link" with a Destination URL field (helper "Must start with https://") and button "Create link", and a QR dialog showing a QR code, the URL and button "Download PNG". Second panel "Referral codes" with button "New code": table Code (TREYZLO1, monospaced is NOT allowed — use the same font, letter-spaced slightly), Uses 12, Created, Status. Empty state text for codes: "Codes let customers credit you at checkout without a link. Create your first code."
3. Conversions. Header "Conversions" with a search box "Search order ID". Table: Order ID (demo-order-2041), Date (18 Oct 2026, 14:32), Order value $240.00, Attribution "Last click", Quality — a cobalt score badge e.g. 82 / 41 / "Scoring…" (grey) / "Model not trained" (grey text). Clicking a row opens a right-side sheet "Order demo-order-2041": order value, date, attributed click time and source "google", device "Mobile", and the quality score 82/100 with why bars: "came from a newsletter +7", "partner tier +5", "purchase 4 hours after the click +4". Pagination at the bottom "Showing 1–20 of 86".
```

---

## Prompt 3 — Partner: commissions, wallet, profile (3 screens)

```
STYLE: ReferrAI, a referral & commission platform. Calm, precise "money ledger" look; numbers are the heroes. Font Schibsted Grotesk everywhere, tabular figures for numbers, sentence case only (no all-caps labels, no eyebrows). Colours: app background #F2F4F1, panels #FFFFFF, borders 1px #DDE2DC, text #18222F, secondary text #5E6B78, primary/positive #0F6E56 (jade), AI elements #3557C9 (cobalt), warning #B7791F (amber), danger #B83A2E (rose). Left sidebar 248px with #18222F background, white text, jade bar on the active item; content max-width 1280px, left aligned, 32px padding. Key figures shown as ONE bordered "ledger strip" split into cells by vertical dividers — not separate cards. Tables: 44px rows, right-aligned money, status pills (jade tint approved/paid, amber tint pending, rose tint rejected/reversed). Radius 10px panels, 6px buttons/inputs, no drop shadows except dialogs. No gradients, glassmorphism, neon, illustrations. Desktop 1440px, also works on mobile.

PARTNER screens. Sidebar items: Dashboard, Referral links, Conversions, Commissions, Wallet, Profile; bottom: "Priya Nair", email, "Sign out".

1. Commissions. Header "Commissions". Ledger strip: Approved $3,301.20 | Paid out $2,174.40 | Reversed $181.20. Filter pills: All, Approved, Paid, Reversed. Table: Date, Order ID, Order value, Rate (12%), Commission (right-aligned, jade +$28.80; reversed rows show the amount struck through in rose with pill "Reversed"), Status pill. Pagination "Showing 1–25 of 86". Empty state: "You'll see a commission here every time a referred customer buys."
2. Wallet. Header "Wallet" with primary button "Withdraw".
   - Ledger strip: Available balance $1,126.80 | Held for pending payouts $150.00 | Total withdrawn $2,174.40 | Lifetime earned $3,482.40.
   - Panel "Request a withdrawal" (inline form, can also be the dialog behind the Withdraw button): Amount field with $ prefix, helper "Minimum $10.00 · amounts under $100.00 are approved instantly", button "Request withdrawal". Show the success toast "Withdrawal of $60.00 approved" and an error "Amount is more than your available balance".
   - Panel "Payout history": table Requested (17 Oct 2026), Amount $150.00, Status pill (Pending review / Approved / Paid / Rejected), Note ("Rejected: bank details missing").
   - Panel "Ledger": every wallet movement — Date, Description ("Commission · order demo-order-2041", "Withdrawal held", "Withdrawal returned", "Commission reversed"), Amount (+$28.80 jade / −$150.00 ink / reversal rose), Balance after.
3. Profile. Header "Profile". Two columns. Left: form panel "Business details" — Full name, Business name, Category (select: Fitness, Fashion, Electronics, Travel, Food, Finance, Beauty, Gaming), Phone, Email (read-only), button "Save changes". Below it panel "Password" with Current password, New password, button "Change password". Right: panel "Your tier": current tier "Silver" pill, "12% commission on every sale", list of all tiers as a vertical step ladder (Bronze 10% · from 0 sales; Silver 12% · 20 sales; Gold 15% · 100 sales or $10,000 revenue) with the current one highlighted in jade and progress to the next. Panel "Account": member since 3 Mar 2026, status pill Active.
```

---

## Prompt 4 — Admin: overview, partners list, partner detail (3 screens)

```
STYLE: ReferrAI, a referral & commission platform. Calm, precise "money ledger" look; numbers are the heroes. Font Schibsted Grotesk everywhere, tabular figures for numbers, sentence case only (no all-caps labels, no eyebrows). Colours: app background #F2F4F1, panels #FFFFFF, borders 1px #DDE2DC, text #18222F, secondary text #5E6B78, primary/positive #0F6E56 (jade), AI elements #3557C9 (cobalt), warning #B7791F (amber), danger/fraud #B83A2E (rose). Left sidebar 248px with #18222F background, white text, jade bar on the active item; content max-width 1280px, left aligned, 32px padding. Key figures shown as ONE bordered "ledger strip" split into cells by vertical dividers — not separate cards. Tables: 44px rows, right-aligned money, status pills. Radius 10px panels, 6px buttons/inputs, no drop shadows except dialogs. Signature element: AI "why" bars — a score badge plus up to 3 horizontal factor bars growing right in jade (raises the score) or left in rose (lowers it) from a centre line, each with a plain label and signed value. Risk score badges: under 40 grey, 40–70 amber, over 70 rose. No gradients, glassmorphism, neon, illustrations. Desktop 1440px, also works on mobile.

ADMIN screens. Sidebar has two groups. "Business": Overview, Partners, Payouts, Commissions, Record a sale, Tiers, Settings. "AI": Models, Fraud alerts (badge 3), Churn risk, Ranking, Discovery. Bottom: "Admin", email, "Sign out". Optional extra item "Audit log".

1. Overview. Header "Overview" with 7 / 30 / 90 days control and a secondary button "Export CSV" (menu: Referrals, Commissions, Partners).
   - Ledger strip with 6 cells: Revenue $84,210.00 (+12% vs previous 30 days) | Commission $9,486.30 | Active partners 41 | Conversion rate 3.8% | Pending payouts 4 · $1,240.00 | Alerts: 3 fraud · 5 churn (rose/amber numbers).
   - Large panel "Revenue and commission": area chart revenue (ink line, light fill) with commission (jade) over 30 days.
   - Panel "Clicks and conversions": bars for clicks, line for conversions.
   - Right column: panel "Needs attention" — a short list: "3 fraud alerts waiting for review" (rose dot, link "Review"), "4 payouts waiting for approval · $1,240.00" (amber, link "Approve"), "5 partners at risk of churning" (amber, link "View"). Panel "Top partners": 5 rows with name, tier pill, revenue, conversions, ranking score badge.
2. Partners. Header "Partners" (count 41). Toolbar: search "Search name, email or business", status filter (All, Active, Suspended, Pending), sort (Ranking, Revenue, Churn risk, Newest). Table: Partner (name + business underneath, e.g. "Priya Nair / Peak Fitness Coaching"), Tier pill, Status pill, Conversions, Revenue, Quality badge, Fraud risk badge, Churn risk badge ("Not enough history" in grey for new partners), Joined date. Row click goes to detail.
3. Partner detail — "Priya Nair". Header with name, business, status pill Active, tier pill Silver, and actions on the right: "Change tier" (select), "Suspend partner" (rose secondary; show its confirmation dialog: "Suspend Priya Nair? She won't earn commission or withdraw until reactivated." buttons "Cancel" / "Suspend partner").
   - Ledger strip: Revenue $28,140.00 | Commission earned $3,482.40 | Wallet balance $1,126.80 | Conversions 86 | Clicks 1,940.
   - Panel "Performance": 90-day earnings area chart.
   - Panel "AI assessment" with three rows, each a score badge + why bars + "Last scored 19 Oct 2026, 09:00": Ranking 81 ("quality 74", "churn resistance 88", "revenue 92"); Churn risk 12 ("clicks this month +4% vs last" lowers, "days since last sale: 1" lowers); Fraud risk 8 (no factors stood out).
   - Panel "Recent conversions" (5 rows) and panel "Payouts" (3 rows).
```

---

## Prompt 5 — Admin: payouts, commissions, record a sale, tiers, settings (5 screens)

```
STYLE: ReferrAI, a referral & commission platform. Calm, precise "money ledger" look; numbers are the heroes. Font Schibsted Grotesk everywhere, tabular figures for numbers, sentence case only (no all-caps labels, no eyebrows). Colours: app background #F2F4F1, panels #FFFFFF, borders 1px #DDE2DC, text #18222F, secondary text #5E6B78, primary/positive #0F6E56 (jade), AI elements #3557C9 (cobalt), warning #B7791F (amber), danger #B83A2E (rose). Left sidebar 248px with #18222F background, white text, jade bar on the active item; content max-width 1280px, left aligned, 32px padding. Tables: 44px rows, right-aligned money, status pills (jade tint approved/active/paid, amber tint pending, rose tint rejected/reversed). Radius 10px panels, 6px buttons/inputs, no drop shadows except dialogs. Dialogs: clear title, one sentence of consequences, matching action button. No gradients, glassmorphism, neon, illustrations. Desktop 1440px, also works on mobile.

ADMIN screens. Sidebar groups — "Business": Overview, Partners, Payouts, Commissions, Record a sale, Tiers, Settings. "AI": Models, Fraud alerts, Churn risk, Ranking, Discovery.

1. Payouts. Header "Payouts". Tabs with counts: Pending review (4), Approved (2), Paid (31), Rejected (3), All. Table: Requested (19 Oct 2026, 10:14), Partner (name + email), Amount, Review reason chip ("Over $100.00", "Fraud alert open" in rose, "24-hour limit reached"), Status pill, actions "Approve" (jade), "Reject" (ghost). Approved tab rows have "Mark as paid". Dialogs: "Approve $250.00 for Priya Nair?" / "Reject this payout? $250.00 goes back to the partner's wallet." with a required Note field / "Mark as paid?" with optional payment reference.
2. Commissions. Header "Commissions". Filter pills All / Approved / Paid / Reversed and a partner search. Table: Date, Partner, Order ID, Order value, Type ("12% of order"), Commission, Status pill, row action "Reverse". Reverse dialog: "Reverse $28.80 commission for Priya Nair? It will be taken back from her wallet. Use this for confirmed fraud or refunds." Reason field, rose button "Reverse commission". Error toast example: "Priya Nair's balance is lower than this commission — it may already have been withdrawn."
3. Record a sale. Header "Record a sale" with helper "Use this to record a sale manually. Your shop can also send sales to the API." Single centred 560px form panel: Partner (searchable select showing name + email), Order ID (helper "Must be unique for this partner — repeats are rejected"), Order value ($ prefix), Referral code (optional), Click ID (optional, under "Advanced"). Button "Record sale". Below it, a result panel showing the success state: "Sale recorded · commission $28.80 credited to Priya Nair · attributed to a click from 18 Oct, 14:02 (last click)", and an error example "This order ID was already recorded for this partner."
4. Tiers. Header "Tiers" with primary button "New tier". Table ordered by rank: Rank 1 Bronze · from 0 sales and $0 revenue · 10% of order · 23 partners; Rank 2 Silver · 20 sales · 12% · 12 partners; Rank 3 Gold · 100 sales or $10,000 · 15% · 6 partners. Row actions Edit, Delete (disabled with tooltip "Move its 23 partners to another tier first"). Edit dialog: Name, Rank, Minimum sales, Minimum revenue, Commission type (Percentage of order / Fixed amount per sale), Rate field that shows "%" or "$" depending on type, inline error "Enter a percentage between 0 and 100". Note under the table: "Partners move up automatically when they reach a tier. Upgrades apply to future sales only."
5. Settings. Header "Settings" with helper "Changes apply immediately and are recorded in the audit log." Sections as panels with a left label column and controls on the right: "Commission" (default type select, default rate %, fixed amount $); "Payouts" (minimum withdrawal $, instant-approval limit $ with helper "Payouts below this, and within this amount per 24 hours, are approved automatically unless the partner has an open fraud alert"); "Attribution" (model radio: First click / Last click with one-line explanations, attribution window in days); "Fraud" (alert threshold slider 0–100 showing 70, points per triggered rule, max clicks per IP per hour, max partners per device per day); "Churn" (alert threshold 65); "Ranking weights" (four number inputs Quality 0.4, Churn 0.2, Volume 0.2, Revenue 0.2 with a live "Total 1.0"); "AI schedule" (recompute churn and ranking every N hours, 0 = off). Each panel has its own "Save" button; show one field in an error state "Must be between 0 and 1".
```

---

## Prompt 6 — Admin AI: models, fraud alerts, churn risk (3 screens)

```
STYLE: ReferrAI, a referral & commission platform. Calm, precise "money ledger" look; numbers are the heroes. Font Schibsted Grotesk everywhere, tabular figures for numbers, sentence case only (no all-caps labels, no eyebrows). Colours: app background #F2F4F1, panels #FFFFFF, borders 1px #DDE2DC, text #18222F, secondary text #5E6B78, primary/positive #0F6E56 (jade), AI elements #3557C9 (cobalt), warning #B7791F (amber), danger/fraud #B83A2E (rose). Left sidebar 248px with #18222F background, white text, jade bar on the active item; content max-width 1280px, left aligned, 32px padding. Tables: 44px rows, status pills. Radius 10px panels, 6px buttons/inputs, no drop shadows except dialogs. Signature element (make it prominent on these screens): AI "why" bars — a score badge plus up to 3 horizontal factor bars growing right in jade (raises the score) or left in rose (lowers it) from a centre line, each with a plain-language label and signed value like "+28". Risk badges: under 40 grey, 40–70 amber, over 70 rose. No gradients, glowing "AI" effects, sparkles, robots, neon or illustrations — AI is presented as a calm explainer. Desktop 1440px, also works on mobile.

ADMIN screens, "AI" section. Sidebar groups — "Business": Overview, Partners, Payouts, Commissions, Record a sale, Tiers, Settings. "AI": Models, Fraud alerts (badge 3), Churn risk, Ranking, Discovery.

1. Models. Header "AI models" with primary button "Retrain models" and secondary "Run churn and ranking now". Line under the header: "Scores refresh automatically every 24 hours · next run 20 Oct 2026, 09:00".
   - Three model panels side by side (Referral quality, Fraud risk, Churn risk). Each: status pill "Trained" (jade) or "Not trained" (grey), version "fraud-20261019130654", trained "19 Oct 2026, 13:06", algorithm ("Gradient boosting" / "Isolation forest + calibration" / "Gradient boosting"), training rows ("13,396 clicks"), and a small metrics table: "Accuracy (ROC AUC) 0.99", "Precision at alert threshold 95%", "Recall at alert threshold 60%", each with a one-line plain explanation on hover. Expandable "Inputs" list of feature names in plain words.
   - Show the training-in-progress state: the Retrain button becomes "Training… 0:12" with a thin progress line across the top of the page, and a success toast "Models retrained · fraud accuracy 0.99".
   - Panel "Training data": "Models learn from a simulated network of 300 partners (fraud rings, churning partners, varying quality) plus your fraud-alert decisions." with secondary button "Generate demo data" and a dialog with fields Partners 20, Clicks per partner 15, Sales 30, Fraud share 25%, Churn share 30%.
2. Fraud alerts. Header "Fraud alerts" with tabs Pending review (3), Confirmed, Dismissed, All. Each alert is a wide row/panel (not a tiny table cell): left — partner name "Rahul Verma / QuickDeals Hub", raised "19 Oct 2026, 11:42", fraud risk badge 97 (rose); middle — why bars: "clicks from the same IP in the last hour +28", "partner's clicks in the last hour +20", "automated (bot) user agent +18"; under them rule chips in rose outline: "Too many clicks from one IP in an hour", "Same device clicked many partners"; right — buttons "Confirm fraud" (rose) and "Dismiss" (secondary), and a quiet link "Open partner". Note at the top: "Alerts never suspend anyone automatically — you decide." Confirm dialog: "Confirm fraud for Rahul Verma? This records your decision and blocks instant payouts while alerts are open. You can then reverse commissions or suspend the partner." Empty state: "No alerts waiting. New ones appear here when traffic looks automated or suspicious."
3. Churn risk. Header "Churn risk" with helper "Partners likely to stop referring in the next 30 days." Toolbar: threshold display "Showing partners above 65" (link "Change in settings"). Table/rows: Partner, Tier, Churn risk badge (rose 92, amber 68), why bars ("clicks in the last 30 days −82% vs before +18", "days since last sale: 41 +12", "revenue in the last 90 days +6"), Last sale date, Action "Email partner" (secondary) and "Open". A second muted section "Not enough history yet" listing new partners (joined under 30 days ago) with grey text instead of a score.
```

---

## Prompt 7 — Admin AI: ranking, discovery, audit log (3 screens)

```
STYLE: ReferrAI, a referral & commission platform. Calm, precise "money ledger" look; numbers are the heroes. Font Schibsted Grotesk everywhere, tabular figures for numbers, sentence case only (no all-caps labels, no eyebrows). Colours: app background #F2F4F1, panels #FFFFFF, borders 1px #DDE2DC, text #18222F, secondary text #5E6B78, primary/positive #0F6E56 (jade), AI elements #3557C9 (cobalt), warning #B7791F (amber), danger #B83A2E (rose). Left sidebar 248px with #18222F background, white text, jade bar on the active item; content max-width 1280px, left aligned, 32px padding. Tables: 44px rows, status pills. Radius 10px panels, 6px buttons/inputs, no drop shadows except dialogs. Signature element: AI "why" bars — a score badge plus horizontal factor bars from a centre line, jade for raises, rose for lowers, each with a plain label and signed value. No gradients, glowing AI effects, sparkles, neon or illustrations. Desktop 1440px, also works on mobile.

ADMIN screens. Sidebar groups — "Business": Overview, Partners, Payouts, Commissions, Record a sale, Tiers, Settings. "AI": Models, Fraud alerts, Churn risk, Ranking, Discovery. Extra item at the bottom of the nav: "Audit log".

1. Ranking. Header "Partner ranking" with secondary button "Recalculate now" and a line "Weights: quality 40% · churn resistance 20% · volume 20% · revenue 20% (change in settings)". A leaderboard table: Rank (1, 2, 3… — this IS a sequence, so numbers are appropriate), Partner, Tier pill, Ranking score (large tabular number + cobalt badge), and a compact stacked horizontal bar per row showing the four weighted parts (quality, churn resistance, volume, revenue) in four tints of jade/cobalt with a legend above the table. Rows with "neutral 50" components show a small grey note "No quality scores yet — counted as 50". Top 3 rows slightly emphasised with a jade left border only.
2. Discovery. Header "Partner discovery" with helper "Find businesses that look like your best partners." Panel "Score new candidates": drag-and-drop area for a CSV ("business_name, category, description, city, country"), link "Download template", or a small inline form to add one candidate; button "Score candidates". Results table sorted by potential: Business (name + city, country), Category, Potential score (cobalt badge 86), why bars ("similar to your top partners +60", "category earns 42% of revenue +26"), "Most similar to: Peak Fitness Coaching, Summit Yoga", Status pill (New / Reviewed / Invited / Dismissed), actions "Invite", "Mark reviewed", "Dismiss". Note for the empty/no-reference case: "Discovery compares candidates with partners who have revenue. Record a few sales first."
3. Audit log. Header "Audit log" with filters: action type (Settings changed, Payout approved, Payout rejected, Payout paid, Fraud confirmed, Fraud dismissed, Partner suspended, Tier changed, Commission reversed, Model training started), person, date range. Table: When (19 Oct 2026, 13:21:08), Who ("admin@referrai.com" or "System" in muted text), Action (plain sentence: "Changed default commission rate from 10% to 12%", "Approved payout of $250.00 for Priya Nair", "Upgraded Priya Nair to Silver (automatic)"), IP address, expandable row showing the before/after values as a two-column diff (old in rose tint, new in jade tint). Pagination.
```

---

## Follow-up prompts (use inside a generation to refine)

- `Make it denser: reduce vertical padding by 25%, keep 44px table rows.`
- `Show this screen in dark mode: background #111A22, panels #18232D, borders #2A3742, text #E6ECEF; keep accent hues but lighten them slightly.`
- `Show the mobile version at 390px wide: sidebar becomes a top bar with a menu button that opens a sheet; ledger strip cells stack 2 per row; tables become stacked rows.`
- `Show the loading state with skeleton rows and the empty state for this screen.`
- `The why bars are too subtle — make them the most prominent element in each row, 8px tall, labels on the left.`
- `Remove any all-caps labels, gradients and decorative icons that don't carry information.`

## What to send back

For each screen: the exported HTML/Tailwind file (or the .zip) and a PNG screenshot, in folders named like the prompts (`01-auth`, `02-partner-home`, `03-partner-money`, `04-admin-overview`, `05-admin-business`, `06-admin-ai`, `07-admin-ai-more`). You can send them one prompt at a time — I'll build each group as it arrives.
