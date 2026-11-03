from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RideCompletedRequest(BaseModel):
    """Payload for POST /rides/completed."""

    model_config = ConfigDict(extra="ignore")

    ride_id: str = Field(..., min_length=1, max_length=100, examples=["ride_101"])
    driver_id: str = Field(..., min_length=1, max_length=100, examples=["driver_abc"])
    distance_km: Decimal = Field(..., gt=0, examples=[15.5])
    vehicle_type: str = Field(..., min_length=1, max_length=50, examples=["EV"])
    completed_at: datetime = Field(..., examples=["2026-11-03T12:00:00Z"])


class RideCancelledRequest(BaseModel):
    """Payload for POST /rides/cancelled."""

    model_config = ConfigDict(extra="ignore")

    ride_id: str = Field(..., min_length=1, max_length=100, examples=["ride_101"])
    cancelled_at: Optional[datetime] = None
    reason: Optional[str] = Field(default="Ride cancelled or refunded", max_length=500)


class RideResponse(BaseModel):
    """Response returned upon processing a completed ride."""

    ride_id: str
    driver_id: str
    distance_km: Decimal
    vehicle_type: str
    completed_at: Optional[datetime]
    status: str
    credits_awarded: Decimal
    message: str


class RideCancelledResponse(BaseModel):
    """Response returned upon processing a cancelled ride."""

    ride_id: str
    status: str
    reversed_credits: Decimal
    message: str

