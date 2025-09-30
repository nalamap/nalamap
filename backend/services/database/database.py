import logging

from core.config import DATABASE_URL

# Try to import psycopg_pool, handle missing dependency gracefully
try:
    from psycopg_pool import AsyncConnectionPool
    PSYCOPG_AVAILABLE = True
except ImportError:
    AsyncConnectionPool = None
    PSYCOPG_AVAILABLE = False

# Initialize connection pool as None
db_pool = None
# Track if database initialization failed
db_initialization_failed = False

logger = logging.getLogger(__name__)


async def init_db():
    """Initialize the async database pool."""
    global db_pool, db_initialization_failed
    if db_pool is None and not db_initialization_failed:  # Ensure we only initialize once
        try:
            if not PSYCOPG_AVAILABLE:
                logger.warning(
                    "psycopg_pool is not available. Database features will be unavailable. "
                    "Install psycopg[pool] to enable database functionality."
                )
                db_initialization_failed = True
                return
                
            if not DATABASE_URL:
                logger.warning(
                    "DATABASE_AZURE_URL environment variable is not set. "
                    "Database features will be unavailable."
                )
                db_initialization_failed = True
                return
            
            # Type guard to ensure AsyncConnectionPool is available
            if AsyncConnectionPool is None:
                raise RuntimeError("AsyncConnectionPool is not available")
                
            db_pool = AsyncConnectionPool(conninfo=DATABASE_URL, min_size=1, max_size=10)
            await db_pool.open()  # Ensure the pool is open
            logger.info("Database connection pool initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            db_initialization_failed = True
            db_pool = None


async def close_db():
    """Close the async database pool."""
    global db_pool
    if db_pool:
        await db_pool.close()
        db_pool = None


# Dependency function for FastAPI
async def get_db():
    """Provide an async database connection."""
    global db_initialization_failed
    if db_initialization_failed:
        raise RuntimeError(
            "Database is not available. Please check your DATABASE_AZURE_URL environment variable "
            "and ensure the database server is accessible."
        )
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized!")
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            yield cur


def is_database_available() -> bool:
    """Check if the database is available for use."""
    return db_pool is not None and not db_initialization_failed
