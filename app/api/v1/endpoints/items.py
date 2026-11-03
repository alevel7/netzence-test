from fastapi import APIRouter, Depends, Path, status

from app.api.deps import PaginationParams, get_item_service
from app.schemas.item import (
    ItemCreate,
    ItemListResponse,
    ItemResponse,
    ItemUpdate,
)
from app.services.item_service import ItemService

router = APIRouter()


@router.get(
    "/",
    response_model=ItemListResponse,
    summary="List items",
    description="Retrieves a paginated list of items.",
)
async def list_items(
    pagination: PaginationParams = Depends(),
    service: ItemService = Depends(get_item_service),
) -> ItemListResponse:
    return await service.list_items(page=pagination.page, page_size=pagination.page_size)


@router.post(
    "/",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create item",
    description="Creates a new item and caches it in Redis.",
)
async def create_item(
    item_in: ItemCreate,
    service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    return await service.create_item(item_in)


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Get item by ID",
    description="Retrieves an item by ID, leveraging Redis cache when available.",
)
async def get_item(
    item_id: int = Path(..., ge=1, description="Item ID"),
    service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    return await service.get_item(item_id)


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    summary="Update item",
    description="Updates an existing item and refreshes the Redis cache.",
)
async def update_item(
    item_in: ItemUpdate,
    item_id: int = Path(..., ge=1, description="Item ID"),
    service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    return await service.update_item(item_id, item_in)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete item",
    description="Deletes an item from the database and evicts it from the Redis cache.",
)
async def delete_item(
    item_id: int = Path(..., ge=1, description="Item ID"),
    service: ItemService = Depends(get_item_service),
) -> None:
    await service.delete_item(item_id)

