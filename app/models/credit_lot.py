from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CreditLotStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVERSED = "REVERSED"
    DEPLETED = "DEPLETED"
    EXPIRED = "EXPIRED"


class CreditLot(Base, TimestampMixin):
    """Credit lot representing earned carbon credits with 12-month expiration and remaining balance."""

    __tablename__ = "credit_lots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    driver_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    ride_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("rides.id"), nullable=True, index=True)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=Decimal("0.0000"))
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default=CreditLotStatus.ACTIVE.value, nullable=False)

    __table_args__ = (
        # Optimized index for unexpired, active lots query in FIFO order
        Index("ix_credit_lots_driver_unexpired", "driver_id", "expires_at", "earned_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<CreditLot id={self.id} driver_id={self.driver_id!r} "
            f"remaining={self.remaining_amount}/{self.original_amount} expires_at={self.expires_at}>"
        )

