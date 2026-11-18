from django.db import models
from django.utils import timezone


class Corporate(models.Model):
    name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class Transaction(models.Model):
    class Type(models.TextChoices):
        COLLECTION = "COLLECTION", "Collection"
        PAYOUT = "PAYOUT", "Payout"

    class Status(models.TextChoices):
    SUCCESSFUL = "SUCCESSFUL", "Successful"
    FAILED = "FAILED", "Failed"

    corporate = models.ForeignKey(
        Corporate, on_delete=models.PROTECT, related_name="transactions"
    )
    reference = models.CharField(max_length=64, unique=True)
    type = models.CharField(max_length=10, choices=Type.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")
    destination = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="transaction_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["corporate", "created_at"]),
        ]

    def __str__(self):
        return self.reference


class SubmissionLog(models.Model):
    reference = models.CharField(max_length=64, db_index=True)
    received_at = models.DateTimeField(default=timezone.now)
    accepted = models.BooleanField()

        def __str__(self):
            return f"{self.reference}  ({'accepted' if self.accepted else 'rejected'})"


class RiskAssessment(models.Model):
    class Result(models.TextChoices):
        LOW = "LOW", "Low Risk"
        REVIEW = "REVIEW", "Review Required"
        HIGH = "HIGH", "High Risk"

    class ReviewStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CLEARED = "CLEARED", "Cleared"

    transaction = models.OneToOneField(
        Transaction, on_delete=models.PROTECT, related_name="assessment"
    )
    score = models.PositiveSmallIntegerField()
    result = models.CharField(max_length=6, choices=Result.choices)
    review_status = models.CharField(
        max_length=10,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    review_note = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    assessed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(score__range=(0, 100)),
                name="assessment_score_0_to_100",
            ),
        ]

    def __str__(self):
        return f"{self.transaction.reference}: {self.get_result_display()} ({self.score})"


class TriggeredRule(models.Model):
    assessment = models.ForeignKey(
        RiskAssessment, on_delete=models.PROTECT, related_name="triggered_rules"
    )
    rule_code = models.CharField(max_length=40)
    points = models.PositiveSmallIntegerField()
    reason = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assessment", "rule_code"],
                name="unique_rule_per_assessment",
            ),
        ]

    def __str__(self):
        return f"{self.rule_code} (+{self.points})"
