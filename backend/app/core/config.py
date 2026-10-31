# -----------------------------------------------------------------------------
# backend/app/core/config.py
#
# Typed, env-file-aware application configuration via Pydantic Settings. Reads
# .env first, then real environment variables override (Docker sets DATABASE_URL
# directly). All other modules import the module-level `settings` singleton —
# never instantiate Settings() a second time. extra="ignore" silences unrecognized
# env vars injected by Docker. Business thresholds (commission, fraud, churn,
# withdrawal limits) are NOT here — they live in the `settings` table, see
# app/core/setting_definitions.py. Only deployment/infrastructure config
# belongs in this file. The app refuses to start in production with the
# default SECRET_KEY.
# -----------------------------------------------------------------------------

import pathlib

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/referrai"
    # Disable connection pooling (used by the test suite, where every test
    # runs in its own event loop and pooled asyncpg connections can't be shared).
    DB_NULL_POOL: bool = False
    SECRET_KEY: str = _INSECURE_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 15
    # "development" | "production" | "test"
    ENV: str = "development"
    # Comma-separated list of allowed browser origins for CORS.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:80,http://localhost"
    # Directory that holds trained model artifacts (*.joblib + *.meta.json).
    # Defaults to backend/models; Docker sets /models (a named volume).
    AI_MODEL_DIR: str = str(pathlib.Path(__file__).resolve().parents[2] / "models")
    # Start the in-process scheduler that recomputes churn/ranking scores.
    ENABLE_SCHEDULER: bool = True
    # Optional: create this admin on startup if it doesn't exist (demo/dev).
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""

    @model_validator(mode="after")
    def _refuse_insecure_secret_in_production(self) -> "Settings":
        if self.ENV == "production" and self.SECRET_KEY == _INSECURE_SECRET:
            raise ValueError("SECRET_KEY must be set to a strong value when ENV=production")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
