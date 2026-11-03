from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate


class ItemRepository:
    """Encapsulates database operations for Item entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, item_id: int) -> Optional[Item]:
        statement = select(Item).where(Item.id == item_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(self, skip: int = 0, limit: int = 20) -> Tuple[List[Item], int]:
        count_stmt = select(func.count(Item.id))
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar_one()

        items_stmt = (
            select(Item)
            .order_by(Item.id.desc())
            .offset(skip)
            .limit(limit)
        )
        items_result = await self.session.execute(items_stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def create(self, item_in: ItemCreate) -> Item:
        item = Item(
            title=item_in.title,
            description=item_in.description,
            price=item_in.price,
            is_active=item_in.is_active,
        )
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def update(self, item: Item, item_in: ItemUpdate) -> Item:
        update_data = item_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def delete(self, item: Item) -> None:
        await self.session.delete(item)
        await self.session.flush()

