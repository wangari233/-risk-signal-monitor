"""Generate synthetic demo transactions for the risk monitor.

Everything here is made up. A fixed seed and a fixed start time mean the same
file is produced every time. Run it from the project root:

    python scripts/generate_data.py
"""

import csv
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

SEED = 42
START = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "sample_transactions.csv"
FIELDS = [
    "corporate", "reference", "type", "amount", "currency",
    "status", "destination", "created_at", "expected_result", "scenario",
]


def money(cents):
    """Whole cents to a string like '100.00', never through a float."""
    return f"{Decimal(cents) / 100:.2f}"


def add(rows, corporate, type_, status, cents, when, scenario, expected):
    rows.append({
        "corporate": corporate,
        "type": type_,
        "status": status,
        "amount": money(cents),
        "currency": "KES",
        "destination": "0700000000",
        "created_at": when.isoformat(),
        "scenario": scenario,
        "expected_result": expected,
    })


def normal_activity(rows, rng):
    """Steady collections and small payouts that should never be flagged."""
    for n in range(1, 4):
        corporate = f"Demo Corporate {n:02d}"
        for day in range(5):
            day_start = START + timedelta(days=day)
            for hours in (1, 3, 6):  # 09:00, 11:00 and 14:00
                add(rows, corporate, "COLLECTION", "SUCCESSFUL",
                    rng.randint(9000, 11000),
                    day_start + timedelta(hours=hours), "normal", "LOW")
            add(rows, corporate, "PAYOUT", "SUCCESSFUL", 5000,
                day_start + timedelta(hours=8), "normal", "LOW")


def repeated_failures(rows):
    """Demo Corporate 04: three failures in a row, then a success."""
    corporate = "Demo Corporate 04"
    start = START + timedelta(days=1, hours=2)  # 10:00 on the second day
    for step, status, expected in (
        (0, "FAILED", "LOW"),
        (3, "FAILED", "LOW"),
        (6, "FAILED", "REVIEW"),      # the 3rd failure in 10 minutes
        (8, "SUCCESSFUL", "REVIEW"),  # a success after 3 failures
    ):
        add(rows, corporate, "COLLECTION", status, 10000,
            start + timedelta(minutes=step), "repeated_failures", expected)


def unusual_amount(rows):
    """Demo Corporate 05: five steady collections, then a much larger one."""
    corporate = "Demo Corporate 05"
    start = START + timedelta(days=2)  # 08:00 on the third day
    for hour in range(5):
        add(rows, corporate, "COLLECTION", "SUCCESSFUL", 10000,
            start + timedelta(hours=hour), "unusual_amount", "LOW")
    add(rows, corporate, "COLLECTION", "SUCCESSFUL", 60000,
        start + timedelta(hours=5), "unusual_amount", "REVIEW")


def rapid_funding(rows):
    """Demo Corporate 06: a deposit, then most of it paid out quickly."""
    corporate = "Demo Corporate 06"
    start = START + timedelta(days=3, hours=1)  # 09:00 on the fourth day
    add(rows, corporate, "COLLECTION", "SUCCESSFUL", 100000,
        start, "rapid_funding", "LOW")
    add(rows, corporate, "PAYOUT", "SUCCESSFUL", 90000,
        start + timedelta(minutes=20), "rapid_funding", "REVIEW")


def combined_risk(rows):
    """Demo Corporate 07: failures, then a large payout of a recent deposit."""
    corporate = "Demo Corporate 07"
    start = START + timedelta(days=3, hours=6)  # 14:00 on the fourth day
    add(rows, corporate, "COLLECTION", "SUCCESSFUL", 100000,
        start, "combined_risk", "LOW")
    for minutes, status, expected in (
        (10, "FAILED", "LOW"),
        (12, "FAILED", "LOW"),
        (14, "FAILED", "REVIEW"),      # the 3rd failure in 10 minutes
        (16, "SUCCESSFUL", "HIGH"),    # repeated failures + rapid funding
    ):
        add(rows, corporate, "PAYOUT", status, 90000,
            start + timedelta(minutes=minutes), "combined_risk", expected)


def near_misses(rows):
    """Demo Corporates 08, 09 and 10: just under each threshold."""
    day = START + timedelta(days=4)

    # 08: only two failures before a success, one short of the limit of 3
    start = day + timedelta(hours=1)
    for minutes, status in ((0, "FAILED"), (3, "FAILED"), (6, "SUCCESSFUL")):
        add(rows, "Demo Corporate 08", "COLLECTION", status, 10000,
            start + timedelta(minutes=minutes), "near_miss_failures", "LOW")

    # 09: a payout of 799.90 is 79.99% of the deposit, just under 80%
    start = day + timedelta(hours=3)
    add(rows, "Demo Corporate 09", "COLLECTION", "SUCCESSFUL", 100000,
        start, "near_miss_funding", "LOW")
    add(rows, "Demo Corporate 09", "PAYOUT", "SUCCESSFUL", 79990,
        start + timedelta(minutes=20), "near_miss_funding", "LOW")

    # 10: exactly 5 times the average of 100.00, which does not fire
    start = day + timedelta(hours=5)
    for hour in range(5):
        add(rows, "Demo Corporate 10", "COLLECTION", "SUCCESSFUL", 10000,
            start + timedelta(hours=hour), "near_miss_amount", "LOW")
    add(rows, "Demo Corporate 10", "COLLECTION", "SUCCESSFUL", 50000,
        start + timedelta(hours=5), "near_miss_amount", "LOW")


def main():
    rng = random.Random(SEED)
    rows = []
    normal_activity(rows, rng)
    repeated_failures(rows)
    unusual_amount(rows)
    rapid_funding(rows)
    combined_risk(rows)
    near_misses(rows)

    # Same timezone and format, so the text sorts in time order.
    rows.sort(key=lambda r: r["created_at"])
    for number, r in enumerate(rows, start=1):
        r["reference"] = f"TXN-{number:06d}"

    OUTPUT.parent.mkdir(exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
