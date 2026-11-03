from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import close_db
from app.core.redis import close_redis
from app.main import app


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provides an AsyncClient for testing the FastAPI application without starting an HTTP server."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def cleanup_connections() -> AsyncGenerator[None, None]:
    """Ensures database and redis connections are gracefully closed after each test."""
    yield
    await close_db()
    await close_redis()
