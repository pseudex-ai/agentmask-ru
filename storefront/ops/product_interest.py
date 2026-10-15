"""Consented beta contacts, deliberately separate from anonymous demand/analytics."""

from django.db import models


class ProductInterest(models.Model):
    class Product(models.TextChoices):
        ENTERPRISE = "enterprise", "AI Security для компании"
        CODING = "coding", "AI Coding"

    class Role(models.TextChoices):
        SECURITY = "security", "Информационная безопасность"
        PLATFORM = "platform", "ИТ / платформа"
        DEVELOPER = "developer", "Разработчик"
        LEAD = "lead", "Руководитель команды"
        OTHER = "other", "Другая роль"

    class Harness(models.TextChoices):
        CLAUDE_CODE = "claude_code", "Claude Code"
        CURSOR = "cursor", "Cursor"
        CODEX = "codex", "Codex"
        OTHER = "other", "Другой инструмент"
        UNDECIDED = "undecided", "Пока выбираем"

    class UseCase(models.TextChoices):
        DATA_PROTECTION = "data_protection", "Защита данных при работе с ИИ"
        AGENT_CONTROL = "agent_control", "Контроль ИИ-агентов"
        SECURE_CODING = "secure_coding", "Безопасный AI-кодинг"
        EVALUATION = "evaluation", "Оценка для пилота"

    product = models.CharField(max_length=16, choices=Product.choices)
    role = models.CharField(max_length=16, choices=Role.choices)
    harness = models.CharField(max_length=16, choices=Harness.choices)
    use_case = models.CharField(max_length=24, choices=UseCase.choices)
    email = models.EmailField(max_length=254)
    consent_at = models.DateTimeField()
    consent_revision = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = "заявка на ранний доступ"
        verbose_name_plural = "заявки на ранний доступ"
        constraints = [
            models.CheckConstraint(condition=models.Q(product__in=("enterprise", "coding")), name="product_interest_product_closed"),
            models.CheckConstraint(condition=models.Q(role__in=("security", "platform", "developer", "lead", "other")), name="product_interest_role_closed"),
            models.CheckConstraint(condition=models.Q(harness__in=("claude_code", "cursor", "codex", "other", "undecided")), name="product_interest_harness_closed"),
            models.CheckConstraint(condition=models.Q(use_case__in=("data_protection", "agent_control", "secure_coding", "evaluation")), name="product_interest_use_case_closed"),
        ]

    def __str__(self):
        # Object labels enter admin history/logs; the contact belongs in its
        # explicitly permission-protected field, not an incidental repr.
        return f"{self.get_product_display()} · #{self.pk}"
