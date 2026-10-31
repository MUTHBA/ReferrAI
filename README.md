# ReferrAI

Referral and commission platform with an AI layer. Partners share links and codes, earn commission on the sales they refer, and withdraw from a wallet. Admins approve payouts, review fraud alerts and use AI scores (referral quality, fraud risk, churn risk, ranking, partner discovery) to manage the network.

- **Backend:** FastAPI, async SQLAlchemy, PostgreSQL, Alembic, scikit-learn + SHAP
- **Frontend:** React 18, Vite, Tailwind CSS v4, shadcn-style components, TanStack Query, Recharts
- **Design:** `docs/design/DESIGN.md` (Stitch prompts and exports live next to it)

## Run it with Docker

```bash
cp .env.example .env              # set SECRET_KEY etc.
docker compose up --build         # db, backend (migrates + trains models on first start), frontend, nginx
```

Open http://localhost. The API docs are at http://localhost/docs.

### Demo data

On an empty database, load six months of realistic activity (12 partners, clicks, sales, commissions, tier upgrades, payouts in every state, AI scores and discovery candidates):

```bash
docker compose exec backend python -m scripts.demo_history
```

| Role | Email | Password |
|---|---|---|
| Admin | admin@referrai.io | Admin123! |
| Partner | priya@demo.referrai.io (also marcus@, elena@, kiran@, …) | Partner123! |

To start again: `docker compose down -v && docker compose up --build`, then run the script again.

To create an admin without demo data: `docker compose exec backend python -m scripts.create_admin --email you@example.com --password '...'`.

Password reset emails aren't sent; the reset link is printed in the backend log (`docker compose logs backend | grep "password reset"`).

## Run it without Docker

```bash
# backend (PostgreSQL running locally)
cd backend && pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5432/referrai
alembic upgrade head
python -m app.ai.train --if-missing
python -m scripts.demo_history          # optional
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend && npm install
VITE_PROXY_TARGET=http://localhost:8000 npm run dev    # http://localhost:3000
```

## Checks

```bash
PYTHONPATH=backend pytest            # needs an empty PostgreSQL database, see CLAUDE.md
cd frontend && npm run lint && npm run build
```

## Where things are

```
backend/app/api/v1/routes/   HTTP endpoints, one file per area
backend/app/services/        business rules (commission, wallet, attribution, tiers, AI jobs)
backend/app/ai/              features, training, model registry, explanations
backend/scripts/             create_admin, demo_history
frontend/src/features/       pages: auth/, partner/, admin/
frontend/src/components/     ui/ (buttons, tables, dialogs…) and app/ (shell, ledger strip, charts, why bars)
frontend/src/lib/            API client, endpoints, formatting
```
