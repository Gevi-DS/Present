"""Reservation tests use only fake teammate contracts."""

import unittest
from datetime import datetime, timedelta, timezone

from contracts import (
    BookingError,
    ICourt,
    IBookingPolicy,
    IPricing,
    IPayment,
)
from reservation import ReservationService


class FakeCourt(ICourt):
    def __init__(self, court_id="C1"):
        self._id = court_id
        self.blocked = set()

    @property
    def court_id(self):
        return self._id

    @property
    def name(self):
        return "Fake Court"

    def block_slot(self, start):
        self.blocked.add(start)

    def require_available(self, start):
        if start in self.blocked:
            raise BookingError("Unavailable court.")


class FakePolicy(IBookingPolicy):
    def __init__(self):
        self.allow_booking = True
        self.allow_refund = True
        self.calls = []

    @property
    def name(self):
        return "Fake Policy"

    @property
    def refund_notice_hours(self):
        return 24

    def validate_booking(self, start, now):
        self.calls.append((start, now))

        if not self.allow_booking:
            raise BookingError("Policy rejected booking.")

    def refundable(self, start, now):
        return self.allow_refund


class FakePricing(IPricing):
    @property
    def name(self):
        return "Fake Pricing"

    @property
    def base_rate(self):
        return 40000

    def quote(self, court, start, hours=1):
        return self.base_rate


class FakePayment(IPayment):
    def __init__(self, total=40000, paid=0):
        self._total = total
        self._paid = paid
        self.closed = False
        self.fail_close = False

    @property
    def total(self):
        return self._total

    @property
    def paid(self):
        return self._paid

    def record(self, amount, reference):
        self._paid += amount

    def close(self, refund):
        if self.fail_close or self.closed:
            raise BookingError("Cannot close account.")

        result = self._paid if refund else 0

        if refund:
            self._paid = 0

        self.closed = True
        return result


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 10, 10)
        self.start = self.now + timedelta(days=2)
        self.court = FakeCourt()
        self.policy = FakePolicy()
        self.pricing = FakePricing()

        self.service = ReservationService(
            "Facility",
            self.policy,
            self.pricing,
        )

    def add(self, booking_id="B1", paid=0, court=None):
        payment = FakePayment(paid=paid)

        self.service.request(
            booking_id,
            "Maria",
            court or self.court,
            self.start,
            payment,
            self.now,
        )

        return payment

    def test_request_properties_and_snapshot(self):
        snapshot = self.service.booking_ids
        self.add()

        self.assertEqual(snapshot, ())
        self.assertEqual(self.service.booking_ids, ("B1",))
        self.assertEqual(self.service.name, "Facility")
        self.assertEqual(self.service.status("B1"), "pending")
        self.assertEqual(len(self.service), 1)

        self.assertEqual(
            self.policy.calls,
            [(self.start, self.now)],
        )

        for field in ("name", "booking_ids"):
            with self.assertRaises(AttributeError):
                setattr(self.service, field, "replacement")

    def test_invalid_constructor_and_request(self):
        invalid_constructors = (
            (" ", self.policy, self.pricing),
            ("Name", object(), self.pricing),
            ("Name", self.policy, object()),
        )

        for name, policy, pricing in invalid_constructors:
            with self.assertRaises(ValueError):
                ReservationService(name, policy, pricing)

        base = [
            "B1",
            "Maria",
            self.court,
            self.start,
            FakePayment(),
            self.now,
        ]

        invalid_arguments = (
            (0, ""),
            (1, " "),
            (2, object()),
            (4, object()),
            (3, self.start.replace(minute=1)),
            (5, "now"),
            (5, self.now.replace(tzinfo=timezone.utc)),
        )

        for index, value in invalid_arguments:
            args = base.copy()
            args[index] = value

            with self.assertRaises(ValueError):
                self.service.request(*args)

        self.assertEqual(len(self.service), 0)

    def test_duplicate_id_reused_payment_and_quote_mismatch(self):
        payment = self.add()

        with self.assertRaises(BookingError):
            self.add()

        with self.assertRaises(BookingError):
            self.service.request(
                "B2", "Maria", self.court,
                self.start, payment, self.now,
            )

        with self.assertRaises(BookingError):
            self.service.request(
                "B3", "Maria", self.court,
                self.start, FakePayment(total=60000), self.now,
            )

        self.assertEqual(self.service.booking_ids, ("B1",))

    def test_policy_and_court_rejection_leave_no_record(self):
        self.policy.allow_booking = False

        with self.assertRaises(BookingError):
            self.add()

        self.policy.allow_booking = True
        self.court.block_slot(self.start)

        with self.assertRaises(BookingError):
            self.add()

        self.assertEqual(len(self.service), 0)

    def test_deposit_required_and_repeat_confirmation_rejected(self):
        payment = self.add()

        with self.assertRaises(BookingError):
            self.service.confirm("B1", self.now)

        self.assertEqual(self.service.status("B1"), "pending")

        payment.record(20000, "DEP")
        self.service.confirm("B1", self.now)

        with self.assertRaises(BookingError):
            self.service.confirm("B1", self.now)

    def test_pending_requests_compete_at_confirmation(self):
        self.add("B1", paid=20000)
        self.add("B2", paid=20000)

        self.service.confirm("B1", self.now)

        with self.assertRaises(BookingError):
            self.service.confirm("B2", self.now)

        self.assertEqual(self.service.status("B2"), "pending")

        # Matching court IDs represent the same physical court.
        with self.assertRaises(BookingError):
            self.add("B3", court=FakeCourt("C1"))

        # A different court can be booked at the same time.
        self.add("B4", paid=20000, court=FakeCourt("C2"))
        self.service.confirm("B4", self.now)

        self.assertEqual(self.service.status("B4"), "confirmed")

    def test_confirmation_rechecks_policy_and_court(self):
        self.add(paid=20000)
        self.policy.allow_booking = False

        with self.assertRaises(BookingError):
            self.service.confirm("B1", self.now)

        self.policy.allow_booking = True
        self.court.block_slot(self.start)

        with self.assertRaises(BookingError):
            self.service.confirm("B1", self.now)

        self.assertEqual(self.service.status("B1"), "pending")

    def test_pending_cancellation_refunds_despite_policy(self):
        payment = self.add(paid=20000)
        self.policy.allow_refund = False

        self.assertEqual(
            self.service.cancel("B1", self.now),
            20000,
        )
        self.assertTrue(payment.closed)
        self.assertEqual(self.service.status("B1"), "cancelled")

        with self.assertRaises(BookingError):
            self.service.cancel("B1", self.now)

    def test_confirmed_cancellation_uses_policy_and_releases_slot(self):
        for refund in (True, False):
            with self.subTest(refund=refund):
                self.setUp()

                payment = self.add(paid=20000)
                self.service.confirm("B1", self.now)
                self.policy.allow_refund = refund

                expected = 20000 if refund else 0

                self.assertEqual(
                    self.service.cancel("B1", self.now),
                    expected,
                )
                self.assertEqual(
                    payment.paid,
                    0 if refund else 20000,
                )

                self.add("B2", paid=20000)
                self.service.confirm("B2", self.now)

    def test_failed_closure_preserves_confirmed_booking(self):
        payment = self.add(paid=20000)
        self.service.confirm("B1", self.now)
        payment.fail_close = True

        with self.assertRaises(BookingError):
            self.service.cancel("B1", self.now)

        self.assertEqual(self.service.status("B1"), "confirmed")

        with self.assertRaises(BookingError):
            self.add("B2")

    def test_cancellation_at_start_rejected(self):
        payment = self.add(paid=20000)

        with self.assertRaises(BookingError):
            self.service.cancel("B1", self.start)

        self.assertFalse(payment.closed)
        self.assertEqual(self.service.status("B1"), "pending")

    def test_check_in_requires_confirmation_balance_and_slot(self):
        payment = self.add(paid=20000)

        with self.assertRaises(BookingError):
            self.service.check_in("B1", self.start)

        self.service.confirm("B1", self.now)

        with self.assertRaises(BookingError):
            self.service.check_in("B1", self.start)

        payment.record(20000, "BAL")

        for now in (
            self.start - timedelta(seconds=1),
            self.start + timedelta(hours=1),
        ):
            with self.assertRaises(BookingError):
                self.service.check_in("B1", now)

        self.service.check_in("B1", self.start)

        self.assertEqual(self.service.status("B1"), "checked_in")

        with self.assertRaises(BookingError):
            self.service.check_in("B1", self.start)

    def test_completion_requires_check_in_and_end(self):
        self.add(paid=40000)
        self.service.confirm("B1", self.now)
        end = self.start + timedelta(hours=1)

        with self.assertRaises(BookingError):
            self.service.complete("B1", end)

        self.service.check_in("B1", self.start)

        with self.assertRaises(BookingError):
            self.service.complete(
                "B1",
                end - timedelta(seconds=1),
            )

        self.service.complete("B1", end)

        self.assertEqual(self.service.status("B1"), "completed")

        with self.assertRaises(BookingError):
            self.service.complete("B1", end)

    def test_unknown_ids_and_malformed_times(self):
        with self.assertRaises(BookingError):
            self.service.status("missing")

        with self.assertRaises(ValueError):
            self.service.status(" ")

        self.add()

        for method in (
            self.service.confirm,
            self.service.cancel,
            self.service.check_in,
            self.service.complete,
        ):
            with self.assertRaises(BookingError):
                method("missing", self.now)

            with self.assertRaises(ValueError):
                method("B1", "now")