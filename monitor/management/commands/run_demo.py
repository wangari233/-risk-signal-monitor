"""Run the synthetic demo transactions through the risk monitor.

Reads a CSV, validates each row, saves it, assesses it, and compares the
monitor's result with the row's expected_result.

    python manage.py run_demo          (checks everything, then rolls back)
    python manage.py run_demo --keep   (keeps the data so the admin can show it)
"""

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from monitor.models import Corporate, Transaction
from monitor.scoring import assess_transaction

DEFAULT_FILE = Path(settings.BASE_DIR) / "data" / "sample_transactions.csv"


def process_row(row):
    """Validate, save and assess one CSV row. Returns the RiskAssessment.

    Raises ValidationError if the row is not acceptable.
    """
    try:
        amount = Decimal(row["amount"])  # never float: exact money
        created_at = datetime.fromisoformat(row["created_at"])
    except (InvalidOperation, ValueError, KeyError, TypeError) as error:
        raise ValidationError(f"Unreadable amount or time: {error!r}") from error
    if created_at.tzinfo is None:
        raise ValidationError("created_at must include a timezone")

    corporate, _ = Corporate.objects.get_or_create(name=row["corporate"])
    txn = Transaction(
        corporate=corporate,
        reference=row["reference"],
        type=row["type"],
        status=row["status"],
        amount=amount,
        currency=row["currency"],
        destination=row["destination"],
        created_at=created_at,
    )
    txn.full_clean()  # rejects a bad type or status, extra decimals, duplicates
    txn.save()
    return assess_transaction(txn)


class Command(BaseCommand):
    help = "Run the synthetic demo transactions through the risk monitor."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT_FILE), help="CSV to read")
        parser.add_argument(
            "--keep", action="store_true",
            help="keep the data instead of rolling it back",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        rows = matched = mismatched = rejected = 0
        with transaction.atomic():
            with path.open(newline="", encoding="utf-8") as handle:
                for line, row in enumerate(csv.DictReader(handle), start=2):
                    rows += 1
                    try:
                        assessment = process_row(row)
                    except ValidationError as error:
                        rejected += 1
                        self.stdout.write(
                            f"line {line}: REJECTED {row.get('reference')}: "
                            + "; ".join(error.messages)
                        )
                        continue

                    expected = row.get("expected_result", "")
                    ok = assessment.result == expected
                    matched += ok
                    mismatched += not ok
                    rules = ", ".join(
                        r.rule_code for r in assessment.triggered_rules.all()
                    )
                    self.stdout.write(
                        f"{row['reference']}  {row['corporate']:<18} "
                        f"{row['type']:<10} {row['status']:<10} {row['amount']:>10}  "
                        f"score {assessment.score:>3}  {assessment.result:<6} "
                        f"expected {expected:<6} {'ok' if ok else 'MISMATCH'}  {rules}"
                    )

            if not options["keep"]:
                transaction.set_rollback(True)

        self.stdout.write(
            f"Rows: {rows} | Matched: {matched} | Mismatched: {mismatched} "
            f"| Rejected: {rejected}"
        )
        self.stdout.write(
            "Data kept." if options["keep"] else "Rolled back: nothing was saved."
        )
        if mismatched:
            raise CommandError(f"{mismatched} row(s) did not match expected_result")
