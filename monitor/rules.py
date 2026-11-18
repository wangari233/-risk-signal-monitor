from dataclasses import dataclass
from datetime import timedelta

from .models import Transaction

REPEATED_FAILURES_CODE = "REPEATED_FAILURES"
REPEATED_FAILURES_POINTS = 30
REPEATED_FAILURES_LIMIT = 3
REPEATED_FAILURES_WINDOW = timedelta(minutes=10)


@dataclass(frozen=True)
class RuleResult:
    rule_code: str
    points: int
    reason: str


def check_repeated_failures(txn):
    """Flag a transaction when its corporate has 3 or more failed attempts
    within the 10 minutes up to and including this transaction's time.
    A successful transaction after 3 or more such failures also fires.

    Returns a RuleResult, or None if the rule does not fire.
    """
    window_start = txn.created_at - REPEATED_FAILURES_WINDOW

    # Other failed attempts by the same corporate inside the window.
    # The transaction itself is excluded so it is never counted twice,
    # whether or not it has been saved yet.
    failures = (
        Transaction.objects.filter(
            corporate=txn.corporate,
            status=Transaction.Status.FAILED,
            created_at__gte=window_start,
            created_at__lte=txn.created_at,
        )
        .exclude(pk=txn.pk)
        .count()
    )

    # If this transaction is itself a failure, it counts as one attempt.
    if txn.status == Transaction.Status.FAILED:
        failures += 1

    if failures < REPEATED_FAILURES_LIMIT:
        return None

    minutes = int(REPEATED_FAILURES_WINDOW.total_seconds() // 60)
    return RuleResult(
        rule_code=REPEATED_FAILURES_CODE,
        points=REPEATED_FAILURES_POINTS,
        reason=f"{failures} failed attempts within {minutes} minutes",
    )