"""Every threshold, window and point value used by the risk monitor.

Change values here and nowhere else. Changes go through a pull request,
so each one is reviewed. These are starting values, tuned during testing.
"""

from datetime import timedelta
from decimal import Decimal

# Result bands: a score at or above a minimum gets that label.
MAX_SCORE = 100
REVIEW_REQUIRED_MIN_SCORE = 25
HIGH_RISK_MIN_SCORE = 60

# Rule 1: repeated failed attempts
REPEATED_FAILURES_POINTS = 30
REPEATED_FAILURES_LIMIT = 3
REPEATED_FAILURES_WINDOW = timedelta(minutes=10)

# Rule 2: duplicate reference
DUPLICATE_REFERENCE_POINTS = 40

# Rule 3: amount far from normal
UNUSUAL_AMOUNT_POINTS = 25
UNUSUAL_AMOUNT_MULTIPLIER = Decimal("5")
UNUSUAL_AMOUNT_MIN_HISTORY = 5

# Rule 4: rapid funding then payout
RAPID_FUNDING_POINTS = 35
RAPID_FUNDING_MIN_FRACTION = Decimal("0.80")
RAPID_FUNDING_WINDOW = timedelta(minutes=30)
