"""Database engine and session configuration for ORM models."""

import asyncio
import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from core.config import DATABASE_URL
from db.base import Base

logger = logging.getLogger(__name__)


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
    max_attempts = 15
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                # run_sync executes a synchronous callable in the async engine
                await conn.run_sync(Base.metadata.create_all)
            return
        except OperationalError as exc:
            if attempt >= max_attempts:
                raise
            logger.warning(
                "Database not ready (attempt %s/%s): %s",
                attempt,
                max_attempts,
                exc,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 5.0)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async generator yielding a database session for dependency injection."""
    if AsyncSessionLocal is None:
        raise RuntimeError(
            """
            Database session factory is not configured;
            set DATABASE_URL and ensure PostgreSQL is running 
            (e.g. docker compose -f db/docker-compose.yml up -d).
            """
        )
    async with AsyncSessionLocal() as session:
        yield session
