from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import Membership, Organization, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "is_staff", "is_active", "date_joined")
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Права", {"fields": ("is_active", "is_staff", "is_superuser",
                              "groups", "user_permissions")}),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",),
                             "fields": ("email", "password1", "password2")}),)


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "legal_name", "inn", "created_at",
                    "trial_granted", "signup_email_domain")
    list_filter = ("trial_granted",)
    search_fields = ("id", "display_name", "legal_name", "inn",
                     "signup_email_domain")
    readonly_fields = ("id", "created_at", "signup_ip_hash", "signup_email_domain")
    inlines = [MembershipInline]
    actions = ("action_grant_trial",)

    @admin.action(description="Выдать пробный период (снять отметку повтора)")
    def action_grant_trial(self, request, queryset):
        """Вернуть пробу тому, кого фильтр повторов задел зря.

        ФИЛЬТР ОШИБАЕТСЯ В ЖИВУЮ СТОРОНУ, И ЭТО ЗНАЛИ ЗАРАНЕЕ: один офис за NAT
        — это один адрес, поэтому второй настоящий клиент оттуда пробы не
        получит. Автоматике такое не доверишь, а решение одного человека за
        десять секунд — можно. Дни отсчитываются ОТ СЕЙЧАС, а не от регистрации:
        человек, которому проба досталась через сутки после отказа, получает её
        целиком, а не остаток.
        """
        from django.utils import timezone
        from datetime import timedelta
        from billing import services
        trial = services.trial_plan()
        if trial is None:
            self.message_user(request, "Пробного тарифа нет — отметьте его в тарифах.",
                              level=messages.ERROR)
            return
        granted = 0
        for organization in queryset:
            subscription = getattr(organization, "subscription", None)
            if subscription is None:
                continue
            organization.trial_granted = True
            organization.save(update_fields=["trial_granted"])
            subscription.trial_ends_at = timezone.now() + timedelta(days=trial.trial_days)
            subscription.save(update_fields=["trial_ends_at"])
            granted += 1
        self.message_user(request, f"Проба выдана: {granted}. "
                                   f"Дней: {trial.trial_days}, от текущего момента.")
