# -----------------------------------------------------------------------------
# backend/app/core/database.py
#
# Async SQLAlchemy engine, session factory, and the get_db FastAPI dependency.
# Route handlers declare `db: AsyncSession = Depends(get_db)` to receive a
# scoped session that closes automatically after the request. pool_pre_ping=True
# validates connections before use — essential after container restarts.
# expire_on_commit=False keeps ORM attribute values accessible after a commit
# without issuing a new SELECT, which matters in async contexts. Alembic does
# not use this engine; it creates its own via asyncpg in alembic/env.py.
# -----------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if settings.DB_NULL_POOL:
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
