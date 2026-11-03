from fastapi import APIRouter, Depends, Path, status

from app.api.deps import get_driver_service
from app.schemas.driver import (
    DriverBalanceResponse,
    DriverHistoryResponse,
    RedeemRequest,
    RedeemResponse,
)
from app.services.driver_service import DriverService

router = APIRouter()


@router.get(
    "/{id}/balance",
    response_model=DriverBalanceResponse,
    summary="Get active driver carbon credit balance",
    description="Returns the total active, unexpired carbon credit balance for the specified driver.",
)
async def get_driver_balance(
    driver_id: str = Path(..., alias="id", description="Unique driver ID"),
    service: DriverService = Depends(get_driver_service),
) -> DriverBalanceResponse:
    return await service.get_balance(driver_id)


@router.get(
    "/{id}/history",
    response_model=DriverHistoryResponse,
    summary="Get driver credit & debit history",
    description="Returns an audit ledger of every credit, debit, and reversal transaction with its reason.",
)
async def get_driver_history(
    driver_id: str = Path(..., alias="id", description="Unique driver ID"),
    service: DriverService = Depends(get_driver_service),
) -> DriverHistoryResponse:
    return await service.get_history(driver_id)


@router.post(
    "/{id}/redeem",
    response_model=RedeemResponse,
    status_code=status.HTTP_200_OK,
    summary="Redeem driver credits (FIFO)",
    description=(
        "Consumes unexpired carbon credits using FIFO order (oldest lots first). "
        "Guarantees that simultaneous requests will never drive the balance below zero."
    ),
)
async def redeem_driver_credits(
    payload: RedeemRequest,
    driver_id: str = Path(..., alias="id", description="Unique driver ID"),
    service: DriverService = Depends(get_driver_service),
) -> RedeemResponse:
    return await service.redeem_credits(driver_id, payload)

