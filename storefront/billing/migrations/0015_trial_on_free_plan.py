"""Пробные подписки, заведённые ДО выделенного пробного тарифа, сидят на обычном
тарифе (обычно `start`) — из-за чего кабинет показывал платный тариф на пробе.
Экранный дефект уже закрыт `display_plan`, но сама строка подписки всё ещё несёт
`start`. Здесь она переводится на пробный тариф (`free`), а выбранный человеком
тариф сохраняется в `intended_plan`, чтобы кабинет по-прежнему предлагал именно
его. Идемпотентно: повторный прогон не находит таких подписок.
"""
from django.db import migrations


def move_trials_to_free(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    Subscription = apps.get_model("billing", "Subscription")

    trial = Plan.objects.filter(is_trial=True).first()
    if trial is None:
        # Пробного тарифа в этой инсталляции нет — переводить не на что.
        return

    stuck = Subscription.objects.filter(state="trial").exclude(plan=trial)
    for sub in stuck:
        fields = ["plan"]
        if sub.intended_plan_id is None:
            sub.intended_plan_id = sub.plan_id
            fields.append("intended_plan")
        sub.plan = trial
        sub.save(update_fields=fields)


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0014_invoice_bonus_days_invoice_target_plan_and_more"),
    ]

    operations = [
        migrations.RunPython(move_trials_to_free, migrations.RunPython.noop),
    ]
