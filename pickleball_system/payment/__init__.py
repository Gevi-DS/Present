# Author: Villaren, Nehemiah Timothy B. (module: payment)
"""Record staff-verified payments in integer centavos."""

from datetime import datetime

from contracts import BookingError, ICourt, IPayment, IPricing


class PaymentAccount(IPayment):
    """Track payments for one reservation."""

    def __init__(
        self,
        pricing: IPricing,
        court: ICourt,
        start: datetime,
    ):
        """Freeze a quote; reject malformed inputs with ValueError.

        An unavailable court may raise BookingError through pricing.quote.
        """
        if not isinstance(pricing, IPricing) or not isinstance(court, ICourt):
            raise ValueError(
                "Pricing and court must implement their contracts."
            )

        if not isinstance(start, datetime) or start.tzinfo is not None:
            raise ValueError(
                "Use a naive datetime in Philippine local time."
            )

        if start.minute or start.second or start.microsecond:
            raise ValueError("Slots must start exactly on the hour.")

        total = pricing.quote(court, start)

        if type(total) is not int or total <= 0 or total % 2:
            raise ValueError("Quote must be positive even centavos.")

        self._total = total
        self._paid = 0
        self._references: list[str] = []
        self._closed = False

    @property
    def total(self) -> int:
        """Return the read-only frozen price in centavos."""
        return self._total

    @property
    def paid(self) -> int:
        """Return payments less recorded refunds in centavos."""
        return self._paid

    @property
    def references(self) -> tuple[str, ...]:
        """Return an immutable snapshot of payment references."""
        return tuple(self._references)

    def record(self, amount: int, reference: str) -> None:
        """Record verified funds with a minimum 50% first payment.

        Malformed inputs raise ValueError.
        Business-rule violations raise BookingError.
        Failed operations leave state unchanged.
        References must be unique within this account.
        """
        if type(amount) is not int or amount <= 0:
            raise ValueError("Amount must be positive integer centavos.")

        if not isinstance(reference, str) or not reference.strip():
            raise ValueError("Payment reference must be a nonempty string.")

        reference = reference.strip()

        if self._closed:
            raise BookingError("This payment account is closed.")

        if reference in self._references:
            raise BookingError(
                "This payment reference has already been used."
            )

        if self._paid == 0 and amount < self._total // 2:
            raise BookingError(
                "The first payment must cover the 50% deposit."
            )

        if self._paid + amount > self._total:
            raise BookingError("Payment exceeds the remaining balance.")

        self._paid += amount
        self._references.append(reference)

    def close(self, refund: bool) -> int:
        """Close once and return the recorded refund in centavos.

        True records a full refund and resets paid to zero.
        False retains paid, such as for a forfeited deposit.
        Raise ValueError for non-bool input.
        Raise BookingError if already closed.

        Eligibility is decided elsewhere; this does not transfer money.
        """
        if type(refund) is not bool:
            raise ValueError("Refund must be True or False.")

        if self._closed:
            raise BookingError("This payment account is already closed.")

        refunded = self._paid if refund else 0

        if refund:
            self._paid = 0

        self._closed = True
        return refunded

    def __str__(self) -> str:
        """Return a readable payment summary."""
        return f"Paid {self._paid} of {self._total} centavos"