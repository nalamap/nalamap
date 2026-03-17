"""Database engine and session configuration for ORM models."""

import asyncio
import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

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

# Track whether tables have been successfully created
_tables_created = False


async def init_db(max_retries: int = 5, retry_delay: float = 3.0) -> None:
    """Initialize the database by creating all tables defined on Base metadata.

    Retries on connection failure to handle cases where the database container
    starts after the backend (e.g. scale-from-zero in Azure Container Apps).
    """
    global _tables_created
    if engine is None:
        return

    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            _tables_created = True
            logger.info("Database tables initialized successfully")
            return
        except Exception as exc:
            if attempt < max_retries:
                logger.warning(
                    "Database init attempt %d/%d failed (%s), "
                    "retrying in %.0fs...",
                    attempt,
                    max_retries,
                    exc,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error(
                    "Database init failed after %d attempts: %s",
                    max_retries,
                    exc,
                )


async def ensure_tables() -> None:
    """Ensure tables exist, creating them if needed.

    Called lazily on first DB access when startup init_db failed or was skipped
    (e.g. the database container was not yet ready).
    """
    global _tables_created
    if _tables_created or engine is None:
        return
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        _tables_created = True
        logger.info("Database tables created on first access")
    except Exception as exc:
        logger.error("Failed to create database tables on demand: %s", exc)
        raise


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async generator yielding a database session for dependency injection."""
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Database session factory is not configured; set DATABASE_AZURE_URL first."
        )
    await ensure_tables()
    async with AsyncSessionLocal() as session:
        yield session
