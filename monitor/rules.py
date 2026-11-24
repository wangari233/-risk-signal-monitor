from dataclasses import dataclass
from decimal import Decimal

from .models import Transaction
from .rule_settings import (
    RAPID_FUNDING_MIN_FRACTION,
    RAPID_FUNDING_POINTS,
    RAPID_FUNDING_WINDOW,
    REPEATED_FAILURES_LIMIT,
    REPEATED_FAILURES_POINTS,
    REPEATED_FAILURES_WINDOW,
    UNUSUAL_AMOUNT_MIN_HISTORY,
    UNUSUAL_AMOUNT_MULTIPLIER,
    UNUSUAL_AMOUNT_POINTS,
)

REPEATED_FAILURES_CODE = "REPEATED_FAILURES"
UNUSUAL_AMOUNT_CODE = "UNUSUAL_AMOUNT"
RAPID_FUNDING_CODE = "RAPID_FUNDING_PAYOUT"

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


def check_unusual_amount(txn):
    """Flag a transaction whose amount is more than 5 times the average of the
    same corporate's earlier successful transactions in the same currency.
    Skipped when there are fewer than 5 such transactions.

    Returns a RuleResult, or None if the rule does not fire.
    """
    history = list(
        Transaction.objects.filter(
            corporate=txn.corporate,
            currency=txn.currency,
            status=Transaction.Status.SUCCESSFUL,
            created_at__lt=txn.created_at,
        )
        .exclude(pk=txn.pk)
        .values_list("amount", flat=True)
    )

    if len(history) < UNUSUAL_AMOUNT_MIN_HISTORY:
        return None

    average = sum(history, Decimal("0")) / len(history)
    if txn.amount <= average * UNUSUAL_AMOUNT_MULTIPLIER:
        return None

    return RuleResult(
        rule_code=UNUSUAL_AMOUNT_CODE,
        points=UNUSUAL_AMOUNT_POINTS,
        reason=(
            f"Amount {txn.amount} is more than {UNUSUAL_AMOUNT_MULTIPLIER} times "
            f"the average of {average.quantize(Decimal('0.01'))} "
            f"over {len(history)} earlier transactions"
        ),
    )

def check_rapid_funding_payout(txn):
    """Flag a successful payout that is 80% or more of the money the same
    corporate received through successful collections in the 30 minutes
    before it (same currency).

    Returns a RuleResult, or None if the rule does not fire.
    """
    if (
        txn.type != Transaction.Type.PAYOUT
        or txn.status != Transaction.Status.SUCCESSFUL
    ):
        return None

    window_start = txn.created_at - RAPID_FUNDING_WINDOW
    deposits = list(
        Transaction.objects.filter(
            corporate=txn.corporate,
            currency=txn.currency,
            type=Transaction.Type.COLLECTION,
            status=Transaction.Status.SUCCESSFUL,
            created_at__gte=window_start,
            created_at__lt=txn.created_at,
        ).values_list("amount", flat=True)
    )

    total = sum(deposits, Decimal("0"))
    if total == 0:
        return None

    if txn.amount < total * RAPID_FUNDING_MIN_FRACTION:
        return None

    percent = (txn.amount / total * 100).quantize(Decimal("0.1"))
    minutes = int(RAPID_FUNDING_WINDOW.total_seconds() // 60)
    return RuleResult(
        rule_code=RAPID_FUNDING_CODE,
        points=RAPID_FUNDING_POINTS,
        reason=(
            f"Payout of {txn.amount} is {percent}% of the {total} "
            f"collected in the last {minutes} minutes"
        ),
    )