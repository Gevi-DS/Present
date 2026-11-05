# Shared contracts — initial version approved at the October 29 checkpoint.
"""Public interfaces for the pickleball reservation system.

Common rules:
- Times are naive datetime objects representing Philippine local time.
- Slot starts must be exactly on the hour; now may include minutes and seconds.
- Money is integer centavos. Rates and total quotes are positive even integers.
- Payment amounts are positive integers; bool is not accepted as an integer.
- Names, IDs, and references must be nonempty strings after stripping whitespace.
- Malformed arguments raise ValueError.
- Valid arguments that violate business rules raise BookingError.
- Failed operations leave state unchanged.
"""
from abc import ABC, abstractmethod
from datetime import datetime


class BookingError(Exception):
    """A valid request violates a facility business rule."""


class ICourt(ABC):
    """Court with daily operating hours and one-hour maintenance closures."""
    @property
    @abstractmethod
    def court_id(self) -> str:
        """Stable nonempty court ID; read-only."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nonempty display name; read-only."""

    @abstractmethod
    def block_slot(self, start: datetime) -> None:
        """Block one hour. BookingError: already blocked or outside open hours."""

    @abstractmethod
    def require_available(self, start: datetime) -> None:
        """BookingError if closed or blocked. Does not check reservations."""


class IBookingPolicy(ABC):
    """Booking window and cancellation eligibility."""
    @property
    @abstractmethod
    def name(self) -> str:
        """Policy name; read-only."""

    @property
    @abstractmethod
    def refund_notice_hours(self) -> int:
        """Minimum notice for a full refund; read-only nonnegative integer."""

    @abstractmethod
    def validate_booking(self, start: datetime, now: datetime) -> None:
        """BookingError unless now < start <= now + seven days."""

    @abstractmethod
    def refundable(self, start: datetime, now: datetime) -> bool:
        """Return whether cancellation qualifies for a full refund.

        Return True when notice is at least refund_notice_hours.
        Exactly meeting the threshold qualifies.
        Raise ValueError for malformed times.
        Raise BookingError if now is at or after start.
        """


class IPricing(ABC):
    """Interchangeable standard and peak pricing for one-hour slots."""
    @property
    @abstractmethod
    def name(self) -> str:
        """Pricing name; read-only."""

    @property
    @abstractmethod
    def base_rate(self) -> int:
        """Positive even centavos per hour; read-only."""

    @abstractmethod
    def quote(self, court: ICourt, start: datetime, hours: int = 1) -> int:
        """Return a positive even integer price in centavos for one hour.
        Raise ValueError for an invalid court, malformed start, or non-integer hours.
        Raise BookingError if integer hours != 1 or the court is unavailable.
        Check availability using court.require_available(start).
        """


class IPayment(ABC):
    """One payment account per reservation; records staff-verified money only."""
    @property
    @abstractmethod
    def total(self) -> int:
        """Frozen price quote in centavos; read-only."""

    @property
    @abstractmethod
    def paid(self) -> int:
        """Total recorded payments in centavos, less recorded refunds; read-only."""

    @abstractmethod
    def record(self, amount: int, reference: str) -> None:
        """Record a positive integer amount in centavos.

        Raise ValueError for an invalid amount or empty/non-string reference.
        Strip reference whitespace; references must be unique within this account.
        Raise BookingError for a first payment below half the total, a duplicate
        reference, an overpayment, or a closed account.
        Failed payments leave state unchanged.
        """

    @abstractmethod
    def close(self, refund: bool) -> int:
        """Close the account and return the recorded refund in centavos.

        refund must be a bool; otherwise raise ValueError.
        If True, return the paid amount and reset paid to zero.
        If False, return zero and retain the paid amount.
        Raise BookingError if the account is already closed.
        A closed account accepts no further payments.
        This method records a refund; it never transfers real money.
        """

class IReservationService(ABC):
    """Service coordinates all courts and bookings within one facility instance."""
    @property
    @abstractmethod
    def name(self) -> str:
        """Facility name; read-only."""

    @property
    @abstractmethod
    def booking_ids(self) -> tuple[str, ...]:
        """Immutable snapshot of all registered booking IDs; read-only."""

    @abstractmethod
    def request(self, booking_id: str, player_name: str, court: ICourt,
                start: datetime, payment: IPayment, now: datetime) -> None:
        """Create pending request. BookingError: duplicate ID, reused payment,
        invalid window, unavailable court, conflicting confirmed or checked-in booking for the same court and start, or
        payment.total differs from injected pricing.quote(court, start).
        A pending request does not hold the slot.
        """

    @abstractmethod
    def confirm(self, booking_id: str, now: datetime) -> None:
        """Recheck availability/window/conflicts and require paid >= total / 2.

        BookingError for unknown ID, wrong state, or failed checks.
        """

    @abstractmethod
    def cancel(self, booking_id: str, now: datetime) -> int:
        """Cancel pending/confirmed request before start; return refund centavos.

        Pending: refund all recorded funds. Confirmed: injected policy decides.
        Call payment.close; release slot only on success. BookingError for
        unknown ID, wrong state, or cancellation at/after start.
        """

    @abstractmethod
    def check_in(self, booking_id: str, now: datetime) -> None:
        """Require confirmed, fully paid, and start <= now < start + one hour.

        Change state to checked_in; otherwise raise BookingError.
        """

    @abstractmethod
    def complete(self, booking_id: str, now: datetime) -> None:
        """Require checked_in and now >= end; change state to completed.

        Otherwise raise BookingError.
        """

    @abstractmethod
    def status(self, booking_id: str) -> str:
        """Return pending/confirmed/cancelled/checked_in/completed.

        BookingError for unknown ID.
        """
