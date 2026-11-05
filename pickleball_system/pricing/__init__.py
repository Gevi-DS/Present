# Author: Bautista, Michael Y. (module: pricing)
"""Standard and peak-hour prices in integer centavos."""

from datetime import datetime

from contracts import BookingError, ICourt, IPricing


class StandardPricing(IPricing):
    """Charge a fixed rate for an available one-hour court slot."""

    def __init__(self, name: str, base_rate: int):
        """Reject invalid names or rates with ValueError."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Pricing name must be a nonempty string.")

        if type(base_rate) is not int or base_rate <= 0 or base_rate % 2:
            raise ValueError(
                "Rate must be a positive even integer in centavos."
            )

        self._name = name.strip()
        self._base_rate = base_rate

    @property
    def name(self) -> str:
        """Return the read-only pricing name."""
        return self._name

    @property
    def base_rate(self) -> int:
        """Return the read-only hourly rate in centavos."""
        return self._base_rate

    def quote(
        self,
        court: ICourt,
        start: datetime,
        hours: int = 1,
    ) -> int:
        """Return a price in centavos for one available hour.

        Invalid types or times raise ValueError.
        Unsupported durations or unavailable courts raise BookingError.
        No state is changed.
        """
        if not isinstance(court, ICourt):
            raise ValueError("Court must implement ICourt.")

        if not isinstance(start, datetime) or start.tzinfo is not None:
            raise ValueError(
                "Use a naive datetime in Philippine local time."
            )

        if start.minute or start.second or start.microsecond:
            raise ValueError("Slots must start exactly on the hour.")

        if type(hours) is not int:
            raise ValueError("Duration must be an integer.")

        if hours != 1:
            raise BookingError("Only one-hour bookings are supported.")

        court.require_available(start)
        return self._base_rate

    def __str__(self) -> str:
        """Return a readable rate label."""
        return f"{self._name}: {self._base_rate} centavos/hour"


class TimeBasedPricing(StandardPricing):
    """Use an evening rate for slots starting from 18:00 through 21:00."""

    def __init__(
        self,
        name: str,
        base_rate: int,
        evening_rate: int,
    ):
        """Reject invalid evening rates or rates below the base rate."""
        super().__init__(name, base_rate)

        if (
            type(evening_rate) is not int
            or evening_rate < base_rate
            or evening_rate % 2
        ):
            raise ValueError(
                "Evening rate must be even and at least the base rate."
            )

        self._evening_rate = evening_rate

    @property
    def evening_rate(self) -> int:
        """Return the read-only evening rate in centavos."""
        return self._evening_rate

    def quote(
        self,
        court: ICourt,
        start: datetime,
        hours: int = 1,
    ) -> int:
        """Select the rate according to the booking start time."""
        normal_rate = super().quote(court, start, hours)

        if 18 <= start.hour < 22:
            return self._evening_rate

        return normal_rate