# Author: Canoy, Gevi P. (module: court)
"""Court operating hours and one-hour maintenance/weather closures."""
from datetime import datetime
from contracts import BookingError, ICourt


class Court(ICourt):
    """Court operating hours and one-hour maintenance closures."""

    def __init__(self, court_id: str, 
                 name: str,
                 opening_hour: int = 6, 
                 closing_hour: int = 22):
        """Create a court; reject invalid names or hours with ValueError."""
        if not isinstance(court_id, str) or not court_id.strip():
            raise ValueError("Court ID must be a nonempty string.")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Court name must be a nonempty string.")
        if (type(opening_hour) is not int or type(closing_hour) is not int
                or not 0 <= opening_hour < closing_hour <= 24):
            raise ValueError("Hours must satisfy 0 <= opening < closing <= 24.")
        self._court_id = court_id.strip()
        self._name = name.strip()
        self._opening_hour = opening_hour
        self._closing_hour = closing_hour
        self._blocked_slots: set[datetime] = set()

    @property
    def court_id(self) -> str:
        """Return the read-only court ID."""
        return self._court_id

    @property
    def name(self) -> str:
        """Return the read-only display name."""
        return self._name

    @property
    def blocked_slots(self) -> frozenset[datetime]:
        """Return an immutable snapshot of maintenance slots."""
        return frozenset(self._blocked_slots)

    def _validate_slot(self, start: datetime) -> None:
        if not isinstance(start, datetime) or start.tzinfo is not None:
            raise ValueError("Use a naive datetime in Philippine local time.")
        if start.minute or start.second or start.microsecond:
            raise ValueError("Slots must start exactly on the hour.")

    def _require_open_hours(self, start: datetime) -> None:
        if not self._opening_hour <= start.hour < self._closing_hour:
            raise BookingError("The slot is outside court operating hours.")

    def block_slot(self, start: datetime) -> None:
        """Block one hour; reject duplicate closures or outside-hours slots."""
        self._validate_slot(start)
        self._require_open_hours(start)
        if start in self._blocked_slots:
            raise BookingError("This slot is already blocked for maintenance.")
        self._blocked_slots.add(start)

    def require_available(self, start: datetime) -> None:
        """Reject closed or blocked slots with BookingError.

        Malformed starts raise ValueError. Reservation conflicts are handled
        separately by the reservation service.
        """
        self._validate_slot(start)
        self._require_open_hours(start)
        if start in self._blocked_slots:
            raise BookingError("The court is closed for maintenance.")

    def __str__(self) -> str:
        """Return a short court label for the demo."""
        return f"{self._court_id}: {self._name}"


