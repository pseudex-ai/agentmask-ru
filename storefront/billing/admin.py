"""The back office.

This is the lever that keeps manual support near zero: every routine
intervention — mark an invoice paid, resume a stopped customer, issue a key — is
one click here rather than a shell on a production box. Django's admin also logs
who did what, which a shell does not.

WHAT IS DELIBERATELY NOT HERE: any way to read a license key. Keys are stored as
a prefix and a hash, so this screen cannot show one even if someone wanted it to,
and a support person with admin access still cannot impersonate a customer's
gateway.
"""

from django.contrib import admin, messages
from django.utils import timezone

from billing import licensing, services
from billing.models import Invoice, LicenseKey, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "monthly_price", "max_instances",
                    "included_values", "rpm_limit", "max_keys", "is_public")
    list_editable = ("monthly_price", "included_values", "is_public")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("organization", "plan", "state", "trial_ends_at",
                    "current_period_end", "cancel_at_period_end")
    list_filter = ("state", "plan")
    search_fields = ("organization__id", "organization__display_name")
    actions = ("action_resume", "action_mark_unpaid")

    @admin.action(description="Возобновить обслуживание (оплачено)")
    def action_resume(self, request, queryset):
        for subscription in queryset:
            try:
                licensing.set_status(subscription.organization_id, "active")
            except licensing.LicensingError as error:
                # Reported per row, not as one summary: a partial failure over a
                # multi-select is exactly where a customer gets silently left
                # stopped.
                self.message_user(request, f"{subscription.organization_id}: {error}",
                                  level=messages.ERROR)
                continue
            subscription.state = Subscription.ACTIVE
            subscription.save(update_fields=["state"])
            self.message_user(request, f"{subscription.organization_id}: возобновлено")

    @admin.action(description="Остановить за неоплату")
    def action_mark_unpaid(self, request, queryset):
        for subscription in queryset:
            try:
                services.mark_unpaid(subscription.organization)
            except licensing.LicensingError as error:
                self.message_user(request, f"{subscription.organization_id}: {error}",
                                  level=messages.ERROR)
                continue
            self.message_user(request, f"{subscription.organization_id}: остановлено")


@admin.register(LicenseKey)
class LicenseKeyAdmin(admin.ModelAdmin):
    list_display = ("prefix", "organization", "environment", "label",
                    "created_at", "revoked_at")
    list_filter = ("environment",)
    search_fields = ("prefix", "organization__id", "organization__display_name")
    # The hash is not a secret, but showing it invites someone to treat it as an
    # identifier to paste around. Nothing here needs it.
    exclude = ("key_hash",)
    readonly_fields = ("prefix", "created_at", "last_seen_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "organization", "state", "total",
                    "period_start", "period_end", "due_at", "paid_at")
    list_filter = ("state",)
    search_fields = ("number", "organization__id", "organization__display_name")
    actions = ("action_mark_paid",)

    @admin.action(description="Отметить оплаченным и возобновить обслуживание")
    def action_mark_paid(self, request, queryset):
        for invoice in queryset.exclude(state=Invoice.PAID):
            try:
                services.mark_paid(invoice)
            except licensing.LicensingError as error:
                self.message_user(request, f"{invoice.number}: {error}",
                                  level=messages.ERROR)
                continue
            self.message_user(request, f"{invoice.number}: оплачен, сервис возобновлён")
