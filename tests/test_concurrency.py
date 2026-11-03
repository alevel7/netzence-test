import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_concurrent_redemption_never_overdraws_balance() -> None:
    """Stress tests concurrency safety under simultaneous redemption requests.

    Setup: Driver is awarded 100 credits.
    Simulation: 5 concurrent redemption requests of 30 credits each are submitted in parallel.
    Expected outcome:
      - Total requested: 150 credits
      - Exactly 3 requests must succeed (90 credits redeemed)
      - Exactly 2 requests must fail with 400 Bad Request
      - Final driver balance is exactly 10 credits and NEVER drops below zero.
    """
    transport = ASGITransport(app=app)
    driver_id = f"driver_concurrency_{datetime.now().timestamp()}"

    # Use a client to set up the driver's credits
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        setup_resp = await client.post(
            "/rides/completed",
            json={
                "ride_id": f"ride_setup_{datetime.now().timestamp()}",
                "driver_id": driver_id,
                "distance_km": 100.0,
                "vehicle_type": "EV",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert setup_resp.status_code == 200
        assert Decimal(str(setup_resp.json()["credits_awarded"])) == Decimal("100.0000")

    # Define concurrent redemption worker
    async def attempt_redeem(worker_idx: int) -> int:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                f"/drivers/{driver_id}/redeem",
                json={"amount": 30.0, "reason": f"Concurrent redeem attempt {worker_idx}"},
            )
            return resp.status_code

    # Fire 5 concurrent requests simultaneously
    results = await asyncio.gather(*[attempt_redeem(i) for i in range(5)])

    successes = [code for code in results if code == 200]
    failures = [code for code in results if code == 400]

    # Exactly 3 must succeed (3 x 30 = 90) and 2 must fail (10 < 30)
    assert len(successes) == 3, f"Expected 3 successes, got {len(successes)}: {results}"
    assert len(failures) == 2, f"Expected 2 failures, got {len(failures)}: {results}"

    # Verify final balance is exactly 10.0000
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        bal_resp = await client.get(f"/drivers/{driver_id}/balance")
        assert bal_resp.status_code == 200
        final_balance = Decimal(str(bal_resp.json()["balance"]))
        assert final_balance == Decimal("10.0000")

