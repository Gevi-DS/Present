"""Payment tests using contract fakes."""

import unittest
from datetime import datetime, timezone

from contracts import BookingError, ICourt, IPricing
from payment import PaymentAccount


class FakeCourt(ICourt):
    """Minimal available court for payment tests."""

    @property
    def court_id(self):
        return "FAKE"

    @property
    def name(self):
        return "Fake Court"

    def block_slot(self, start):
        raise BookingError("Closures are not supported by this fake.")

    def require_available(self, start):
        return None


class FakePricing(IPricing):
    """Controllable quote with a record of calls."""

    def __init__(self, rate=40000):
        self.rate = rate
        self.calls = []

    @property
    def name(self):
        return "Fake Pricing"

    @property
    def base_rate(self):
        return self.rate

    def quote(self, court, start, hours=1):
        self.calls.append((court, start, hours))
        court.require_available(start)
        return self.rate


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.court = FakeCourt()
        self.pricing = FakePricing()
        self.start = datetime(2026, 11, 10, 10)

        self.account = PaymentAccount(
            self.pricing,
            self.court,
            self.start,
        )

    def test_quote_is_frozen_and_properties_read_only(self):
        self.assertEqual(
            self.pricing.calls,
            [(self.court, self.start, 1)],
        )

        self.pricing.rate = 60000

        self.assertEqual(self.account.total, 40000)
        self.assertEqual(self.account.paid, 0)

        for field in ("total", "paid", "references"):
            with self.assertRaises(AttributeError):
                setattr(self.account, field, 1)

    def test_deposit_and_remaining_balance(self):
        self.account.record(20000, "DEP-1")
        self.account.record(5000, "PART-1")
        self.account.record(15000, "BAL-1")

        self.assertEqual(self.account.paid, 40000)
        self.assertEqual(
            str(self.account),
            "Paid 40000 of 40000 centavos",
        )

    def test_insufficient_deposit_does_not_change_state(self):
        with self.assertRaises(BookingError):
            self.account.record(19999, "DEP-1")

        self.assertEqual(self.account.paid, 0)
        self.assertEqual(self.account.references, ())

        self.account.record(20000, "DEP-1")
        self.assertEqual(self.account.paid, 20000)

    def test_duplicate_reference_does_not_change_state(self):
        self.account.record(20000, " DEP-1 ")

        with self.assertRaises(BookingError):
            self.account.record(1000, "DEP-1")

        self.assertEqual(self.account.paid, 20000)
        self.assertEqual(self.account.references, ("DEP-1",))

    def test_overpayment_rejected(self):
        with self.assertRaises(BookingError):
            self.account.record(40001, "TOO-MUCH")

        self.account.record(20000, "DEP-1")

        with self.assertRaises(BookingError):
            self.account.record(20001, "TOO-MUCH")

        self.assertEqual(self.account.paid, 20000)
        self.assertEqual(self.account.references, ("DEP-1",))

    def test_references_are_immutable_snapshots(self):
        snapshot = self.account.references
        self.account.record(20000, "DEP-1")

        self.assertEqual(snapshot, ())
        self.assertIsInstance(self.account.references, tuple)

    def test_refund_closes_account(self):
        self.account.record(20000, "DEP-1")

        self.assertEqual(self.account.close(True), 20000)
        self.assertEqual(self.account.paid, 0)
        self.assertEqual(self.account.references, ("DEP-1",))

        with self.assertRaises(BookingError):
            self.account.record(20000, "NEW")

        with self.assertRaises(BookingError):
            self.account.close(True)

    def test_forfeiture_retains_paid_and_closes_account(self):
        self.account.record(20000, "DEP-1")

        self.assertEqual(self.account.close(False), 0)
        self.assertEqual(self.account.paid, 20000)

        with self.assertRaises(BookingError):
            self.account.record(20000, "BAL-1")

        with self.assertRaises(BookingError):
            self.account.close(True)

    def test_invalid_payment_inputs(self):
        for amount in (0, -1, True, 20000.0, "20000"):
            with self.assertRaises(ValueError):
                self.account.record(amount, "DEP-1")

        for reference in ("", " ", None, 123):
            with self.assertRaises(ValueError):
                self.account.record(20000, reference)

        for refund in (1, "yes", None):
            with self.assertRaises(ValueError):
                self.account.close(refund)

        self.assertEqual(self.account.paid, 0)

        self.account.record(40000, "FULL")
        self.assertEqual(self.account.paid, 40000)

    def test_invalid_constructor_inputs(self):
        invalid_dependencies = (
            (object(), self.court),
            (self.pricing, object()),
        )

        for pricing, court in invalid_dependencies:
            with self.assertRaises(ValueError):
                PaymentAccount(pricing, court, self.start)

        invalid_starts = (
            None,
            "tomorrow",
            self.start.replace(minute=1),
            self.start.replace(second=1),
            self.start.replace(microsecond=1),
            self.start.replace(tzinfo=timezone.utc),
        )

        for start in invalid_starts:
            with self.assertRaises(ValueError):
                PaymentAccount(self.pricing, self.court, start)

        for rate in (0, -2, 101, True, 40000.0):
            with self.assertRaises(ValueError):
                PaymentAccount(
                    FakePricing(rate),
                    self.court,
                    self.start,
                )

    def test_unpaid_account_can_close(self):
        self.assertEqual(self.account.close(True), 0)

        with self.assertRaises(BookingError):
            self.account.record(20000, "DEP-1")