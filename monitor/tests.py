from datetime import timedelta
from decimal import Decimal

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
from .rules import check_repeated_failures


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


class RuleSettingsTests(SimpleTestCase):
    def test_result_bands_are_in_order(self):
        self.assertTrue(
            0
            < rule_settings.REVIEW_REQUIRED_MIN_SCORE
            < rule_settings.HIGH_RISK_MIN_SCORE
            <= rule_settings.MAX_SCORE
        )