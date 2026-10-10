import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("ops", "0006_analytics_grant")]
    operations = [
        migrations.CreateModel(
            name="AcquisitionDelivery",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("counter_id", models.CharField(max_length=32)),
                ("organization_id", models.CharField(db_index=True, max_length=32)),
                ("target", models.CharField(max_length=64)),
                ("fact_key", models.CharField(max_length=100)),
                ("event_at", models.DateTimeField()),
                ("state", models.CharField(db_index=True, default="unknown", max_length=24)),
                ("uploading_id", models.BigIntegerField(null=True)),
                ("remote_status", models.CharField(blank=True, max_length=24)),
                ("source_quantity", models.PositiveIntegerField(null=True)),
                ("line_quantity", models.PositiveIntegerField(null=True)),
                ("error_code", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("checked_at", models.DateTimeField(null=True)),
                ("grant", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="ops.analyticsgrant")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("counter_id", "organization_id", "target"), name="acq_first_outcome_once")]},
        ),
    ]
