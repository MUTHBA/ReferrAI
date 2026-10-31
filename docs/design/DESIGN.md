# ReferrAI design brief

ReferrAI is a referral and commission platform. Partners (influencers, small businesses, affiliates) share links and codes, earn commission on sales they refer, and withdraw money. Admins approve payouts, review fraud alerts, and use AI scores (referral quality, fraud risk, churn risk, partner ranking) to manage the partner network. Desktop-first web app, must also work on mobile.

## Personality

A precise money ledger with a quiet intelligence layer. Calm, trustworthy, information-dense, never flashy. The interface should feel like a well-kept accounts book: numbers are the heroes, aligned and easy to compare. AI is presented as an explainer, never as magic.

## The one signature element: "why" bars

Every AI score (0–100) is shown with a short horizontal **factor bar**: up to three labelled bars growing left (lowers the score, rose red) or right (raises the score, jade green) from a centre line, with a plain-language label such as "clicks from the same IP in the last hour  +28". This appears in fraud alerts, churn risk, referral quality and ranking. Everything else stays quiet so this stands out.

## Colour tokens

| Token | Hex | Use |
|---|---|---|
| ink | #18222F | primary text, sidebar background |
| canvas | #F2F4F1 | app background (cool sage grey, not cream) |
| surface | #FFFFFF | panels, tables, dialogs |
| line | #DDE2DC | 1px borders and dividers |
| jade | #0F6E56 | primary actions, positive money, "raises" bars |
| cobalt | #3557C9 | AI elements: score badges, explanation links, model status |
| amber | #B7791F | warnings, pending states |
| rose | #B83A2E | fraud, errors, destructive actions, "lowers" bars |
| muted | #5E6B78 | secondary text |

Dark mode: canvas #111A22, surface #18232D, line #2A3742, ink text #E6ECEF; accents keep their hue, lightened ~15%.

## Typography

- One family: **Schibsted Grotesk** (Google Fonts) for everything.
- Numbers use **tabular figures** so columns of money line up.
- Scale: 28/36 page title (600), 20/28 section title (600), 15/22 body (400), 13/18 secondary and table text (400), 32/38 key figures (600, tabular).
- Sentence case everywhere. No all-caps labels, no letter-spaced eyebrows above headings.

## Layout

- Left sidebar 248px (ink background, white text, jade indicator on the active item); content area max width 1280px, left aligned, 32px padding (16px on mobile; the sidebar becomes a top bar with a menu sheet).
- Page header: title on the left, primary action button on the right, one line of muted helper text under the title only when it adds information.
- **Key figures are a single "ledger strip"**: one bordered band split into 4–6 cells by vertical dividers (label above, large tabular number below, small delta or context line). Not separate floating cards.
- Tables are the main content form: 44px rows, right-aligned money columns, status pills, row hover tint, sticky header, pagination at the bottom.
- Charts sit in plain bordered panels: area chart for money over time (jade fill 12% opacity), bars for counts, thin gridlines, legend above the chart.
- Radius: 10px panels and dialogs, 6px inputs and buttons, full pill for status chips. No drop shadows except dialogs and menus.
- Spacing scale 4/8/12/16/24/32/48.

## Components

- Buttons: primary jade filled; secondary white with line border; destructive rose; ghost for table row actions. Labels say exactly what happens ("Approve payout", not "Submit").
- Status pills: approved/active/paid = jade tint, pending/pending review = amber tint, rejected/reversed/suspended/confirmed fraud = rose tint, dismissed/inactive = grey.
- Score badge: number in cobalt-outlined pill; risk scores (fraud, churn) colour by risk: under 40 grey, 40–70 amber, over 70 rose. "Not trained yet" and "Not enough history" shown as grey text, never as 0.
- Empty states: one sentence saying what will appear here plus the action that creates it.
- Toasts bottom-right; dialogs centred with a clear title, consequences in one sentence, and a matching action button.

## Writing

Plain, specific, sentence case. Name things by what users understand: "Payouts", "Fraud alerts", "Churn risk". Money shown as $1,240.50. Dates as "19 Oct 2026". Errors say what happened and how to fix it.

## Avoid

Gradient washes, glassmorphism, neon, mascots, stock illustrations, identical card grids for everything, all-caps labels, monospace labels, arrows appended to link text, purple-to-blue gradients.
