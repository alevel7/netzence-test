from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_lot import CreditLot, CreditLotStatus


class CreditRepository:
    """Data access repository for Credit Lots and Balance calculations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_lot(
        self,
        driver_id: str,
        ride_id: Optional[str],
        amount: Decimal,
        earned_at: datetime,
        expires_at: datetime,
    ) -> CreditLot:
        lot = CreditLot(
            driver_id=driver_id,
            ride_id=ride_id,
            original_amount=amount,
            remaining_amount=amount,
            earned_at=earned_at,
            expires_at=expires_at,
            status=CreditLotStatus.ACTIVE.value,
        )
        self.session.add(lot)
        await self.session.flush()
        return lot

    async def get_lot_by_ride_id(self, ride_id: str) -> Optional[CreditLot]:
        stmt = select(CreditLot).where(CreditLot.ride_id == ride_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_unexpired_balance(self, driver_id: str, as_of: datetime) -> Decimal:
        """Calculates total active, unexpired credits for driver."""
        stmt = (
            select(func.coalesce(func.sum(CreditLot.remaining_amount), Decimal("0.0000")))
            .where(CreditLot.driver_id == driver_id)
            .where(CreditLot.status == CreditLotStatus.ACTIVE.value)
            .where(CreditLot.remaining_amount > Decimal("0.0000"))
            .where(CreditLot.expires_at > as_of)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_active_lots_fifo_for_update(
        self, driver_id: str, as_of: datetime
    ) -> List[CreditLot]:
        """Fetches active, unexpired credit lots ordered by earned_at ASC (FIFO) with row-level locks."""
        stmt = (
            select(CreditLot)
            .where(CreditLot.driver_id == driver_id)
            .where(CreditLot.status == CreditLotStatus.ACTIVE.value)
            .where(CreditLot.remaining_amount > Decimal("0.0000"))
            .where(CreditLot.expires_at > as_of)
            .order_by(CreditLot.earned_at.asc(), CreditLot.id.asc())
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

