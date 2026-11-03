from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import LedgerTransaction, TransactionType


class LedgerRepository:
    """Data access repository for immutable audit ledger transactions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_transaction(
        self,
        driver_id: str,
        transaction_type: TransactionType,
        amount: Decimal,
        reason: str,
        ride_id: Optional[str] = None,
    ) -> LedgerTransaction:
        entry = LedgerTransaction(
            driver_id=driver_id,
            transaction_type=transaction_type.value,
            amount=amount,
            reason=reason,
            ride_id=ride_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_history_by_driver(
        self, driver_id: str, limit: int = 100
    ) -> List[LedgerTransaction]:
        stmt = (
            select(LedgerTransaction)
            .where(LedgerTransaction.driver_id == driver_id)
            .order_by(LedgerTransaction.created_at.desc(), LedgerTransaction.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

