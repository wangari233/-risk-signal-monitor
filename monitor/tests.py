from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from . import rule_settings
from .models import (
    Corporate,
    RiskAssessment,
    SubmissionLog,
    Transaction,
    TriggeredRule,
)
from .rules import RuleResult, check_repeated_failures
from .scoring import assess_transaction


class RiskModelTests(TestCase):
    def setUp(self):
        self.corporate = Corporate.objects.create(name="Corporate A")

    def make_transaction(self, reference):
        return Transaction.objects.create(
            corporate=self.corporate,
            reference=reference,
            type=Transaction.Type.PAYOUT,
            status=Transaction.Status.SUCCESSFUL,
            amount=Decimal("500.00"),
        )

    def make_assessment(self, reference="TXN-000001", score=0):
        return RiskAssessment.objects.create(
            transaction=self.make_transaction(reference),
            score=score,
            result=RiskAssessment.result_for(score),
        )

    def test_result_for_covers_every_band_edge(self):
        self.assertEqual(RiskAssessment.result_for(0), RiskAssessment.Result.LOW)
        self.assertEqual(RiskAssessment.result_for(24), RiskAssessment.Result.LOW)
        self.assertEqual(RiskAssessment.result_for(25), RiskAssessment.Result.REVIEW)
        self.assertEqual(RiskAssessment.result_for(59), RiskAssessment.Result.REVIEW)
        self.assertEqual(RiskAssessment.result_for(60), RiskAssessment.Result.HIGH)
        self.assertEqual(RiskAssessment.result_for(100), RiskAssessment.Result.HIGH)

    def test_assessment_result_matches_its_score(self):
        assessment = self.make_assessment(score=95)
        self.assertEqual(assessment.result, RiskAssessment.Result.HIGH)

    def test_score_above_100_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_assessment(score=101)

    def test_scores_0_and_100_are_accepted(self):
        low = self.make_assessment(reference="TXN-LOW", score=0)
        high = self.make_assessment(reference="TXN-HIGH", score=100)
        self.assertEqual(low.score, 0)
        self.assertEqual(high.score, 100)

    def test_duplicate_rule_on_one_assessment_is_rejected(self):
        assessment = self.make_assessment()
        TriggeredRule.objects.create(
            assessment=assessment,
            rule_code="DUPLICATE_REF",
            points=40,
            reason="Reference submitted twice",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TriggeredRule.objects.create(
                    assessment=assessment,
                    rule_code="DUPLICATE_REF",
                    points=40,
                    reason="Same rule recorded again",
                )

    def test_duplicate_submission_references_are_allowed(self):
        SubmissionLog.objects.create(reference="TXN-000001", accepted=True)
        SubmissionLog.objects.create(reference="TXN-000001", accepted=False)
        count = SubmissionLog.objects.filter(reference="TXN-000001").count()
        self.assertEqual(count, 2)

    def test_new_assessment_defaults_to_pending_review(self):
        assessment = self.make_assessment()
        self.assertEqual(
            assessment.review_status, RiskAssessment.ReviewStatus.PENDING
        )

    def test_submission_can_record_which_corporate_sent_it(self):
        log = SubmissionLog.objects.create(
            corporate=self.corporate, reference="TXN-000001", accepted=False
        )
        self.assertEqual(log.corporate, self.corporate)

    def test_submission_from_unknown_corporate_is_allowed(self):
        log = SubmissionLog.objects.create(reference="TXN-000002", accepted=False)
        self.assertIsNone(log.corporate)

    def test_corporate_with_submissions_cannot_be_deleted(self):
        SubmissionLog.objects.create(
            corporate=self.corporate, reference="TXN-000003", accepted=True
        )
        with self.assertRaises(ProtectedError):
            self.corporate.delete()


class TransactionModelTests(TestCase):
    def setUp(self):
        self.corporate = Corporate.objects.create(name="Corporate A")

    def make_transaction(self, reference="TXN-000001", amount="1000.00"):
        return Transaction.objects.create(
            corporate=self.corporate,
            reference=reference,
            type=Transaction.Type.COLLECTION,
            status=Transaction.Status.SUCCESSFUL,
            amount=Decimal(amount),
        )

    def test_amount_is_stored_exactly(self):
        saved = self.make_transaction(amount="1000.10")
        saved.refresh_from_db()
        self.assertEqual(saved.amount, Decimal("1000.10"))

    def test_duplicate_reference_is_rejected(self):
        self.make_transaction()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_transaction()

    def test_zero_amount_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_transaction(reference="TXN-ZERO", amount="0.00")

    def test_negative_amount_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.make_transaction(reference="TXN-NEG", amount="-5.00")

    def test_corporate_with_transactions_cannot_be_deleted(self):
        self.make_transaction()
        with self.assertRaises(ProtectedError):
            self.corporate.delete()


class RepeatedFailuresRuleTests(TestCase):
    def setUp(self):
        self.corporate = Corporate.objects.create(name="Corporate A")
        self.base = timezone.now()  # fixed reference point for every test
        self.counter = 0

    def make_txn(self, status, minutes_before=0, seconds_before=0, corporate=None):
        self.counter += 1
        return Transaction.objects.create(
            corporate=corporate or self.corporate,
            reference=f"TXN-{self.counter:06d}",
            type=Transaction.Type.COLLECTION,
            status=status,
            amount=Decimal("100.00"),
            created_at=self.base
            - timedelta(minutes=minutes_before, seconds=seconds_before),
        )

    def test_two_failures_do_not_fire(self):
        self.make_txn(Transaction.Status.FAILED, minutes_before=2)
        latest = self.make_txn(Transaction.Status.FAILED)
        self.assertIsNone(check_repeated_failures(latest))

    def test_third_failure_fires(self):
        self.make_txn(Transaction.Status.FAILED, minutes_before=2)
        self.make_txn(Transaction.Status.FAILED, minutes_before=1)
        latest = self.make_txn(Transaction.Status.FAILED)
        result = check_repeated_failures(latest)
        self.assertIsNotNone(result)
        self.assertEqual(result.rule_code, "REPEATED_FAILURES")
        self.assertEqual(result.points, 30)
        self.assertIn("3 failed attempts", result.reason)

    def test_failures_spread_over_an_hour_do_not_fire(self):
        self.make_txn(Transaction.Status.FAILED, minutes_before=60)
        self.make_txn(Transaction.Status.FAILED, minutes_before=30)
        latest = self.make_txn(Transaction.Status.FAILED)
        self.assertIsNone(check_repeated_failures(latest))

    def test_success_after_three_failures_fires(self):
        self.make_txn(Transaction.Status.FAILED, minutes_before=5)
        self.make_txn(Transaction.Status.FAILED, minutes_before=4)
        self.make_txn(Transaction.Status.FAILED, minutes_before=3)
        latest = self.make_txn(Transaction.Status.SUCCESSFUL)
        result = check_repeated_failures(latest)
        self.assertIsNotNone(result)
        self.assertIn("3 failed attempts", result.reason)

    def test_failure_exactly_ten_minutes_earlier_counts(self):
        self.make_txn(Transaction.Status.FAILED, minutes_before=10)
        self.make_txn(Transaction.Status.FAILED, minutes_before=1)
        latest = self.make_txn(Transaction.Status.FAILED)
        self.assertIsNotNone(check_repeated_failures(latest))

    def test_failure_just_outside_the_window_does_not_count(self):
        self.make_txn(Transaction.Status.FAILED, minutes_before=10, seconds_before=1)
        self.make_txn(Transaction.Status.FAILED, minutes_before=1)
        latest = self.make_txn(Transaction.Status.FAILED)
        self.assertIsNone(check_repeated_failures(latest))

    def test_other_corporates_failures_do_not_count(self):
        other = Corporate.objects.create(name="Corporate B")
        self.make_txn(Transaction.Status.FAILED, minutes_before=2, corporate=other)
        self.make_txn(Transaction.Status.FAILED, minutes_before=1, corporate=other)
        latest = self.make_txn(Transaction.Status.FAILED)
        self.assertIsNone(check_repeated_failures(latest))


def fake_rule(code, points):
    """A stand-in rule that always fires, so scoring can be tested on its own."""
    return lambda txn: RuleResult(code, points, "test reason")


class AssessTransactionTests(TestCase):
    def setUp(self):
        self.corporate = Corporate.objects.create(name="Corporate A")
        self.base = timezone.now()
        self.counter = 0

    def make_txn(self, status=Transaction.Status.SUCCESSFUL, minutes_before=0):
        self.counter += 1
        return Transaction.objects.create(
            corporate=self.corporate,
            reference=f"TXN-{self.counter:06d}",
            type=Transaction.Type.COLLECTION,
            status=status,
            amount=Decimal("100.00"),
            created_at=self.base - timedelta(minutes=minutes_before),
        )

    def test_nothing_fires_gives_low_risk_with_no_triggered_rules(self):
        assessment = assess_transaction(self.make_txn())
        self.assertEqual(assessment.score, 0)
        self.assertEqual(assessment.result, RiskAssessment.Result.LOW)
        self.assertEqual(assessment.triggered_rules.count(), 0)
        self.assertEqual(
            assessment.review_status, RiskAssessment.ReviewStatus.PENDING
        )

    def test_real_rule_fires_and_is_recorded(self):
        self.make_txn(Transaction.Status.FAILED, minutes_before=2)
        self.make_txn(Transaction.Status.FAILED, minutes_before=1)
        latest = self.make_txn(Transaction.Status.FAILED)
        assessment = assess_transaction(latest)
        self.assertEqual(assessment.score, 30)
        self.assertEqual(assessment.result, RiskAssessment.Result.REVIEW)
        triggered = assessment.triggered_rules.get()
        self.assertEqual(triggered.rule_code, "REPEATED_FAILURES")
        self.assertEqual(triggered.points, 30)

    def test_points_add_up(self):
        rules = [fake_rule("FAKE_A", 30), fake_rule("FAKE_B", 35)]
        assessment = assess_transaction(self.make_txn(), rules=rules)
        self.assertEqual(assessment.score, 65)
        self.assertEqual(assessment.result, RiskAssessment.Result.HIGH)
        self.assertEqual(assessment.triggered_rules.count(), 2)

    def test_score_is_capped_at_100(self):
        rules = [
            fake_rule("FAKE_A", 40),
            fake_rule("FAKE_B", 35),
            fake_rule("FAKE_C", 30),
        ]
        assessment = assess_transaction(self.make_txn(), rules=rules)
        self.assertEqual(assessment.score, 100)
        self.assertEqual(assessment.result, RiskAssessment.Result.HIGH)
        self.assertEqual(assessment.triggered_rules.count(), 3)

    def test_assessing_twice_changes_nothing(self):
        txn = self.make_txn()
        rules = [fake_rule("FAKE_A", 30)]
        first = assess_transaction(txn, rules=rules)
        second = assess_transaction(txn, rules=rules)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(RiskAssessment.objects.filter(transaction=txn).count(), 1)
        self.assertEqual(first.triggered_rules.count(), 1)

    def test_unsaved_transaction_is_refused(self):
        unsaved = Transaction(
            corporate=self.corporate,
            reference="TXN-UNSAVED",
            type=Transaction.Type.COLLECTION,
            status=Transaction.Status.SUCCESSFUL,
            amount=Decimal("100.00"),
        )
        with self.assertRaises(ValueError):
            assess_transaction(unsaved)

    def test_a_failure_while_saving_leaves_no_assessment(self):
        txn = self.make_txn()
        with patch(
            "monitor.scoring.TriggeredRule.objects.create",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                assess_transaction(txn, rules=[fake_rule("FAKE_A", 30)])
        self.assertEqual(RiskAssessment.objects.filter(transaction=txn).count(), 0)


class RuleSettingsTests(SimpleTestCase):
    def test_result_bands_are_in_order(self):
        self.assertTrue(
            0
            < rule_settings.REVIEW_REQUIRED_MIN_SCORE
            < rule_settings.HIGH_RISK_MIN_SCORE
            <= rule_settings.MAX_SCORE
        )