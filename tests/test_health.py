from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert data["health"] == "/api/v1/health"


@pytest.mark.asyncio
async def test_liveness_probe(async_client: AsyncClient) -> None:
    response = await async_client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "alive"}


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.health.check_database_health")
@patch("app.api.v1.endpoints.health.check_redis_health")
async def test_readiness_probe_healthy(
    mock_redis: patch, mock_db: patch, async_client: AsyncClient
) -> None:
    mock_db.return_value = True
    mock_redis.return_value = True

    response = await async_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.health.check_database_health")
@patch("app.api.v1.endpoints.health.check_redis_health")
async def test_readiness_probe_unhealthy(
    mock_redis: patch, mock_db: patch, async_client: AsyncClient
) -> None:
    mock_db.return_value = False
    mock_redis.return_value = True

    response = await async_client.get("/api/v1/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not ready"
    assert data["database"] == "down"
    assert data["redis"] == "up"


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.health.check_database_health")
@patch("app.api.v1.endpoints.health.check_redis_health")
async def test_comprehensive_health_healthy(
    mock_redis: patch, mock_db: patch, async_client: AsyncClient
) -> None:
    mock_db.return_value = True
    mock_redis.return_value = True

    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["services"]["database"]["status"] == "up"
    assert data["services"]["redis"]["status"] == "up"
    assert "latency_ms" in data["services"]["database"]
    assert "latency_ms" in data["services"]["redis"]


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.health.check_database_health")
@patch("app.api.v1.endpoints.health.check_redis_health")
async def test_comprehensive_health_degraded(
    mock_redis: patch, mock_db: patch, async_client: AsyncClient
) -> None:
    mock_db.return_value = True
    mock_redis.return_value = False

    response = await async_client.get("/api/v1/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["services"]["database"]["status"] == "up"
    assert data["services"]["redis"]["status"] == "down"

