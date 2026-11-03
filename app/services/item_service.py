from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.core.redis import RedisCache
from app.models.item import Item
from app.repositories.item_repository import ItemRepository
from app.schemas.item import (
    ItemCreate,
    ItemListResponse,
    ItemResponse,
    ItemUpdate,
)


class ItemService:
    """Business logic for Items with Redis caching support."""

    CACHE_KEY_PREFIX = "item:"
    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ItemRepository(session)

    @classmethod
    def _cache_key(cls, item_id: int) -> str:
        return f"{cls.CACHE_KEY_PREFIX}{item_id}"

    async def get_item(self, item_id: int) -> ItemResponse:
        """Retrieves an item by ID, checking Redis cache first (Cache-Aside pattern)."""
        cache_key = self._cache_key(item_id)

        # 1. Check Redis Cache
        cached_data = await RedisCache.get_json(cache_key)
        if cached_data:
            logger.debug(f"Redis cache hit for key: {cache_key}")
            return ItemResponse.model_validate(cached_data)

        # 2. Query Database
        logger.debug(f"Redis cache miss for key: {cache_key}. Querying database...")
        item = await self.repository.get_by_id(item_id)
        if not item:
            raise NotFoundException(f"Item with ID {item_id} was not found")

        # 3. Serialize and Populate Redis Cache
        response_model = ItemResponse.model_validate(item)
        await RedisCache.set_json(
            cache_key,
            response_model.model_dump(mode="json"),
            expire_seconds=self.CACHE_TTL_SECONDS,
        )

        return response_model

    async def list_items(self, page: int = 1, page_size: int = 20) -> ItemListResponse:
        """Lists paginated items from the database."""
        skip = (page - 1) * page_size
        items, total = await self.repository.list(skip=skip, limit=page_size)

        return ItemListResponse(
            items=[ItemResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_item(self, item_in: ItemCreate) -> ItemResponse:
        """Creates a new item in the database and caches it in Redis."""
        item = await self.repository.create(item_in)
        response_model = ItemResponse.model_validate(item)

        # Cache new item in Redis
        cache_key = self._cache_key(item.id)
        await RedisCache.set_json(
            cache_key,
            response_model.model_dump(mode="json"),
            expire_seconds=self.CACHE_TTL_SECONDS,
        )

        logger.info(f"Created new Item with ID={item.id}")
        return response_model

    async def update_item(self, item_id: int, item_in: ItemUpdate) -> ItemResponse:
        """Updates an existing item and invalidates/refreshes the cache."""
        item = await self.repository.get_by_id(item_id)
        if not item:
            raise NotFoundException(f"Item with ID {item_id} was not found")

        updated_item = await self.repository.update(item, item_in)
        response_model = ItemResponse.model_validate(updated_item)

        # Invalidate/update cache
        cache_key = self._cache_key(item_id)
        await RedisCache.set_json(
            cache_key,
            response_model.model_dump(mode="json"),
            expire_seconds=self.CACHE_TTL_SECONDS,
        )

        logger.info(f"Updated Item with ID={item_id}")
        return response_model

    async def delete_item(self, item_id: int) -> None:
        """Deletes an item from the database and removes it from Redis cache."""
        item = await self.repository.get_by_id(item_id)
        if not item:
            raise NotFoundException(f"Item with ID {item_id} was not found")

        await self.repository.delete(item)

        # Evict from Redis cache
        cache_key = self._cache_key(item_id)
        await RedisCache.delete(cache_key)

        logger.info(f"Deleted Item with ID={item_id}")

