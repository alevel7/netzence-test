from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver_lock import DriverLock


class DriverLockRepository:
    """Provides row-level synchronization lock per driver."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def acquire_driver_lock(self, driver_id: str) -> None:
        """Upserts a driver lock row and locks it exclusively with FOR UPDATE.

        Ensures that concurrent transactions for the same driver execute sequentially.
        """
        # Ensure lock row exists using PostgreSQL ON CONFLICT DO NOTHING
        insert_stmt = (
            insert(DriverLock)
            .values(driver_id=driver_id)
            .on_conflict_do_nothing(index_elements=["driver_id"])
        )
        await self.session.execute(insert_stmt)

        # Acquire exclusive row-level lock
        select_stmt = (
            select(DriverLock.driver_id)
            .where(DriverLock.driver_id == driver_id)
            .with_for_update()
        )
        await self.session.execute(select_stmt)

