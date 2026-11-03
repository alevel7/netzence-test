import json
from collections.abc import AsyncGenerator
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings
from app.core.logging import logger

redis_pool: Optional[ConnectionPool] = None
redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Returns the singleton Redis client instance."""
    global redis_pool, redis_client
    if redis_client is None:
        redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=30,
        )
        redis_client = Redis(connection_pool=redis_pool)
    return redis_client


async def init_redis() -> None:
    """Initializes Redis connection and performs health check on startup."""
    logger.info("Initializing Redis connection pool...")
    client = get_redis_client()
    try:
        await client.ping()
        logger.info("Redis connection successfully established.")
    except Exception as exc:
        logger.warning(f"Could not connect to Redis on startup: {exc}")


async def close_redis() -> None:
    """Closes Redis connection pool on application shutdown."""
    global redis_pool, redis_client
    if redis_client is not None:
        logger.info("Closing Redis connection pool...")
        await redis_client.aclose()
        if redis_pool is not None:
            await redis_pool.disconnect()
        redis_client = None
        redis_pool = None
        logger.info("Redis connection closed.")


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency that provides the active Redis client."""
    client = get_redis_client()
    yield client


async def check_redis_health() -> bool:
    """Pings Redis server to verify connectivity."""
    try:
        client = get_redis_client()
        return bool(await client.ping())
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        return False


class RedisCache:
    """Utility helper class for cache operations with JSON serialization."""

    @staticmethod
    async def get(key: str) -> Optional[str]:
        try:
            client = get_redis_client()
            return await client.get(key)
        except Exception as exc:
            logger.warning(f"Redis get failed for key '{key}': {exc}")
            return None

    @staticmethod
    async def get_json(key: str) -> Optional[Any]:
        val = await RedisCache.get(key)
        if val is not None:
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    async def set(
        key: str,
        value: str,
        expire_seconds: int = settings.REDIS_CACHE_EXPIRE_SECONDS,
    ) -> bool:
        try:
            client = get_redis_client()
            await client.set(key, value, ex=expire_seconds)
            return True
        except Exception as exc:
            logger.warning(f"Redis set failed for key '{key}': {exc}")
            return False

    @staticmethod
    async def set_json(
        key: str,
        value: Any,
        expire_seconds: int = settings.REDIS_CACHE_EXPIRE_SECONDS,
    ) -> bool:
        try:
            serialized = json.dumps(value, default=str)
            return await RedisCache.set(key, serialized, expire_seconds)
        except Exception as exc:
            logger.warning(f"Redis JSON serialization failed for key '{key}': {exc}")
            return False

    @staticmethod
    async def delete(key: str) -> bool:
        try:
            client = get_redis_client()
            await client.delete(key)
            return True
        except Exception as exc:
            logger.warning(f"Redis delete failed for key '{key}': {exc}")
            return False

    @staticmethod
    async def delete_pattern(pattern: str) -> int:
        """Deletes all keys matching a specific pattern (e.g. 'driver:*')."""
        try:
            client = get_redis_client()
            deleted_count = 0
            async for key in client.scan_iter(match=pattern):
                await client.delete(key)
                deleted_count += 1
            return deleted_count
        except Exception as exc:
            logger.warning(f"Redis delete pattern '{pattern}' failed: {exc}")
            return 0

