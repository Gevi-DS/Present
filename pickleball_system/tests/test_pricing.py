"""Pricing tests using a fake court contract."""

import unittest
from datetime import datetime, timezone

from contracts import BookingError, ICourt
from pricing import StandardPricing, TimeBasedPricing

class FakeCourt(ICourt):
    """Minimal court with controllable availability."""

    def __init__(self):
        self.blocked = set()
        self.checked = []

    @property
    def court_id(self):
        return "FAKE"

    @property
    def name(self):
        return "Fake Court"

    def block_slot(self, start):
        self.blocked.add(start)

    def require_available(self, start):
        self.checked.append(start)

        if start in self.blocked:
            raise BookingError("Unavailable slot.")


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.court = FakeCourt()
        self.start = datetime(2026, 11, 10, 10)
        self.standard = StandardPricing("Standard", 40000)
        self.time_based = TimeBasedPricing("Peak", 40000, 60000)

    def test_standard_quote_uses_court_contract(self):
        result = self.standard.quote(self.court, self.start)

        self.assertEqual(result, 40000)
        self.assertEqual(self.court.checked, [self.start])

    def test_peak_boundaries(self):
        cases = (
            (17, 40000),
            (18, 60000),
            (21, 60000),
            (22, 40000),
        )

        for hour, expected in cases:
            with self.subTest(hour=hour):
                result = self.time_based.quote(
                    self.court,
                    self.start.replace(hour=hour),
                )
                self.assertEqual(result, expected)

    def test_interchangeable_pricing(self):
        start = self.start.replace(hour=18)

        results = [
            policy.quote(self.court, start)
            for policy in (self.standard, self.time_based)
        ]

        self.assertEqual(results, [40000, 60000])

    def test_unavailable_court_rejected(self):
        self.court.block_slot(self.start)

        for policy in (self.standard, self.time_based):
            with self.assertRaises(BookingError):
                policy.quote(self.court, self.start)

    def test_unsupported_durations_rejected(self):
        for policy in (self.standard, self.time_based):
            for hours in (0, -1, 2):
                with self.assertRaises(BookingError):
                    policy.quote(self.court, self.start, hours)

        self.assertEqual(self.court.checked, [])

    def test_constructor_validation(self):
        for name in ("", " ", None, 5):
            with self.assertRaises(ValueError):
                StandardPricing(name, 40000)

        for rate in (0, -2, 101, True, 4.0, "40000"):
            with self.assertRaises(ValueError):
                StandardPricing("Standard", rate)

        for rate in (20000, 60001, True, None, 60000.0):
            with self.assertRaises(ValueError):
                TimeBasedPricing("Peak", 40000, rate)

    def test_properties_and_string(self):
        self.assertEqual(self.standard.name, "Standard")
        self.assertEqual(self.standard.base_rate, 40000)
        self.assertEqual(self.time_based.evening_rate, 60000)

        self.assertEqual(
            str(self.standard),
            "Standard: 40000 centavos/hour",
        )

        for field in ("name", "base_rate", "evening_rate"):
            with self.assertRaises(AttributeError):
                setattr(self.time_based, field, 1)

    def test_malformed_arguments(self):
        for policy in (self.standard, self.time_based):
            with self.assertRaises(ValueError):
                policy.quote(object(), self.start)

            for hours in (True, 1.0, "1", None):
                with self.assertRaises(ValueError):
                    policy.quote(self.court, self.start, hours)

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
                    policy.quote(self.court, start)