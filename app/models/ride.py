from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RideStatus(str, Enum):
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Ride(Base, TimestampMixin):
    """Ride entity tracking completed and cancelled ride events."""

    __tablename__ = "rides"

    # Using string ride_id from external service as primary key for natural idempotency
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    driver_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    distance_km: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0.0000"))
    vehicle_type: Mapped[str] = mapped_column(String(50), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=RideStatus.COMPLETED.value, nullable=False)

    def __repr__(self) -> str:
        return f"<Ride id={self.id!r} driver_id={self.driver_id!r} status={self.status}>"

