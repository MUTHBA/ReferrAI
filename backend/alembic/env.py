# -----------------------------------------------------------------------------
# backend/alembic/env.py
#
# Alembic migration runner — loaded automatically by every `alembic` CLI call.
# Implements a dual-path strategy: async via asyncpg for PostgreSQL (no psycopg2
# needed — avoids C-extension build failures on Python 3.13), and sync SQLite
# for local dev and CI testing. A SQLite type-compiler shim renders JSONB as
# JSON so CREATE TABLE succeeds on both backends. DATABASE_URL env var overrides
# the SQLite default in alembic.ini at runtime (set automatically in Docker).
# Developers: run `alembic upgrade head` from backend/ to apply migrations.
# -----------------------------------------------------------------------------

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Path setup — add backend/ to sys.path so "from app.models import Base" works
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import all models so their tables land on Base.metadata
from app.models import Base  # noqa: E402

# ---------------------------------------------------------------------------
# SQLite compat: render JSONB as JSON for local-dev testing
# ---------------------------------------------------------------------------
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler  # noqa: E402


def _sqlite_visit_JSONB(self, type_, **kw):  # noqa: N802
    return "JSON"


SQLiteTypeCompiler.visit_JSONB = _sqlite_visit_JSONB  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Alembic config
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Allow DATABASE_URL env var to override alembic.ini at runtime
_env_url: str | None = os.environ.get("DATABASE_URL")
if _env_url:
    config.set_main_option("sqlalchemy.url", _env_url)


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def _do_run_migrations(connection) -> None:
    url = connection.engine.url.render_as_string(hide_password=False)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations(url: str) -> None:
    """Used when DATABASE_URL is an asyncpg (PostgreSQL) URL."""
    engine = create_async_engine(url, poolclass=pool.NullPool)
    async with engine.connect() as conn:
        await conn.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")

    if url.startswith("postgresql+asyncpg") or url.startswith("postgresql+aiopg"):
        # Async path: uses asyncpg — no psycopg2 required
        asyncio.run(_run_async_migrations(url))
    else:
        # Sync path: SQLite for local dev/CI
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        with connectable.connect() as connection:
            _do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
