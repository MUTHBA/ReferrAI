# -----------------------------------------------------------------------------
# backend/app/main.py
#
# FastAPI application entry point (`uvicorn app.main:app`). Wires CORS (origins
# from settings.CORS_ORIGINS), mounts every v1 router under /api/v1 plus the
# public /r/{slug} redirect, and exposes /health for Docker health checks.
#
# The lifespan hook runs on startup:
#   * optionally bootstraps an admin from BOOTSTRAP_ADMIN_EMAIL/PASSWORD;
#   * loads trained AI models into memory and starts the batch-scoring
#     scheduler (see app/ai/registry.py and app/services/scheduler.py).
# Swagger UI: /api/docs; OpenAPI JSON: /api/openapi.json.
# -----------------------------------------------------------------------------

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import admin as admin_routes
from app.api.v1.routes import ai_scores as ai_scores_routes
from app.api.v1.routes import auth as auth_routes
from app.api.v1.routes import commissions as commission_routes
from app.api.v1.routes import dashboard as dashboard_routes
from app.api.v1.routes import fraud as fraud_routes
from app.api.v1.routes import audit_logs as audit_log_routes
from app.api.v1.routes import partners as partner_routes
from app.api.v1.routes import referrals as referral_routes
from app.api.v1.routes import settings as settings_routes
from app.api.v1.routes import wallet as wallet_routes
from app.core.config import settings

logger = logging.getLogger(__name__)


async def _bootstrap_admin() -> None:
    if not (settings.BOOTSTRAP_ADMIN_EMAIL and settings.BOOTSTRAP_ADMIN_PASSWORD):
        return
    from app.core.database import AsyncSessionLocal
    from app.services.auth_service import AuthService, EmailAlreadyRegisteredError

    try:
        async with AsyncSessionLocal() as session:
            await AuthService(session).create_admin(
                settings.BOOTSTRAP_ADMIN_EMAIL, settings.BOOTSTRAP_ADMIN_PASSWORD
            )
        logger.info("Bootstrapped admin %s", settings.BOOTSTRAP_ADMIN_EMAIL)
    except EmailAlreadyRegisteredError:
        pass
    except Exception:  # DB not migrated yet, etc. — never block startup.
        logger.exception("Admin bootstrap failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await _bootstrap_admin()
    from app.ai import registry
    from app.services import scheduler

    registry.load_all()
    if settings.ENABLE_SCHEDULER:
        scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(
    title="ReferrAI",
    description="Referral & commission management platform with integrated AI",
    version="0.2.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (
    auth_routes,
    admin_routes,
    ai_scores_routes,
    settings_routes,
    referral_routes,
    wallet_routes,
    commission_routes,
    partner_routes,
    dashboard_routes,
    fraud_routes,
    audit_log_routes,
):
    app.include_router(module.router, prefix="/api/v1")
app.include_router(referral_routes.redirect_router)  # public /r/{slug} — no /api/v1 prefix


@app.get("/health", tags=["ops"])
async def health() -> dict:
    from app.ai import registry

    return {"status": "ok", "models_loaded": {m["name"]: m["trained"] for m in registry.describe()}}
