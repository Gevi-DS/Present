import unittest
from datetime import datetime, timedelta, timezone

from contracts import BookingError, IBookingPolicy
from booking_policy import BookingPolicy, RegularPolicy, FlexiblePolicy


class BookingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 10, 10)
        self.regular = RegularPolicy()
        self.flexible = FlexiblePolicy()

    def test_properties_are_read_only(self):
        cases = (
            (self.regular, "Regular", 24),
            (self.flexible, "Flexible", 6),
        )

        for policy, name, hours in cases:
            self.assertIsInstance(policy, IBookingPolicy)
            self.assertEqual(policy.name, name)
            self.assertEqual(policy.refund_notice_hours, hours)

            with self.assertRaises(AttributeError):
                policy.name = "Changed"

            with self.assertRaises(AttributeError):
                policy.refund_notice_hours = 1

    def test_invalid_constructor_values(self):
        for name in ("", " ", None, 123):
            for policy_class in (RegularPolicy, FlexiblePolicy):
                with self.subTest(name=name, policy=policy_class):
                    with self.assertRaises(ValueError):
                        policy_class(name)

        for hours in (-1, True, 1.5, "24", None):
            with self.subTest(hours=hours):
                with self.assertRaises(ValueError):
                    BookingPolicy("Custom", hours)

    def test_name_normalization_and_string(self):
        policy = RegularPolicy("  Regular  ")

        self.assertEqual(policy.name, "Regular")
        self.assertEqual(
            str(policy),
            "Regular: 24-hour refund notice",
        )

    def test_future_booking_accepted_by_both_policies(self):
        start = self.now + timedelta(hours=1)

        for policy in (self.regular, self.flexible):
            self.assertIsNone(
                policy.validate_booking(start, self.now)
            )

    def test_booking_at_or_before_now_rejected(self):
        for policy in (self.regular, self.flexible):
            for offset in (0, -1):
                start = self.now + timedelta(hours=offset)

                with self.assertRaises(BookingError):
                    policy.validate_booking(start, self.now)

    def test_seven_day_boundary(self):
        start = self.now + timedelta(days=7)

        for policy in (self.regular, self.flexible):
            self.assertIsNone(
                policy.validate_booking(start, self.now)
            )

            # One second beyond the seven-day window.
            with self.assertRaises(BookingError):
                policy.validate_booking(
                    start,
                    self.now - timedelta(seconds=1),
                )

    def test_refund_thresholds(self):
        for policy in (self.regular, self.flexible):
            start = self.now + timedelta(
                hours=policy.refund_notice_hours
            )

            # Exactly at the threshold: eligible.
            self.assertTrue(
                policy.refundable(start, self.now)
            )

            # More notice: eligible.
            self.assertTrue(
                policy.refundable(
                    start,
                    self.now - timedelta(seconds=1),
                )
            )

            # One second less notice: not eligible.
            self.assertFalse(
                policy.refundable(
                    start,
                    self.now + timedelta(seconds=1),
                )
            )

    def test_policies_produce_different_refund_decisions(self):
        start = self.now + timedelta(hours=12)

        self.assertFalse(
            self.regular.refundable(start, self.now)
        )
        self.assertTrue(
            self.flexible.refundable(start, self.now)
        )

    def test_cancellation_at_or_after_start_rejected(self):
        for policy in (self.regular, self.flexible):
            for now in (
                self.now,
                self.now + timedelta(seconds=1),
            ):
                with self.assertRaises(BookingError):
                    policy.refundable(self.now, now)

    def test_invalid_dates_for_both_operations(self):
        invalid_values = (
            None,
            "tomorrow",
            self.now.replace(tzinfo=timezone.utc),
        )

        for policy in (self.regular, self.flexible):
            for method in (
                policy.validate_booking,
                policy.refundable,
            ):
                for value in invalid_values:
                    with self.assertRaises(ValueError):
                        method(value, self.now)

                    with self.assertRaises(ValueError):
                        method(
                            self.now + timedelta(days=1),
                            value,
                        )

                for field in ("minute", "second", "microsecond"):
                    invalid_start = self.now.replace(**{field: 1})

                    with self.assertRaises(ValueError):
                        method(invalid_start, self.now)

    def test_now_can_include_minutes(self):
        start = self.now + timedelta(hours=1)
        now = self.now + timedelta(minutes=30)

        self.assertIsNone(
            self.regular.validate_booking(start, now)
        )

    def test_zero_notice_policy_rejects_started_booking(self):
        policy = BookingPolicy("Custom", 0)

        self.assertTrue(
            policy.refundable(
                self.now + timedelta(hours=1),
                self.now,
            )
        )

        with self.assertRaises(BookingError):
            policy.refundable(self.now, self.now)