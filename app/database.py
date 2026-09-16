"""Async SQLAlchemy setup — engine, session factory, get_db dependency."""

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# The engine — one for the whole app's lifetime.
engine = create_async_engine(
    settings.db_url,
    echo=False,  # set True to see every SQL statement (Module 06 demo)
    pool_pre_ping=True,  # checks connection liveness before use
)

# Session factory — call it to get a fresh session.
async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,  # keeps objects usable after commit (FastAPI-friendly)
)


async def close_db() -> None:
    """Dispose engine on shutdown."""
    await engine.dispose()

async def get_db():
    async with async_session() as session:
        yield session