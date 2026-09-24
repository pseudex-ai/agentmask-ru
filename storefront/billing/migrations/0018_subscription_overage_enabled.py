from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0017_plan_offer_notes'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='overage_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
