from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DriverBalanceResponse(BaseModel):
    """Response returned for GET /drivers/{id}/balance."""

    driver_id: str
    balance: Decimal = Field(..., description="Active, unexpired carbon credits balance")
    currency: str = "carbon_credits"
    as_of: datetime


class RedeemRequest(BaseModel):
    """Payload for POST /drivers/{id}/redeem."""

    model_config = ConfigDict(extra="ignore")

    amount: Decimal = Field(..., gt=0, examples=[50.0], description="Amount of credits to redeem")
    reason: Optional[str] = Field(default="Driver credit redemption", max_length=200)


class RedeemResponse(BaseModel):
    """Response returned for POST /drivers/{id}/redeem."""

    driver_id: str
    redeemed_amount: Decimal
    remaining_balance: Decimal
    transaction_id: int
    message: str


class LedgerTransactionItem(BaseModel):
    """Individual transaction entry in driver history."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    driver_id: str
    type: str = Field(..., alias="type")
    amount: Decimal
    reason: str
    ride_id: Optional[str] = None
    created_at: datetime


class DriverHistoryResponse(BaseModel):
    """Response returned for GET /drivers/{id}/history."""

    driver_id: str
    history: List[LedgerTransactionItem]
    total_entries: int

