import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# SQLite compatibility shim: render JSONB as JSON so the migration can be
# applied to a local SQLite DB for testing.  Has no effect on PostgreSQL.
# ---------------------------------------------------------------------------
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler  # noqa: E402


def _sqlite_visit_JSONB(self, type_, **kw):  # noqa: N802
    return "JSON"


SQLiteTypeCompiler.visit_JSONB = _sqlite_visit_JSONB  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Path setup — make "backend/" importable as the root package directory so
# that "from app.models import Base" works regardless of CWD.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import all models so their tables are registered on Base.metadata.
from app.models import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to alembic.ini values.
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Allow DATABASE_URL env var to override the alembic.ini URL at runtime.
# Async driver prefixes are converted to their sync equivalents because
# Alembic uses plain SQLAlchemy (sync) connections for migrations.
# ---------------------------------------------------------------------------
_env_url = os.environ.get("DATABASE_URL")
if _env_url:
    _env_url = (
        _env_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        .replace("postgresql+aiopg://", "postgresql+psycopg2://")
    )
    config.set_main_option("sqlalchemy.url", _env_url)


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without a live DB connection."""
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
    """Run migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    url = config.get_main_option("sqlalchemy.url", "")
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
