"""Database connection and asyncpg connection pool manager."""

import logging
from typing import AsyncGenerator, Optional
import asyncpg
from app.config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool instance
db_pool: Optional[asyncpg.Pool] = None


async def init_db() -> asyncpg.Pool:
    """Initialize the asyncpg connection pool using application settings."""
    global db_pool
    if db_pool is not None:
        return db_pool

    settings = get_settings()
    logger.info(
        "Initializing database connection pool (database: %s, host: %s, port: %s)",
        settings.pg_database,
        settings.pg_host,
        settings.pg_port,
    )

    try:
        db_pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
            timeout=5.0,
        )
    except Exception as exc:
        logger.warning(
            "Failed connecting via database_url (%s), attempting discrete parameters...",
            exc,
        )
        db_pool = await asyncpg.create_pool(
            host=settings.pg_host,
            port=settings.pg_port,
            user=settings.pg_user,
            password=settings.pg_password,
            database=settings.pg_database,
            min_size=2,
            max_size=10,
            command_timeout=60,
            timeout=5.0,
        )

    logger.info("Database connection pool initialized successfully.")
    return db_pool


def get_pool() -> Optional[asyncpg.Pool]:
    """Get the active asyncpg connection pool if initialized."""
    return db_pool


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency to acquire a connection from the pool and return it after use."""
    global db_pool
    if db_pool is None:
        try:
            await init_db()
        except Exception as exc:
            # Raise a proper HTTP error (with CORS headers) instead of crashing,
            # so the browser shows the real reason rather than "Failed to fetch".
            from fastapi import HTTPException

            raise HTTPException(
                status_code=503,
                detail=f"Database unavailable: {exc}. Run 'python setup_db.py' in the backend folder.",
            )

    assert db_pool is not None, "Database pool failed to initialize"
    async with db_pool.acquire() as connection:
        yield connection


async def close_db() -> None:
    """Close all connections in the database connection pool."""
    global db_pool
    if db_pool is not None:
        logger.info("Closing database connection pool...")
        await db_pool.close()
        db_pool = None
        logger.info("Database connection pool closed.")
