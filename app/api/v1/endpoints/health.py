import time
from typing import Dict

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.database import check_database_health
from app.core.redis import check_redis_health
from app.schemas.health import HealthResponse, ServiceComponentStatus

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Comprehensive Health Check",
    description="Checks the operational status and latency of PostgreSQL, Redis, and Application core.",
)
async def health_check(response: Response) -> HealthResponse:
    services: Dict[str, ServiceComponentStatus] = {}

    # Check PostgreSQL
    db_start = time.perf_counter()
    try:
        db_healthy = await check_database_health()
        db_latency = round((time.perf_counter() - db_start) * 1000, 2)
        services["database"] = ServiceComponentStatus(
            status="up" if db_healthy else "down",
            latency_ms=db_latency,
            error=None if db_healthy else "Database connection ping failed",
        )
    except Exception as exc:
        services["database"] = ServiceComponentStatus(
            status="down",
            latency_ms=round((time.perf_counter() - db_start) * 1000, 2),
            error=str(exc),
        )

    # Check Redis
    redis_start = time.perf_counter()
    try:
        redis_healthy = await check_redis_health()
        redis_latency = round((time.perf_counter() - redis_start) * 1000, 2)
        services["redis"] = ServiceComponentStatus(
            status="up" if redis_healthy else "down",
            latency_ms=redis_latency,
            error=None if redis_healthy else "Redis ping failed",
        )
    except Exception as exc:
        services["redis"] = ServiceComponentStatus(
            status="down",
            latency_ms=round((time.perf_counter() - redis_start) * 1000, 2),
            error=str(exc),
        )

    all_up = all(s.status == "up" for s in services.values())
    any_up = any(s.status == "up" for s in services.values())

    if all_up:
        overall_status = "healthy"
        response.status_code = status.HTTP_200_OK
    elif any_up:
        overall_status = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
        services=services,
    )


@router.get(
    "/health/live",
    summary="Liveness Probe",
    description="Kubernetes/Docker liveness probe to verify that the app process is responsive.",
)
async def liveness_probe() -> dict:
    return {"status": "alive"}


@router.get(
    "/health/ready",
    summary="Readiness Probe",
    description="Kubernetes/Docker readiness probe checking whether the app can serve traffic.",
)
async def readiness_probe(response: Response) -> dict:
    db_ok = await check_database_health()
    redis_ok = await check_redis_health()

    if db_ok and redis_ok:
        return {"status": "ready"}

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "not ready",
        "database": "up" if db_ok else "down",
        "redis": "up" if redis_ok else "down",
    }

