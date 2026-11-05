# Author: Sumoroy, Harry M. (module: booking_policy)
"""Booking windows and cancellation policies."""

from datetime import datetime, timedelta

from contracts import BookingError, IBookingPolicy


class BookingPolicy(IBookingPolicy):
    """Validate bookings and determine refund eligibility."""

    def __init__(self, name: str, refund_notice_hours: int):
        """Reject invalid names or notice hours with ValueError."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Policy name must be a nonempty string.")

        if type(refund_notice_hours) is not int or refund_notice_hours < 0:
            raise ValueError("Refund notice must be a nonnegative integer.")

        self._name = name.strip()
        self._refund_notice_hours = refund_notice_hours

    @property
    def name(self) -> str:
        """Return the read-only policy name."""
        return self._name

    @property
    def refund_notice_hours(self) -> int:
        """Return the read-only refund notice in hours."""
        return self._refund_notice_hours

    def _validate_times(self, start: datetime, now: datetime) -> None:
        for value in (start, now):
            if not isinstance(value, datetime) or value.tzinfo is not None:
                raise ValueError(
                    "Use naive datetimes in Philippine local time."
                )

        if start.minute or start.second or start.microsecond:
            raise ValueError("Booking start must be exactly on the hour.")

    def validate_booking(self, start: datetime, now: datetime) -> None:
        """Accept future bookings up to and including seven days ahead.

        Raise ValueError for malformed times.
        Raise BookingError for bookings outside the allowed window.
        """
        self._validate_times(start, now)
        notice = start - now

        if notice <= timedelta(0):
            raise BookingError("A booking must start in the future.")

        if notice > timedelta(days=7):
            raise BookingError("Bookings are limited to seven days ahead.")

    def refundable(self, start: datetime, now: datetime) -> bool:
        """Return whether cancellation qualifies for a full refund.

        Exactly meeting the notice threshold qualifies.
        Raise BookingError at or after the booking starts.
        Raise ValueError for malformed times.
        This method does not record or transfer money.
        """
        self._validate_times(start, now)
        notice = start - now

        if notice <= timedelta(0):
            raise BookingError(
                "Cancellation is not allowed once play starts."
            )

        whole_hours = notice // timedelta(hours=1)
        return whole_hours >= self._refund_notice_hours

    def __str__(self) -> str:
        """Return a readable policy description."""
        return (
            f"{self._name}: "
            f"{self._refund_notice_hours}-hour refund notice"
        )


class RegularPolicy(BookingPolicy):
    """Require at least 24 hours of notice for a full refund."""

    def __init__(self, name: str = "Regular"):
        """Create a regular policy and validate its name."""
        super().__init__(name, 24)


class FlexiblePolicy(BookingPolicy):
    """Require at least six hours of notice for a full refund."""

    def __init__(self, name: str = "Flexible"):
        """Create a flexible policy and validate its name."""
        super().__init__(name, 6)