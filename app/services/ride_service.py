from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.redis import RedisCache
from app.models.credit_lot import CreditLotStatus
from app.models.ledger import TransactionType
from app.models.ride import RideStatus
from app.repositories.credit_repository import CreditRepository
from app.repositories.ledger_repository import LedgerRepository
from app.repositories.ride_repository import RideRepository
from app.schemas.ride import (
    RideCancelledRequest,
    RideCancelledResponse,
    RideCompletedRequest,
    RideResponse,
)
from app.services.carbon_calculator import CarbonCalculator


def add_twelve_months(dt: datetime) -> datetime:
    """Adds approximately 12 months (365 days) to datetime."""
    return dt + timedelta(days=365)


class RideService:
    """Business logic for ride completions, idempotency, and cancellations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ride_repo = RideRepository(session)
        self.credit_repo = CreditRepository(session)
        self.ledger_repo = LedgerRepository(session)

    async def process_completed_ride(self, request: RideCompletedRequest) -> RideResponse:
        """Processes a completed ride event.

        Enforces idempotency: if the ride_id was already processed, existing credits are
        returned and duplicate credits are NEVER awarded.
        """
        # Lock and check if ride already exists
        existing_ride = await self.ride_repo.get_by_id_for_update(request.ride_id)

        if existing_ride:
            # 1. Handle idempotency: Ride already completed
            if existing_ride.status == RideStatus.COMPLETED.value:
                existing_lot = await self.credit_repo.get_lot_by_ride_id(request.ride_id)
                awarded = existing_lot.original_amount if existing_lot else Decimal("0.0000")
                logger.info(
                    f"Duplicate completion event ignored for ride_id={request.ride_id}. "
                    f"Existing credits={awarded}"
                )
                return RideResponse(
                    ride_id=existing_ride.id,
                    driver_id=existing_ride.driver_id,
                    distance_km=existing_ride.distance_km,
                    vehicle_type=existing_ride.vehicle_type,
                    completed_at=existing_ride.completed_at,
                    status=existing_ride.status,
                    credits_awarded=awarded,
                    message="Ride already completed. Duplicate event ignored.",
                )

            # 2. Handle out-of-order arrival: Ride was already CANCELLED prior to completion
            if existing_ride.status == RideStatus.CANCELLED.value:
                existing_ride.driver_id = request.driver_id
                existing_ride.distance_km = request.distance_km
                existing_ride.vehicle_type = request.vehicle_type
                existing_ride.completed_at = request.completed_at
                logger.warning(
                    f"Ride {request.ride_id} received completion after prior cancellation tombstone. "
                    "Zero credits awarded."
                )
                return RideResponse(
                    ride_id=existing_ride.id,
                    driver_id=request.driver_id,
                    distance_km=request.distance_km,
                    vehicle_type=request.vehicle_type,
                    completed_at=request.completed_at,
                    status=RideStatus.CANCELLED.value,
                    credits_awarded=Decimal("0.0000"),
                    message="Ride was cancelled prior to completion arrival. No credits awarded.",
                )

        # 3. New Ride Completion
        credits_awarded = CarbonCalculator.calculate_credits(
            distance_km=request.distance_km,
            vehicle_type=request.vehicle_type,
        )

        # Persist ride
        ride = await self.ride_repo.create(
            ride_id=request.ride_id,
            driver_id=request.driver_id,
            distance_km=request.distance_km,
            vehicle_type=request.vehicle_type,
            completed_at=request.completed_at,
            status=RideStatus.COMPLETED,
        )

        # Compute 12-month expiration date
        expires_at = add_twelve_months(request.completed_at)

        # Create credit lot
        await self.credit_repo.create_lot(
            driver_id=request.driver_id,
            ride_id=request.ride_id,
            amount=credits_awarded,
            earned_at=request.completed_at,
            expires_at=expires_at,
        )

        # Record audit ledger entry
        await self.ledger_repo.record_transaction(
            driver_id=request.driver_id,
            transaction_type=TransactionType.CREDIT,
            amount=credits_awarded,
            reason=f"Completed {request.distance_km}km ride ({request.vehicle_type})",
            ride_id=request.ride_id,
        )

        # Invalidate cached balance in Redis if any
        await RedisCache.delete(f"driver:balance:{request.driver_id}")

        logger.info(
            f"Successfully processed ride_id={request.ride_id}: "
            f"awarded {credits_awarded} credits to driver={request.driver_id}"
        )

        return RideResponse(
            ride_id=ride.id,
            driver_id=ride.driver_id,
            distance_km=ride.distance_km,
            vehicle_type=ride.vehicle_type,
            completed_at=ride.completed_at,
            status=ride.status,
            credits_awarded=credits_awarded,
            message="Ride completed successfully. Credits awarded.",
        )

    async def process_cancelled_ride(self, request: RideCancelledRequest) -> RideCancelledResponse:
        """Processes a cancelled/refunded ride.

        Reverses the credits for the ride while preserving the original credit in the ledger.
        """
        ride = await self.ride_repo.get_by_id_for_update(request.ride_id)

        # 1. Out-of-order cancellation (cancellation arrives before completion)
        if not ride:
            await self.ride_repo.create_cancelled_tombstone(request.ride_id)
            logger.info(
                f"Recorded pre-cancellation tombstone for future ride_id={request.ride_id}"
            )
            return RideCancelledResponse(
                ride_id=request.ride_id,
                status=RideStatus.CANCELLED.value,
                reversed_credits=Decimal("0.0000"),
                message="Cancellation recorded prior to completion event. No credits to reverse.",
            )

        # 2. Idempotency: Ride already cancelled
        if ride.status == RideStatus.CANCELLED.value:
            logger.info(f"Ride {request.ride_id} is already cancelled. Idempotent response.")
            return RideCancelledResponse(
                ride_id=ride.id,
                status=RideStatus.CANCELLED.value,
                reversed_credits=Decimal("0.0000"),
                message="Ride is already marked as cancelled.",
            )

        # 3. Cancel previously completed ride and reverse credits
        ride.status = RideStatus.CANCELLED.value
        reversed_amount = Decimal("0.0000")

        lot = await self.credit_repo.get_lot_by_ride_id(request.ride_id)
        if lot:
            reversed_amount = lot.original_amount
            lot.remaining_amount = Decimal("0.0000")
            lot.status = CreditLotStatus.REVERSED.value

        # Record reversal in audit ledger
        await self.ledger_repo.record_transaction(
            driver_id=ride.driver_id,
            transaction_type=TransactionType.REVERSAL,
            amount=-reversed_amount,
            reason=f"Reversal for cancelled ride {request.ride_id}: {request.reason or 'Cancelled'}",
            ride_id=request.ride_id,
        )

        # Evict cache in Redis
        await RedisCache.delete(f"driver:balance:{ride.driver_id}")

        logger.info(
            f"Successfully cancelled ride_id={request.ride_id}: "
            f"reversed {reversed_amount} credits for driver={ride.driver_id}"
        )

        return RideCancelledResponse(
            ride_id=ride.id,
            status=RideStatus.CANCELLED.value,
            reversed_credits=reversed_amount,
            message="Ride cancelled successfully and credits reversed.",
        )

