from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.api.deps import get_item_service
from app.main import app
from app.schemas.item import ItemListResponse, ItemResponse


@pytest.fixture
def sample_item_response() -> ItemResponse:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return ItemResponse(
        id=1,
        title="Gaming Keyboard",
        description="Mechanical RGB keyboard",
        price=Decimal("129.99"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_list_items(async_client: AsyncClient, sample_item_response: ItemResponse) -> None:
    mock_service = AsyncMock()
    mock_service.list_items.return_value = ItemListResponse(
        items=[sample_item_response],
        total=1,
        page=1,
        page_size=20,
    )

    app.dependency_overrides[get_item_service] = lambda: mock_service

    try:
        response = await async_client.get("/api/v1/items/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Gaming Keyboard"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_item(async_client: AsyncClient, sample_item_response: ItemResponse) -> None:
    mock_service = AsyncMock()
    mock_service.create_item.return_value = sample_item_response

    app.dependency_overrides[get_item_service] = lambda: mock_service

    payload = {
        "title": "Gaming Keyboard",
        "description": "Mechanical RGB keyboard",
        "price": 129.99,
        "is_active": True,
    }

    try:
        response = await async_client.post("/api/v1/items/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Gaming Keyboard"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_item_by_id(async_client: AsyncClient, sample_item_response: ItemResponse) -> None:
    mock_service = AsyncMock()
    mock_service.get_item.return_value = sample_item_response

    app.dependency_overrides[get_item_service] = lambda: mock_service

    try:
        response = await async_client.get("/api/v1/items/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Gaming Keyboard"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_item(async_client: AsyncClient) -> None:
    mock_service = AsyncMock()
    mock_service.delete_item.return_value = None

    app.dependency_overrides[get_item_service] = lambda: mock_service

    try:
        response = await async_client.delete("/api/v1/items/1")
        assert response.status_code == 204
    finally:
        app.dependency_overrides.clear()

