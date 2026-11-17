from django.contrib import admin

from .models import (
    Corporate,
    RiskAssessment,
    SubmissionLog,
    Transaction,
    TriggeredRule,
)


class NoDeleteAdmin(admin.ModelAdmin):
    """Base admin class: records can be viewed and edited but never deleted."""

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Corporate)
class CorporateAdmin(NoDeleteAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Transaction)
class TransactionAdmin(NoDeleteAdmin):
    list_display = ("reference", "corporate", "type", "status", "amount", "created_at")
    list_filter = ("type", "status")
    search_fields = ("reference",)


@admin.register(SubmissionLog)
class SubmissionLogAdmin(NoDeleteAdmin):
    list_display = ("reference", "received_at", "accepted")
    list_filter = ("accepted",)


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(NoDeleteAdmin):
    list_display = ("transaction", "score", "result", "review_status", "assessed_at")
    list_filter = ("result", "review_status")


@admin.register(TriggeredRule)
class TriggeredRuleAdmin(NoDeleteAdmin):
    list_display = ("assessment", "rule_code", "points", "reason")
    list_filter = ("rule_code",)