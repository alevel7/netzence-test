from fastapi import APIRouter, Depends, status

from app.api.deps import get_ride_service
from app.schemas.ride import (
    RideCancelledRequest,
    RideCancelledResponse,
    RideCompletedRequest,
    RideResponse,
)
from app.services.ride_service import RideService

router = APIRouter()


@router.post(
    "/completed",
    response_model=RideResponse,
    status_code=status.HTTP_200_OK,
    summary="Record completed ride event",
    description=(
        "Receives a ride completed event, calculates carbon credits, and awards them to the driver. "
        "Enforces idempotency: duplicate events for the same ride_id are safely ignored without double-crediting."
    ),
)
async def complete_ride(
    payload: RideCompletedRequest,
    service: RideService = Depends(get_ride_service),
) -> RideResponse:
    return await service.process_completed_ride(payload)


@router.post(
    "/cancelled",
    response_model=RideCancelledResponse,
    status_code=status.HTTP_200_OK,
    summary="Reverse credits for cancelled ride",
    description=(
        "Reverses carbon credits awarded for a ride that was cancelled or refunded. "
        "The immutable ledger preserves the original credit entry alongside a reversal debit entry."
    ),
)
async def cancel_ride(
    payload: RideCancelledRequest,
    service: RideService = Depends(get_ride_service),
) -> RideCancelledResponse:
    return await service.process_cancelled_ride(payload)

