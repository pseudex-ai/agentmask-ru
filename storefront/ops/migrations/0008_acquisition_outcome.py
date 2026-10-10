from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("ops", "0007_acquisition_delivery"),
        ("billing", "0018_subscription_overage_enabled"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="AcquisitionOutcome",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[(k, k) for k in (
                    "qualified_lead", "successful_agent_loop", "renewal_paid",
                    "refund_confirmed", "subscription_cancelled")], max_length=32)),
                ("event_at", models.DateTimeField(db_index=True)),
                ("recorded_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("source", models.CharField(default="staff_attested", editable=False, max_length=24)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("currency", models.CharField(blank=True, default="", max_length=3)),
                ("reference_digest", models.CharField(editable=False, max_length=64, unique=True)),
                ("actor", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="accounts.organization")),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="billing.invoice")),
            ],
            options={"ordering": ("event_at", "pk"), "constraints": [
                models.UniqueConstraint(fields=("invoice", "kind"), condition=models.Q(kind="renewal_paid"),
                                        name="acq_renewal_invoice_once")
            ]},
        ),
    ]
