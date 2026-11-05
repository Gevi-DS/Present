# Shared work: Gevi, Harry, Michael, and Timothy
"""Run a repeatable booking story using all five modules."""

from datetime import datetime, timedelta

from contracts import BookingError
from court import Court
from booking_policy import RegularPolicy, FlexiblePolicy
from pricing import StandardPricing, TimeBasedPricing
from payment import PaymentAccount
from reservation import ReservationService


def pesos(centavos: int) -> str:
    """Format nonnegative integer centavos as pesos."""
    return f"PHP {centavos // 100:,}.{centavos % 100:02d}"

def run_demo() -> None:
    """Demonstrate booking rules, payments, cancellation, and completion."""
    # Fixed dates keep the demonstration repeatable.
    now = datetime(2026, 11, 10, 10)
    start = datetime(2026, 11, 12, 18)

    court = Court("C1", "Court One")

    time_based = TimeBasedPricing(
        "Time-based",
        40000,
        60000,
    )

    regular = RegularPolicy()

    service = ReservationService(
        "Pickleball Center",
        regular,
        time_based,
    )

    print("=== PICKLEBALL COURT RESERVATION ===")

    print("1. Facility rules")
    print("Courts are open from 06:00 to 22:00.")
    print("Bookings last one hour.")
    print("Daytime rate: PHP 400.00.")
    print("Evening rate from 18:00 to 21:00: PHP 600.00.")
    print("A 50% deposit is required to confirm a booking.")
    print("Cancellations need 24 hours' notice for a refund.")

    print("\n2. Maria requests Court One, November 12, 18:00-19:00")

    maria_payment = PaymentAccount(time_based, court, start)

    service.request(
        "B001",
        "Maria",
        court,
        start,
        maria_payment,
        now,
    )

    print(f"Booking B001: {service.status('B001')}")
    print(f"Total: {pesos(maria_payment.total)}")
    print(f"Required deposit: {pesos(maria_payment.total // 2)}")

    try:
        maria_payment.record(10000, "MARIA-TOO-SMALL")
    except BookingError as error:
        print(f"Handled insufficient deposit: {error}")
    else:
        raise AssertionError(
            "An insufficient deposit should be rejected."
        )

    maria_payment.record(30000, "MARIA-DEPOSIT")
    service.confirm("B001", now)

    print(f"Deposit recorded: {pesos(maria_payment.paid)}")
    print(f"Booking B001: {service.status('B001')}")

    print("\n3. Ben requests the same court and time")

    ben_payment = PaymentAccount(time_based, court, start)

    try:
        service.request(
            "B002",
            "Ben",
            court,
            start,
            ben_payment,
            now,
        )
    except BookingError as error:
        print(f"Handled booking conflict: {error}")
    else:
        raise AssertionError(
            "A conflicting booking should be rejected."
        )

    print("No payment was collected from Ben.")

    print("\n4. Ben books 19:00-20:00 instead, then cancels early")

    ben_start = start + timedelta(hours=1)
    ben_payment = PaymentAccount(time_based, court, ben_start)

    service.request(
        "B002",
        "Ben",
        court,
        ben_start,
        ben_payment,
        now,
    )

    ben_payment.record(30000, "BEN-DEPOSIT")
    service.confirm("B002", now)

    cancel_time = ben_start - timedelta(hours=24)
    refunded = service.cancel("B002", cancel_time)

    print(f"Cancellation time: {cancel_time:%Y-%m-%d %H:%M}")
    print(f"Recorded refund: {pesos(refunded)}")
    print(f"Booking B002: {service.status('B002')}")

    print("\n5. Maria arrives at 18:00 on November 12")

    try:
        service.check_in("B001", start)
    except BookingError as error:
        print(f"Handled unpaid balance: {error}")
    else:
        raise AssertionError(
            "Check-in with an unpaid balance should fail."
        )

    balance = maria_payment.total - maria_payment.paid
    maria_payment.record(balance, "MARIA-BALANCE")
    service.check_in("B001", start)

    print(f"Balance recorded: {pesos(balance)}")
    print(f"Booking B001: {service.status('B001')}")

    print("\n6. Maria finishes at 19:00")

    service.complete("B001", start + timedelta(hours=1))

    print(f"Booking B001: {service.status('B001')}")
    print(
        f"Booking records: {len(service)} "
        "(including cancelled bookings)"
    )
    print("\n7. Compare policies: cancellation 12 hours before play")
    for policy in (RegularPolicy(), FlexiblePolicy()):
        comparison = ReservationService("Policy comparison", policy, time_based)
        payment = PaymentAccount(time_based, court, start)
        comparison.request("P001", "Alex", court, start, payment, now)
        payment.record(payment.total // 2, "ALEX-DEPOSIT")
        comparison.confirm("P001", now)
        refund = comparison.cancel("P001", start - timedelta(hours=12))
        print(f"{policy.name}: refund {pesos(refund)}")

    print("\n8. Compare pricing for the same 18:00 slot")
    for pricing in (StandardPricing("Standard", 40000), time_based):
        payment = PaymentAccount(pricing, court, start)
        print(f"{pricing.name}: total {pesos(payment.total)}")
    print("Demo completed successfully.")
def create_practice_session():
    """Create fresh objects for the interactive practice session."""
    courts = {
        "C1": Court("C1", "Court One"),
        "C2": Court("C2", "Court Two"),
    }

    pricing = TimeBasedPricing("Peak", 40000, 60000)
    service = ReservationService(
        "Pickleball Center",
        RegularPolicy(),
        pricing,
    )

    return courts, pricing, service


def create_payment(pricing, court, start):
    """Create a fresh payment account for a booking."""
    return PaymentAccount(pricing, court, start)


if __name__ == "__main__":
    run_demo()

