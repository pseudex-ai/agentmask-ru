"""Staff-only beta lead inbox under the existing OTP-protected admin site."""

from django.contrib import admin

from ops.models import ProductInterest


@admin.register(ProductInterest)
class ProductInterestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "product", "email", "role", "harness", "use_case")
    list_filter = ("product", "role", "harness", "use_case", "created_at")
    # Do not put email search strings into GET URLs/admin access logs.
    readonly_fields = ("product", "email", "role", "harness", "use_case",
                       "consent_at", "consent_revision", "created_at")
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Staff may read with view_productinterest, but cannot invent or edit
        # evidence of user consent through the inbox.
        return False

    def has_delete_permission(self, request, obj=None):
        return False
