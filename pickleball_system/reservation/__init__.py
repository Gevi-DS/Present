# Author: Canoy, Gevi P. (module: reservation)
"""Coordinate reservations through shared contracts."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from contracts import (
    BookingError,
    IBookingPolicy,
    ICourt,
    IPayment,
    IPricing,
    IReservationService,
)


@dataclass
class _Booking:
    """Internal record; never returned to callers."""

    player_name: str
    court: ICourt
    start: datetime
    payment: IPayment
    state: str = "pending"


class ReservationService(IReservationService):
    """Manage one facility's bookings using injected contract objects."""

    def __init__(
        self,
        name: str,
        policy: IBookingPolicy,
        pricing: IPricing,
    ):
        """Reject invalid names or dependencies with ValueError."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Facility name must be a nonempty string.")

        if (
            not isinstance(policy, IBookingPolicy)
            or not isinstance(pricing, IPricing)
        ):
            raise ValueError(
                "Policy and pricing must implement their contracts."
            )

        self._name = name.strip()
        self._policy = policy
        self._pricing = pricing
        self._bookings: dict[str, _Booking] = {}

    @property
    def name(self) -> str:
        """Return the read-only facility name."""
        return self._name

    @property
    def booking_ids(self) -> tuple[str, ...]:
        """Return an immutable snapshot of booking IDs."""
        return tuple(self._bookings)

    def _text(self, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("IDs and names must be nonempty strings.")

        return value.strip()

    def _time(self, value: datetime) -> None:
        if not isinstance(value, datetime) or value.tzinfo is not None:
            raise ValueError(
                "Use naive datetimes in Philippine local time."
            )

    def _get(self, booking_id: str) -> _Booking:
        booking_id = self._text(booking_id)

        if booking_id not in self._bookings:
            raise BookingError("Unknown booking ID.")

        return self._bookings[booking_id]

    def _no_conflict(self, court: ICourt, start: datetime) -> None:
        for booking in self._bookings.values():
            if (
                booking.court.court_id == court.court_id
                and booking.start == start
                and booking.state in ("confirmed", "checked_in")
            ):
                raise BookingError(
                    "This court and time are already booked."
                )

    def request(
        self,
        booking_id: str,
        player_name: str,
        court: ICourt,
        start: datetime,
        payment: IPayment,
        now: datetime,
    ) -> None:
        """Create a pending request without holding the slot.

        ValueError: malformed inputs.
        BookingError: duplicate ID, reused account, invalid window,
        unavailable slot, conflict, or mismatched payment quote.
        """
        booking_id = self._text(booking_id)
        player_name = self._text(player_name)
        self._time(start)
        self._time(now)

        if start.minute or start.second or start.microsecond:
            raise ValueError("Slots must start exactly on the hour.")

        if (
            not isinstance(court, ICourt)
            or not isinstance(payment, IPayment)
        ):
            raise ValueError(
                "Court and payment must implement their contracts."
            )

        if booking_id in self._bookings:
            raise BookingError("Booking ID already exists.")

        if any(
            booking.payment is payment
            for booking in self._bookings.values()
        ):
            raise BookingError(
                "Use a separate payment account for each booking."
            )

        self._policy.validate_booking(start, now)
        court.require_available(start)
        self._no_conflict(court, start)

        if payment.total != self._pricing.quote(court, start):
            raise BookingError(
                "Payment total does not match this booking's price."
            )

        self._bookings[booking_id] = _Booking(
            player_name,
            court,
            start,
            payment,
        )

    def confirm(self, booking_id: str, now: datetime) -> None:
        """Confirm a pending request with a deposit.

        Recheck the booking window, court availability, and conflicts.
        Malformed time raises ValueError.
        Failed business checks raise BookingError.
        """
        self._time(now)
        booking = self._get(booking_id)

        if booking.state != "pending":
            raise BookingError(
                "Only pending bookings can be confirmed."
            )

        self._policy.validate_booking(booking.start, now)
        booking.court.require_available(booking.start)
        self._no_conflict(booking.court, booking.start)

        if booking.payment.paid < booking.payment.total // 2:
            raise BookingError(
                "A 50% deposit is required before confirmation."
            )

        booking.state = "confirmed"

    def cancel(self, booking_id: str, now: datetime) -> int:
        """Cancel before start and return recorded refund centavos.

        Pending requests receive a full refund.
        Confirmed bookings follow the cancellation policy.
        Malformed time raises ValueError.
        Wrong states or started bookings raise BookingError.
        A failed payment closure leaves the booking unchanged.
        """
        self._time(now)
        booking = self._get(booking_id)

        if (
            booking.state not in ("pending", "confirmed")
            or now >= booking.start
        ):
            raise BookingError(
                "This booking can no longer be cancelled."
            )

        refund = (
            booking.state == "pending"
            or self._policy.refundable(booking.start, now)
        )

        refunded = booking.payment.close(refund)
        booking.state = "cancelled"
        return refunded

    def check_in(self, booking_id: str, now: datetime) -> None:
        """Require confirmation, full payment, and arrival during the slot.

        Malformed time raises ValueError.
        Failed business checks raise BookingError.
        """
        self._time(now)
        booking = self._get(booking_id)

        if booking.state != "confirmed":
            raise BookingError(
                "Only confirmed bookings can check in."
            )

        if booking.payment.paid != booking.payment.total:
            raise BookingError(
                "Pay the remaining balance before check-in."
            )

        end = booking.start + timedelta(hours=1)

        if not booking.start <= now < end:
            raise BookingError(
                "Check-in must occur during the booked hour."
            )

        booking.state = "checked_in"

    def complete(self, booking_id: str, now: datetime) -> None:
        """Complete a checked-in booking at or after its end.

        Malformed time raises ValueError.
        Wrong states or unfinished slots raise BookingError.
        """
        self._time(now)
        booking = self._get(booking_id)
        end = booking.start + timedelta(hours=1)

        if booking.state != "checked_in" or now < end:
            raise BookingError(
                "Only an ended, checked-in booking can complete."
            )

        booking.state = "completed"

    def status(self, booking_id: str) -> str:
        """Return state; raise BookingError for an unknown ID."""
        return self._get(booking_id).state

    def __len__(self) -> int:
        """Count all booking records, including cancelled ones."""
        return len(self._bookings)