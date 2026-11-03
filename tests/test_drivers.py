import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient

from app.core.database import get_session_factory
from app.models.credit_lot import CreditLot
from sqlalchemy import select


@pytest.mark.asyncio
async def test_twelve_month_credit_expiration(async_client: AsyncClient) -> None:
    """Verifies that credits older than 12 months expire and do not count toward active balance."""
    uid = uuid.uuid4().hex[:8]
    driver_id = f"driver_exp_{uid}"
    now = datetime.now(timezone.utc)

    # 1. Old ride completed 14 months ago (expired)
    old_time = now - timedelta(days=420)
    await async_client.post(
        "/rides/completed",
        json={
            "ride_id": f"ride_old_{uid}",
            "driver_id": driver_id,
            "distance_km": 100.0,
            "vehicle_type": "EV",
            "completed_at": old_time.isoformat(),
        },
    )

    # 2. Fresh ride completed today (valid)
    await async_client.post(
        "/rides/completed",
        json={
            "ride_id": f"ride_fresh_{uid}",
            "driver_id": driver_id,
            "distance_km": 30.0,
            "vehicle_type": "EV",
            "completed_at": now.isoformat(),
        },
    )

    # Balance must ONLY count unexpired credits (30, NOT 130)
    bal_resp = await async_client.get(f"/drivers/{driver_id}/balance")
    assert bal_resp.status_code == 200
    assert Decimal(str(bal_resp.json()["balance"])) == Decimal("30.0000")


@pytest.mark.asyncio
async def test_fifo_credit_redemption(async_client: AsyncClient) -> None:
    """Verifies that when a driver redeems, the oldest unexpired credits are consumed first."""
    uid = uuid.uuid4().hex[:8]
    driver_id = f"driver_fifo_{uid}"
    now = datetime.now(timezone.utc)

    # Lot 1: Earned 3 months ago (50 credits)
    time_lot1 = now - timedelta(days=90)
    ride1_id = f"ride_lot1_{uid}"
    await async_client.post(
        "/rides/completed",
        json={
            "ride_id": ride1_id,
            "driver_id": driver_id,
            "distance_km": 50.0,
            "vehicle_type": "EV",
            "completed_at": time_lot1.isoformat(),
        },
    )

    # Lot 2: Earned 1 month ago (50 credits)
    time_lot2 = now - timedelta(days=30)
    ride2_id = f"ride_lot2_{uid}"
    await async_client.post(
        "/rides/completed",
        json={
            "ride_id": ride2_id,
            "driver_id": driver_id,
            "distance_km": 50.0,
            "vehicle_type": "EV",
            "completed_at": time_lot2.isoformat(),
        },
    )

    # Total balance = 100
    bal_resp = await async_client.get(f"/drivers/{driver_id}/balance")
    assert Decimal(str(bal_resp.json()["balance"])) == Decimal("100.0000")

    # Redeem 70 credits (should completely drain Lot 1 (50) and take 20 from Lot 2)
    redeem_resp = await async_client.post(
        f"/drivers/{driver_id}/redeem",
        json={"amount": 70.0, "reason": "Gift card redemption"},
    )
    assert redeem_resp.status_code == 200
    assert Decimal(str(redeem_resp.json()["remaining_balance"])) == Decimal("30.0000")

    # Check DB to verify Lot 1 remaining = 0 and Lot 2 remaining = 30
    session_factory = get_session_factory()
    async with session_factory() as session:
        lot1 = (
            await session.execute(select(CreditLot).where(CreditLot.ride_id == ride1_id))
        ).scalar_one()
        lot2 = (
            await session.execute(select(CreditLot).where(CreditLot.ride_id == ride2_id))
        ).scalar_one()

        assert lot1.remaining_amount == Decimal("0.0000")
        assert lot1.status == "DEPLETED"
        assert lot2.remaining_amount == Decimal("30.0000")
        assert lot2.status == "ACTIVE"


@pytest.mark.asyncio
async def test_insufficient_balance_rejection(async_client: AsyncClient) -> None:
    """Verifies that attempting to redeem more credits than available returns a 400 Bad Request."""
    uid = uuid.uuid4().hex[:8]
    driver_id = f"driver_overdraw_{uid}"
    
    # Award 10 credits
    await async_client.post(
        "/rides/completed",
        json={
            "ride_id": f"ride_sm_{uid}",
            "driver_id": driver_id,
            "distance_km": 10.0,
            "vehicle_type": "EV",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Try to redeem 15 credits
    resp = await async_client.post(
        f"/drivers/{driver_id}/redeem",
        json={"amount": 15.0},
    )
    assert resp.status_code == 400
    assert "Insufficient" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_driver_history_audit_trail(async_client: AsyncClient) -> None:
    """Verifies that driver history contains an accurate audit trail of credits and debits."""
    uid = uuid.uuid4().hex[:8]
    driver_id = f"driver_hist_{uid}"

    # 1. Earn credit
    await async_client.post(
        "/rides/completed",
        json={
            "ride_id": f"ride_h_{uid}",
            "driver_id": driver_id,
            "distance_km": 40.0,
            "vehicle_type": "EV",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # 2. Redeem credit
    await async_client.post(
        f"/drivers/{driver_id}/redeem",
        json={"amount": 15.0, "reason": "Coffee discount"},
    )

    # 3. Check history
    resp = await async_client.get(f"/drivers/{driver_id}/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_entries"] == 2
    entries = data["history"]
    types = [e["type"] for e in entries]
    assert "CREDIT" in types
    assert "DEBIT" in types
