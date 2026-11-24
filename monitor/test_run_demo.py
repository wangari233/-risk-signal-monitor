import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import RiskAssessment, Transaction

FIELDS = [
    "corporate", "reference", "type", "amount", "currency",
    "status", "destination", "created_at", "expected_result", "scenario",
]


def good_row(**changes):
    row = {
        "corporate": "Test Corporate",
        "reference": "TXN-000001",
        "type": "COLLECTION",
        "amount": "100.00",
        "currency": "KES",
        "status": "SUCCESSFUL",
        "destination": "0700000000",
        "created_at": "2026-11-02T09:00:00+00:00",
        "expected_result": "LOW",
        "scenario": "test",
    }
    row.update(changes)
    return row


class RunDemoTests(TestCase):
    def run_demo(self, rows, *args):
        """Write the rows to a temporary CSV, run the command, return its output."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rows.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            out = StringIO()
            call_command("run_demo", "--file", str(path), *args, stdout=out)
            return out.getvalue()

    def test_a_clean_row_matches(self):
        output = self.run_demo([good_row()])
        self.assertIn("Matched: 1", output)
        self.assertIn("Rejected: 0", output)

    def test_nothing_is_saved_by_default(self):
        self.run_demo([good_row()])
        self.assertEqual(Transaction.objects.count(), 0)

    def test_keep_saves_the_data(self):
        self.run_demo([good_row()], "--keep")
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(RiskAssessment.objects.count(), 1)

    def test_a_bad_type_is_rejected(self):
        output = self.run_demo([good_row(type="BANANA")], "--keep")
        self.assertIn("REJECTED", output)
        self.assertIn("Rejected: 1", output)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_extra_decimal_places_are_rejected(self):
        output = self.run_demo([good_row(amount="10.005")], "--keep")
        self.assertIn("Rejected: 1", output)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_a_negative_amount_is_rejected(self):
        output = self.run_demo([good_row(amount="-5.00")], "--keep")
        self.assertIn("Rejected: 1", output)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_a_duplicate_reference_is_rejected(self):
        output = self.run_demo([good_row(), good_row()], "--keep")
        self.assertIn("Matched: 1", output)
        self.assertIn("Rejected: 1", output)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_an_unreadable_amount_is_rejected(self):
        output = self.run_demo([good_row(amount="abc")], "--keep")
        self.assertIn("Rejected: 1", output)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_a_mismatch_raises_an_error(self):
        with self.assertRaises(CommandError):
            self.run_demo([good_row(expected_result="HIGH")])    

    def test_the_sample_file_matches_expectations(self):
        out = StringIO()
        call_command("run_demo", stdout=out)
        self.assertIn(
            "Rows: 88 | Matched: 88 | Mismatched: 0 | Rejected: 0", out.getvalue()
        )