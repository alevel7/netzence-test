from collections.abc import AsyncGenerator

from fastapi import Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.services.driver_service import DriverService
from app.services.ride_service import RideService


class PaginationParams:
    """Reusable pagination dependency."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size


async def get_ride_service(
    session: AsyncSession = Depends(get_db),
) -> RideService:
    """Dependency injecting RideService with active DB session."""
    return RideService(session)


async def get_driver_service(
    session: AsyncSession = Depends(get_db),
) -> DriverService:
    """Dependency injecting DriverService with active DB session."""
    return DriverService(session)
