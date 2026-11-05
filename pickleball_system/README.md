# Pickleball Court Reservation System

## Status
All five modules are implemented. The integrated booking demo runs
successfully, and all 53 unit tests pass. The initial contract was
approved at the October 29 checkpoint.

## Scenario
Staff manage one-hour pickleball reservations at one facility. Customers request
slots in person or by phone and staff verify payments externally. A 50% deposit
confirms an available slot, and the balance is required at check-in. The console
program records payments and refunds but does not transfer money.

## Meet the Team

| Owner | Module | Contract ABC | Main classes |
|---|---|---|---|
| Gevi | court | ICourt | Court |
| Harry | booking_policy | IBookingPolicy | BookingPolicy, RegularPolicy, FlexiblePolicy |
| Michael | pricing | IPricing | StandardPricing, TimeBasedPricing |
| Timothy | payment | IPayment | PaymentAccount |
| Gevi | reservation | IReservationService | ReservationService |

## Where polymorphism appears
1. **Booking policies**: `RegularPolicy` and `FlexiblePolicy` implement `IBookingPolicy`. `ReservationService` accepts either policy without changing its code. They require 24 hours and 6 hours of cancellation notice, respectively, for a refund.
2. **Pricing**: `StandardPricing` and `TimeBasedPricing` implement `IPricing`. `PaymentAccount` and `ReservationService` accept either pricing strategy. `StandardPricing` uses a fixed rate; `TimeBasedPricing` applies an evening rate.


## Requirements
Python 3.10 or newer, standard library only. No packages need installation.

## Commands
Run from the folder containing main.py:

```sh
python main.py
python -m unittest discover tests
```

## Contract change log

Contract keeper: Gevi Canoy. After the checkpoint, only Gevi edits
contracts, with agreement from all four members.

| Date | Change | Agreed by |
|---|---|---|
| 29/10/2026 | Initial contract approved at checkpoint | All the members |


## AI assistance
The group used OpenAI ChatGPT/Codex to help organize and clarify the code, making it easier for team members to understand and follow. It was also used to improve the structure and readability of project documentation, particularly the README, so the information would be more organized and easier for readers to understand. 


## Change Log
**Draft v0.1 — 29/10/2026:** Initial contract approved at the checkpoint and agreed to by all four members.

**Draft v0.2 — 30/10/2026:** Implemented the five modules, unit tests, and integrated booking demonstration.

**Draft v0.3 — 30/10/2026:** Clarified contract documentation, added policy and pricing comparisons, and removed OutdoorCourt to focus on indoor courts.

**Version 1.0 — 3/11/2026:** Completed the indoor court reservation workflow, verified all 53 tests pass, and finalized the documentation for submission and demonstration.