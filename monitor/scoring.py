from django.db import transaction

from .models import RiskAssessment, TriggeredRule
from .rule_settings import MAX_SCORE
from .rules import check_repeated_failures

# Every rule the monitor runs. Add new rules here as they are written.
RULES = [check_repeated_failures]


def assess_transaction(txn, rules=None):
    """Run every rule on a saved transaction and record the outcome.

    Returns the RiskAssessment. If the transaction was already assessed,
    the existing assessment is returned unchanged.
    """
    rules = RULES if rules is None else rules

    if txn.pk is None:
        raise ValueError("Transaction must be saved before it can be assessed.")

    existing = RiskAssessment.objects.filter(transaction=txn).first()
    if existing is not None:
        return existing

    results = []
    for rule in rules:
        result = rule(txn)
        if result is not None:
            results.append(result)

    total = sum(result.points for result in results)
    score = min(total, MAX_SCORE)

    with transaction.atomic():
        assessment = RiskAssessment.objects.create(
            transaction=txn,
            score=score,
            result=RiskAssessment.result_for(score),
        )
        for result in results:
            TriggeredRule.objects.create(
                assessment=assessment,
                rule_code=result.rule_code,
                points=result.points,
                reason=result.reason,
            )

    return assessment