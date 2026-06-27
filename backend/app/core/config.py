# -----------------------------------------------------------------------------
# backend/app/core/config.py
#
# Typed, env-file-aware application configuration via Pydantic Settings. Reads
# .env first, then real environment variables override (Docker sets DATABASE_URL
# directly). All other modules import the module-level `settings` singleton —
# never instantiate Settings() a second time. extra="ignore" silences unrecognized
# env vars injected by Docker. FRAUD_ALERT_THRESHOLD here is the startup default;
# the service layer should prefer the runtime value from the settings DB table.
# Developers: add new config keys here, never hardcode values in service files.
# -----------------------------------------------------------------------------

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/referrai"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    FRAUD_ALERT_THRESHOLD: float = 70.0


settings = Settings()
