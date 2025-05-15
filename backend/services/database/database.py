import psycopg
from psycopg_pool import AsyncConnectionPool
from fastapi import FastAPI

from core.config import DATABASE_URL

# Initialize connection pool as None
db_pool = None

async def init_db():
    """Initialize the async database pool."""
    global db_pool
    if db_pool is None:  # Ensure we only initialize once
        db_pool = AsyncConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10)
        await db_pool.open()  # Ensure the pool is open

async def close_db():
    """Close the async database pool."""
    global db_pool
    if db_pool:
        await db_pool.close()

# Dependency function for FastAPI
async def get_db():
    """Provide an async database connection."""
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized!")
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            yield cur
