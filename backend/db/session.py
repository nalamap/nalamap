"""Database engine and session configuration for ORM models."""

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.config import DATABASE_URL
from db.base import Base


def _make_async_url(url: str) -> Optional[str]:
    """Convert a DB URL to the async driver form.

    Returns None if the URL scheme is not supported for async operations.
    """
    # Handle PostGIS (postgis://) and PostgreSQL (postgresql://) schemes
    if url.startswith("postgis://"):
        return url.replace("postgis://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    # SQLite async requires aiosqlite driver
    if url.startswith("sqlite"):
        # Skip SQLite for now - async SQLite requires aiosqlite package
        # Return None to disable database features
        return None
    return url


# AsyncEngine using psycopg v3 driver; session factory bound to it if URL is provided
engine: Optional[AsyncEngine] = None
AsyncSessionLocal = None

if DATABASE_URL:
    ASYNC_DATABASE_URL = _make_async_url(DATABASE_URL)
    if ASYNC_DATABASE_URL:
        engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
        AsyncSessionLocal = sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )


async def init_db() -> None:
    """Initialize the database by creating all tables defined on Base metadata."""
    if engine is None:
        return
    async with engine.begin() as conn:
        # run_sync executes a synchronous callable in the async engine
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async generator yielding a database session for dependency injection."""
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Database session factory is not configured; set DATABASE_AZURE_URL first."
        )
    async with AsyncSessionLocal() as session:
        yield session
