# -----------------------------------------------------------------------------
# backend/app/main.py
#
# FastAPI application entry point — imported by uvicorn as `app.main:app`.
# Wires global middleware (CORS allows the Vite dev server and nginx) and mounts
# the ops health endpoint used by Docker health checks. Swagger UI is available
# at /api/docs; OpenAPI JSON at /api/openapi.json.
# Added in COM-001/WAL-001: wallet_routes wired for wallet balance, transaction
# history, and withdrawal request/review endpoints. Added in PRT-001/PRT-002:
# partner_routes wired for partner profile and tier CRUD. Added in RPT-001/002/003:
# dashboard_routes wired for admin/partner KPI dashboards and CSV exports.
# Developers: add new v1 routers with `app.include_router(router, prefix="/api/v1")`.
# -----------------------------------------------------------------------------

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import auth as auth_routes
from app.api.v1.routes import dashboard as dashboard_routes
from app.api.v1.routes import partners as partner_routes
from app.api.v1.routes import referrals as referral_routes
from app.api.v1.routes import settings as settings_routes
from app.api.v1.routes import wallet as wallet_routes

app = FastAPI(
    title="ReferrAI",
    description="Referral & commission management platform with integrated AI",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_routes.router, prefix="/api/v1")
app.include_router(settings_routes.router, prefix="/api/v1")
app.include_router(referral_routes.router, prefix="/api/v1")
app.include_router(referral_routes.redirect_router)  # public /r/{slug} — no /api/v1 prefix
app.include_router(wallet_routes.router, prefix="/api/v1")
app.include_router(partner_routes.router, prefix="/api/v1")
app.include_router(dashboard_routes.router, prefix="/api/v1")


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}
