import uuid
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
import ops.acquisition_consent


class Migration(migrations.Migration):
    dependencies = [
        ("ops", "0005_seoday"),
        ("accounts", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(
        name="AnalyticsGrant",
        fields=[
            ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ("purpose_revision", models.CharField(default="acquisition-v1", max_length=32)),
            ("granted_at", models.DateTimeField(default=django.utils.timezone.now)),
            ("expires_at", models.DateTimeField(default=ops.acquisition_consent.default_expiry, db_index=True)),
            ("revoked_at", models.DateTimeField(null=True, blank=True)),
            ("verified_at", models.DateTimeField(null=True, blank=True)),
            ("client_id", models.CharField(max_length=32, blank=True, default="")),
            ("yclid", models.CharField(max_length=64, blank=True, default="")),
            ("reference_at", models.DateTimeField(default=django.utils.timezone.now)),
            ("user", models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, blank=True,
                                      on_delete=django.db.models.deletion.CASCADE, related_name="analytics_grants")),
            ("organization", models.ForeignKey(to="accounts.organization", null=True, blank=True,
                                              on_delete=django.db.models.deletion.CASCADE, related_name="analytics_grants")),
        ],
    )]
