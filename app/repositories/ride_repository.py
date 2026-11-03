from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride import Ride, RideStatus


class RideRepository:
    """Data access repository for Ride records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, ride_id: str) -> Optional[Ride]:
        stmt = select(Ride).where(Ride.id == ride_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, ride_id: str) -> Optional[Ride]:
        stmt = select(Ride).where(Ride.id == ride_id).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        ride_id: str,
        driver_id: str,
        distance_km: Decimal,
        vehicle_type: str,
        completed_at: datetime,
        status: RideStatus = RideStatus.COMPLETED,
    ) -> Ride:
        ride = Ride(
            id=ride_id,
            driver_id=driver_id,
            distance_km=distance_km,
            vehicle_type=vehicle_type,
            completed_at=completed_at,
            status=status.value,
        )
        self.session.add(ride)
        await self.session.flush()
        return ride

    async def create_cancelled_tombstone(self, ride_id: str, driver_id: str = "unknown") -> Ride:
        ride = Ride(
            id=ride_id,
            driver_id=driver_id,
            distance_km=Decimal("0.0000"),
            vehicle_type="UNKNOWN",
            completed_at=None,
            status=RideStatus.CANCELLED.value,
        )
        self.session.add(ride)
        await self.session.flush()
        return ride

