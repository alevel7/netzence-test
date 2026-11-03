from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TransactionType(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    REVERSAL = "REVERSAL"


class LedgerTransaction(Base):
    """Immutable audit ledger recording every credit, debit, and reversal."""

    __tablename__ = "ledger_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    driver_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Signed amount: positive for CREDIT, negative for DEBIT/REVERSAL
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    ride_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_ledger_driver_created", "driver_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<LedgerTransaction id={self.id} driver={self.driver_id!r} type={self.transaction_type} amount={self.amount}>"

