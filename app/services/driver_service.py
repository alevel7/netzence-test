from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.core.logging import logger
from app.core.redis import RedisCache
from app.models.credit_lot import CreditLotStatus
from app.models.ledger import TransactionType
from app.repositories.credit_repository import CreditRepository
from app.repositories.driver_lock_repository import DriverLockRepository
from app.repositories.ledger_repository import LedgerRepository
from app.schemas.driver import (
    DriverBalanceResponse,
    DriverHistoryResponse,
    LedgerTransactionItem,
    RedeemRequest,
    RedeemResponse,
)


class DriverService:
    """Business logic for driver balance calculation, history, and concurrent FIFO redemption."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.credit_repo = CreditRepository(session)
        self.ledger_repo = LedgerRepository(session)
        self.lock_repo = DriverLockRepository(session)

    async def get_balance(self, driver_id: str) -> DriverBalanceResponse:
        """Retrieves active, unexpired carbon credit balance for driver."""
        now = datetime.now(timezone.utc)
        balance = await self.credit_repo.get_unexpired_balance(driver_id, as_of=now)

        return DriverBalanceResponse(
            driver_id=driver_id,
            balance=balance,
            currency="carbon_credits",
            as_of=now,
        )

    async def get_history(self, driver_id: str) -> DriverHistoryResponse:
        """Retrieves all ledger entries (credits, debits, reversals) for driver."""
        entries = await self.ledger_repo.get_history_by_driver(driver_id)
        items = [
            LedgerTransactionItem(
                id=entry.id,
                driver_id=entry.driver_id,
                type=entry.transaction_type,
                amount=entry.amount,
                reason=entry.reason,
                ride_id=entry.ride_id,
                created_at=entry.created_at,
            )
            for entry in entries
        ]

        return DriverHistoryResponse(
            driver_id=driver_id,
            history=items,
            total_entries=len(items),
        )

    async def redeem_credits(self, driver_id: str, request: RedeemRequest) -> RedeemResponse:
        """Redeems credits using FIFO order (consuming oldest unexpired credits first).

        Guarantees that simultaneous redeem requests never drive the balance below zero
        by serializing per-driver redemptions using row-level locking.
        """
        now = datetime.now(timezone.utc)

        # 1. Acquire row lock for driver to serialize concurrent requests
        await self.lock_repo.acquire_driver_lock(driver_id)

        # 2. Retrieve active unexpired lots ordered by earned_at ASC (FIFO) with row lock
        lots = await self.credit_repo.get_active_lots_fifo_for_update(driver_id, as_of=now)
        total_available = sum(lot.remaining_amount for lot in lots)

        # 3. Guard against insufficient balance
        if total_available < request.amount:
            logger.warning(
                f"Redemption rejected for driver={driver_id}: "
                f"requested {request.amount}, but only {total_available} available"
            )
            raise BadRequestException(
                message=(
                    f"Insufficient unexpired carbon credits. "
                    f"Available: {total_available}, requested: {request.amount}"
                )
            )

        # 4. Consume credits from oldest lots first (FIFO)
        needed = request.amount
        for lot in lots:
            deduct = min(lot.remaining_amount, needed)
            lot.remaining_amount -= deduct
            needed -= deduct

            if lot.remaining_amount == Decimal("0.0000"):
                lot.status = CreditLotStatus.DEPLETED.value

            if needed == Decimal("0.0000"):
                break

        # 5. Record DEBIT in audit ledger
        ledger_entry = await self.ledger_repo.record_transaction(
            driver_id=driver_id,
            transaction_type=TransactionType.DEBIT,
            amount=-request.amount,
            reason=request.reason or "Driver credit redemption",
            ride_id=None,
        )

        # 6. Flush session and calculate remaining balance
        await self.session.flush()
        remaining_balance = total_available - request.amount

        # 7. Evict balance cache in Redis
        await RedisCache.delete(f"driver:balance:{driver_id}")

        logger.info(
            f"Successfully redeemed {request.amount} credits for driver={driver_id}. "
            f"Remaining balance: {remaining_balance}"
        )

        return RedeemResponse(
            driver_id=driver_id,
            redeemed_amount=request.amount,
            remaining_balance=remaining_balance,
            transaction_id=ledger_entry.id,
            message="Credits redeemed successfully.",
        )

