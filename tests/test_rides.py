import uuid
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient

from app.core.database import get_session_factory
from app.models.credit_lot import CreditLot
from app.models.ledger import LedgerTransaction
from sqlalchemy import select


@pytest.mark.asyncio
async def test_complete_ride_success(async_client: AsyncClient) -> None:
    uid = uuid.uuid4().hex[:8]
    ride_id = f"ride_{uid}"
    driver_id = f"driver_{uid}"
    
    payload = {
        "ride_id": ride_id,
        "driver_id": driver_id,
        "distance_km": 25.5,
        "vehicle_type": "EV",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    response = await async_client.post("/rides/completed", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ride_id"] == ride_id
    assert data["driver_id"] == driver_id
    assert Decimal(str(data["credits_awarded"])) == Decimal("25.5000")
    assert data["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_complete_ride_idempotency_duplicate_event(async_client: AsyncClient) -> None:
    uid = uuid.uuid4().hex[:8]
    ride_id = f"ride_dup_{uid}"
    driver_id = f"driver_dup_{uid}"
    
    payload = {
        "ride_id": ride_id,
        "driver_id": driver_id,
        "distance_km": 10.0,
        "vehicle_type": "EV",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    # First event
    resp1 = await async_client.post("/rides/completed", json=payload)
    assert resp1.status_code == 200
    assert Decimal(str(resp1.json()["credits_awarded"])) == Decimal("10.0000")

    # Second duplicate event
    resp2 = await async_client.post("/rides/completed", json=payload)
    assert resp2.status_code == 200
    assert "Duplicate" in resp2.json()["message"]

    # Verify database has exactly 1 credit lot and 1 ledger entry for this ride
    session_factory = get_session_factory()
    async with session_factory() as session:
        lots = (await session.execute(select(CreditLot).where(CreditLot.ride_id == ride_id))).scalars().all()
        assert len(lots) == 1
        
        ledger_entries = (
            await session.execute(select(LedgerTransaction).where(LedgerTransaction.ride_id == ride_id))
        ).scalars().all()
        assert len(ledger_entries) == 1


@pytest.mark.asyncio
async def test_cancel_ride_reverses_credits(async_client: AsyncClient) -> None:
    uid = uuid.uuid4().hex[:8]
    ride_id = f"ride_cancel_{uid}"
    driver_id = f"driver_cancel_{uid}"
    
    # 1. Complete ride
    await async_client.post(
        "/rides/completed",
        json={
            "ride_id": ride_id,
            "driver_id": driver_id,
            "distance_km": 20.0,
            "vehicle_type": "EV",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Verify initial balance is 20
    bal_resp = await async_client.get(f"/drivers/{driver_id}/balance")
    assert Decimal(str(bal_resp.json()["balance"])) == Decimal("20.0000")

    # 2. Cancel ride
    cancel_resp = await async_client.post(
        "/rides/cancelled",
        json={"ride_id": ride_id, "reason": "Passenger cancelled"},
    )
    assert cancel_resp.status_code == 200
    assert Decimal(str(cancel_resp.json()["reversed_credits"])) == Decimal("20.0000")

    # 3. Verify balance is now 0
    bal_resp2 = await async_client.get(f"/drivers/{driver_id}/balance")
    assert Decimal(str(bal_resp2.json()["balance"])) == Decimal("0.0000")

    # 4. Verify history contains both CREDIT and REVERSAL
    hist_resp = await async_client.get(f"/drivers/{driver_id}/history")
    history = hist_resp.json()["history"]
    types = [h["type"] for h in history]
    assert "CREDIT" in types
    assert "REVERSAL" in types


@pytest.mark.asyncio
async def test_out_of_order_cancellation_before_completion(async_client: AsyncClient) -> None:
    uid = uuid.uuid4().hex[:8]
    ride_id = f"ride_ooo_{uid}"
    driver_id = f"driver_ooo_{uid}"

    # 1. Cancellation arrives first
    cancel_resp = await async_client.post(
        "/rides/cancelled",
        json={"ride_id": ride_id, "reason": "Driver vehicle broke down"},
    )
    assert cancel_resp.status_code == 200
    assert "prior to completion" in cancel_resp.json()["message"]

    # 2. Completion arrives subsequently
    comp_resp = await async_client.post(
        "/rides/completed",
        json={
            "ride_id": ride_id,
            "driver_id": driver_id,
            "distance_km": 50.0,
            "vehicle_type": "EV",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert comp_resp.status_code == 200
    # Zero credits awarded due to prior cancellation
    assert Decimal(str(comp_resp.json()["credits_awarded"])) == Decimal("0.0000")
    assert comp_resp.json()["status"] == "CANCELLED"
