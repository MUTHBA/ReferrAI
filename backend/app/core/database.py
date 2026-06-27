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

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
