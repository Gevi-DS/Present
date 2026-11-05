import unittest
from datetime import datetime, timezone
from contracts import BookingError, ICourt
from court import Court


class CourtTests(unittest.TestCase):
    def setUp(self):
        self.court = Court("C1", "Court One")
        self.slot = datetime(2026, 11, 10, 10)

    def test_properties_and_string(self):
        self.assertIsInstance(self.court, ICourt)
        self.assertEqual(self.court.court_id, "C1")
        self.assertEqual(self.court.name, "Court One")
        self.assertEqual(str(self.court), "C1: Court One")
        for field in ("court_id", "name"):
            with self.assertRaises(AttributeError):
                setattr(self.court, field, "replacement")

    def test_constructor_validation(self):
        for args in [("", "Name"), (1, "Name"), ("C1", " "),
                     ("C1", None), ("C1", "Name", True, 22),
                     ("C1", "Name", 8, 8), ("C1", "Name", -1, 22),
                     ("C1", "Name", 8, 25)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                Court(*args)

    def test_operating_boundaries(self):
        for hour in (6, 21):
            self.assertIsNone(self.court.require_available(self.slot.replace(hour=hour)))
        for hour in (5, 22):
            with self.assertRaises(BookingError):
                self.court.require_available(self.slot.replace(hour=hour))
        late = Court("C2", "Late Court", 8, 24)
        self.assertIsNone(late.require_available(self.slot.replace(hour=23)))

    def test_maintenance_blocks_only_selected_slot(self):
        self.court.block_slot(self.slot)
        with self.assertRaises(BookingError):
            self.court.require_available(self.slot)
        self.assertIsNone(self.court.require_available(self.slot.replace(hour=11)))
        self.assertIsNone(self.court.require_available(self.slot.replace(day=11)))

    def test_duplicate_closure_preserves_state(self):
        self.court.block_slot(self.slot)
        before = self.court.blocked_slots
        with self.assertRaises(BookingError):
            self.court.block_slot(self.slot)
        self.assertEqual(self.court.blocked_slots, before)

    def test_closure_outside_hours_preserves_state(self):
        with self.assertRaises(BookingError):
            self.court.block_slot(self.slot.replace(hour=23))
        self.assertEqual(self.court.blocked_slots, frozenset())

    def test_immutable_snapshot(self):
        snapshot = self.court.blocked_slots
        self.court.block_slot(self.slot)
        self.assertEqual(snapshot, frozenset())
        with self.assertRaises(AttributeError):
            snapshot.add(self.slot)

    def test_malformed_slots(self):
        for value in ("10:00", None, self.slot.replace(minute=1),
                      self.slot.replace(second=1), self.slot.replace(microsecond=1),
                      self.slot.replace(tzinfo=timezone.utc)):
            for operation in (self.court.block_slot, self.court.require_available):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    operation(value)
        self.assertEqual(self.court.blocked_slots, frozenset())