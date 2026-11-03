from decimal import Decimal, ROUND_HALF_UP


class CarbonCalculator:
    """Calculates carbon credits awarded for rides based on vehicle type and distance."""

    # Default rate: 1.0000 credit per kilometer for Electric Vehicles (EV)
    # Baseline assumption: An EV eliminates ~120g of CO2 per km relative to an average ICE vehicle.
    # 1 credit = 1 carbon offset unit
    DEFAULT_EV_RATE = Decimal("1.0000")
    HYBRID_RATE = Decimal("0.5000")

    @classmethod
    def calculate_credits(cls, distance_km: Decimal, vehicle_type: str) -> Decimal:
        """Computes credit amount with fixed-point decimal precision (4 decimal places).

        Assumptions:
        - EV / BEV / ELECTRIC: 1.0 credit per km
        - HYBRID / PHEV: 0.5 credits per km
        - Other: 0.2 credits per km
        """
        v_type = vehicle_type.strip().upper()
        if v_type in {"EV", "BEV", "ELECTRIC"}:
            rate = cls.DEFAULT_EV_RATE
        elif v_type in {"HYBRID", "PHEV"}:
            rate = cls.HYBRID_RATE
        else:
            rate = Decimal("0.2000")

        raw_credits = distance_km * rate
        # Quantize to 4 decimal places using bankers rounding / half up
        return raw_credits.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

