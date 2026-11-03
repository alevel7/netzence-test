from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import logger

engine: Optional[AsyncEngine] = None
async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """Returns singleton async database engine, initializing it if needed."""
    global engine, async_session_factory
    if engine is None:
        engine = create_async_engine(
            settings.async_database_url,
            echo=settings.DEBUG,
            future=True,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=True,  # Detect and handle stale/dropped connections
        )
        async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns the async session factory."""
    if async_session_factory is None:
        get_engine()
    assert async_session_factory is not None
    return async_session_factory


async def init_db() -> None:
    """Initializes the database connection pool on application startup."""
    logger.info("Initializing database connection pool...")
    get_engine()
    try:
        is_healthy = await check_database_health()
        if is_healthy:
            logger.info("Database connection successfully established.")
        else:
            logger.warning("Database connection check failed during startup.")
    except Exception as exc:
        logger.error(f"Failed to connect to database on startup: {exc}")


async def close_db() -> None:
    """Disposes database connection pool on application shutdown."""
    global engine, async_session_factory
    if engine is not None:
        logger.info("Closing database connection pool...")
        await engine.dispose()
        engine = None
        async_session_factory = None
        logger.info("Database connection pool closed.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an asynchronous database session per request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> bool:
    """Executes a simple SELECT 1 query to verify database connectivity."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")
        return False

